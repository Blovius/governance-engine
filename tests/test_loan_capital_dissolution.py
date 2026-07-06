import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import DecisionState, ActorState, DecisionMode
from core.actions import Action
from core.constraints import ConstraintStatus, Mode
from knowledge.rules import CreditorDutyConsideration, WrongfulTradingGate
from simulate.simulation import Simulation
from llm.interface import Narrator
from scenarios.loan_capital_dissolution import initial_state, build_engine, simple_transition


def make_sim():
    return Simulation(engine=build_engine(), transition=simple_transition, narrator=Narrator())


# --- CreditorDutyConsideration: unit tests ---

def test_creditor_duty_not_raised_while_solvent():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"solvent": True},
    )
    action = Action(action_id="a1", actor_id="chair", kind="vote", payload={})
    result = CreditorDutyConsideration.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS  # rule doesn't even apply
    assert result.applies is False


def test_creditor_duty_raised_once_insolvent():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"solvent": False},
    )
    action = Action(action_id="a1", actor_id="chair", kind="vote", payload={})
    result = CreditorDutyConsideration.evaluate(state, action)
    assert result.status == ConstraintStatus.WARN
    assert result.mode == Mode.SYNTHESISE
    assert "Sequana" in result.message


# --- WrongfulTradingGate: unit tests ---

def test_wrongful_trading_does_not_apply_while_solvent():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"solvent": True, "no_reasonable_prospect": True},
    )
    action = Action(action_id="a1", actor_id="cfo", kind="incur_new_credit", payload={"amount": 10_000})
    result = WrongfulTradingGate.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS  # solvent - doesn't apply regardless of the other flag
    assert result.applies is False


def test_wrongful_trading_blocks_when_insolvent_and_no_prospect():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"solvent": False, "no_reasonable_prospect": True, "advice_sought": False},
    )
    action = Action(action_id="a1", actor_id="cfo", kind="incur_new_credit", payload={"amount": 10_000})
    result = WrongfulTradingGate.evaluate(state, action)
    assert result.status == ConstraintStatus.BLOCK
    assert "s.214" in result.message


def test_wrongful_trading_defeated_once_advice_sought():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"solvent": False, "no_reasonable_prospect": True, "advice_sought": True},
    )
    action = Action(action_id="a1", actor_id="cfo", kind="incur_new_credit", payload={"amount": 10_000})
    result = WrongfulTradingGate.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS  # defeater fired
    assert result.applies is True  # rule applied - the defeater is what let it pass


def test_wrongful_trading_does_not_apply_if_prospect_still_reasonable():
    """Insolvent but not yet at the 'no reasonable prospect' threshold - not blocked."""
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"solvent": False, "no_reasonable_prospect": False, "advice_sought": False},
    )
    action = Action(action_id="a1", actor_id="cfo", kind="incur_new_credit", payload={"amount": 10_000})
    result = WrongfulTradingGate.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS
    assert result.applies is False


# --- End-to-end: the full deterioration narrative ---

def test_solvency_is_genuinely_computed_not_asserted():
    """Confirms solvency is arithmetic (assets vs liabilities), not a flag the caller sets."""
    sim = make_sim()
    state = initial_state()
    assert state.facts["solvent"] is True  # 500k assets vs 350k liabilities

    # A large loss: assets drop by 200k -> 300k assets vs 350k liabilities -> insolvent
    result = sim.step(state, Action(
        action_id="a1", actor_id="cfo", kind="record_trading_update",
        payload={"asset_delta": -200_000},
    ))
    assert result.state.facts["solvent"] is False
    assert result.state.facts["total_assets"] == 300_000
    assert result.state.facts["total_liabilities"] == 350_000


def test_full_deterioration_to_wrongful_trading_and_advice():
    sim = make_sim()
    state = initial_state()

    # 1. Solvent: new credit raised without friction
    r1 = sim.step(state, Action(
        action_id="a1", actor_id="cfo", kind="incur_new_credit", payload={"amount": 20_000},
    ))
    assert r1.blocked is False
    state = r1.state
    assert state.facts["solvent"] is True

    # 2. Trading update pushes the company into insolvency
    r2 = sim.step(state, Action(
        action_id="a2", actor_id="cfo", kind="record_trading_update",
        payload={"asset_delta": -250_000},
    ))
    assert r2.blocked is False
    state = r2.state
    assert state.facts["solvent"] is False

    # 3. A vote now raises the creditor duty consideration (SYNTHESISE, not blocking)
    r3 = sim.step(state, Action(
        action_id="a3", actor_id="chair", kind="vote",
        payload={"matter_id": "routine", "outcome": "approved"},
    ))
    assert r3.blocked is False
    creditor_warnings = [r for r in r3.results if r.rule_id == "CREDITOR_DUTY_SEQUANA"]
    assert len(creditor_warnings) == 1
    assert creditor_warnings[0].status == ConstraintStatus.WARN
    state = r3.state

    # 4. Further deterioration crosses into "no reasonable prospect"
    r4 = sim.step(state, Action(
        action_id="a4", actor_id="cfo", kind="record_trading_update",
        payload={"asset_delta": -50_000, "no_reasonable_prospect_flag": True},
    ))
    state = r4.state
    assert state.facts["no_reasonable_prospect"] is True

    # 5. Attempt to raise further credit -> blocked under s.214
    r5 = sim.step(state, Action(
        action_id="a5", actor_id="cfo", kind="incur_new_credit", payload={"amount": 15_000},
    ))
    assert r5.blocked is True
    assert "WRONGFUL_TRADING_S214" in [r.rule_id for r in r5.results if r.status == ConstraintStatus.BLOCK]
    # state must not have advanced - the credit was NOT raised
    assert r5.state.facts["new_credit_raised"] == 20_000  # unchanged from step 1

    # 6. Seek professional advice
    r6 = sim.step(state, Action(action_id="a6", actor_id="chair", kind="seek_advice", payload={}))
    assert r6.blocked is False
    state = r6.state
    assert state.facts["advice_sought"] is True

    # 7. Attempt to raise credit again -> now permitted (defeater satisfied)
    r7 = sim.step(state, Action(
        action_id="a7", actor_id="cfo", kind="incur_new_credit", payload={"amount": 15_000},
    ))
    assert r7.blocked is False
    assert r7.state.facts["new_credit_raised"] == 35_000


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

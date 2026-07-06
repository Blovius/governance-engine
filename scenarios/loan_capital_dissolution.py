"""
scenarios/loan_capital_dissolution.py

Loan Capital and Dissolution: The Zone of Insolvency (Week 9).

A company has drawn down a loan facility. Trading deteriorates over
several ticks. Unlike the board-crisis scenario (one meeting, one
decision), this is a genuinely RUNNING-TIME story: solvency is
recalculated as a computed fact after every trading update, and the
directors' duty consideration shifts as that fact changes - without
anyone having to vote on whether it should.

Setup: total_assets and total_liabilities start with a healthy margin.
A sequence of trading updates erodes it. Once liabilities exceed
assets, the company is insolvent, and CreditorDutyConsideration is
raised on every substantive decision from that point on. If the
scenario also reaches "no reasonable prospect" of recovery and the
board tries to raise further credit without first seeking advice,
WrongfulTradingGate blocks it - a genuinely different consequence
shape from anything in the board-crisis scenario, because the SAME
threshold recalculates automatically as more trading updates arrive,
rather than being set once at the start.

The story:
  1. Solvent. New credit raised without any friction.
  2. A trading update pushes liabilities past assets -> insolvent.
     CreditorDutyConsideration is now raised on every decision.
  3. A further update crosses into "no reasonable prospect" territory.
  4. Attempt to raise more credit -> blocked (s.214).
  5. Seek professional advice (the defeater).
  6. Attempt to raise credit again -> permitted, because the board has
     now taken the mitigating step the statute treats as relevant.
"""
from core.state import DecisionState, ActorState, DecisionMode
from core.actions import Action
from knowledge.rules import ALL_RULES
from core.engine import ConstraintEngine


SCENARIO_ID = "loan_capital_dissolution_v1"


def initial_state() -> DecisionState:
    actors = frozenset({
        ActorState(actor_id="chair", role="chair"),
        ActorState(actor_id="ned_1", role="non_executive_director"),
        ActorState(actor_id="cfo", role="cfo"),
    })
    return DecisionState(
        scenario_id=SCENARIO_ID,
        mode=DecisionMode.SIMULATE,
        step=0,
        actors=actors,
        facts={
            "directors_present": 3,
            "quorum_required": 2,
            "present_actor_ids": frozenset({"chair", "ned_1", "cfo"}),
            "total_assets": 500_000,
            "total_liabilities": 350_000,
            "solvent": True,               # computed below; True at start (assets > liabilities)
            "no_reasonable_prospect": False,
            "advice_sought": False,
            "new_credit_raised": 0,
        },
        history=(),
    )


def build_engine() -> ConstraintEngine:
    return ConstraintEngine(ALL_RULES)


def _recompute_solvency(facts: dict) -> dict:
    """The genuinely computed part: solvency is arithmetic, not a flag someone sets."""
    facts["solvent"] = facts["total_assets"] >= facts["total_liabilities"]
    return facts


def simple_transition(state: DecisionState, action: Action) -> DecisionState:
    facts = dict(state.facts)

    if action.kind == "record_trading_update":
        # A trading update changes the position - e.g. a loss reduces
        # assets, a new liability (further drawdown, accrued interest)
        # increases liabilities. The payload carries the deltas; the
        # engine computes the consequence, it is never asserted by
        # the caller.
        facts["total_assets"] = facts["total_assets"] + action.payload.get("asset_delta", 0)
        facts["total_liabilities"] = facts["total_liabilities"] + action.payload.get("liability_delta", 0)
        facts = _recompute_solvency(facts)
        if action.payload.get("no_reasonable_prospect_flag") is not None:
            facts["no_reasonable_prospect"] = bool(action.payload["no_reasonable_prospect_flag"])
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "incur_new_credit":
        facts["new_credit_raised"] = facts.get("new_credit_raised", 0) + action.payload.get("amount", 0)
        facts["total_liabilities"] = facts["total_liabilities"] + action.payload.get("amount", 0)
        facts = _recompute_solvency(facts)
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "seek_advice":
        facts["advice_sought"] = True
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "cease_trading":
        facts["ceased_trading"] = True
        return state.evolve(facts=facts, step=state.step + 1)

    return state.evolve(step=state.step + 1)

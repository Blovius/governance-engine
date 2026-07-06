import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.actions import Action
from simulate.simulation import Simulation
from llm.interface import Narrator
from scenarios.board_crisis import initial_state, build_engine, simple_transition


def make_sim():
    return Simulation(engine=build_engine(), transition=simple_transition, narrator=Narrator())


def test_undeclared_conflicted_vote_is_blocked_end_to_end():
    sim = make_sim()
    state = initial_state()

    action = Action(
        action_id="a1", actor_id="exec_director", kind="vote",
        payload={"matter_id": "related_party_contract"},
    )
    result = sim.step(state, action)

    assert result.blocked is True
    assert "s175" in result.narration or "board cannot proceed" in result.narration.lower()
    # state must NOT have advanced - a blocked action changes nothing
    assert result.state.step == 0


def test_declare_then_authorise_then_vote_succeeds():
    sim = make_sim()
    state = initial_state()

    # Step 1: exec director declares the interest (s177 satisfied)
    declare = Action(
        action_id="a1", actor_id="exec_director", kind="declare_interest",
        payload={"matter_id": "related_party_contract"},
    )
    r1 = sim.step(state, declare)
    assert r1.blocked is False
    state = r1.state

    # Step 2: board authorises participation (defeats the s175 default block)
    authorise = Action(
        action_id="a2", actor_id="chair", kind="authorise_participation",
        payload={"matter_id": "related_party_contract"},
    )
    r2 = sim.step(state, authorise)
    assert r2.blocked is False
    state = r2.state

    # Step 3: exec director may now vote
    vote = Action(
        action_id="a3", actor_id="exec_director", kind="vote",
        payload={"matter_id": "related_party_contract", "outcome": "approved"},
    )
    r3 = sim.step(state, vote)
    assert r3.blocked is False
    assert r3.state.facts["last_vote_outcome"] == "approved"
    assert r3.state.step == 3
    assert len(r3.state.history) == 3


def test_quorum_fails_if_conflicted_director_excluded_and_only_two_remain():
    sim = make_sim()
    state = initial_state()
    # Simulate excluding the conflicted director from the room entirely:
    # quorum required is 3, only 2 remain if exec_director steps out.
    state = state.evolve(facts={**state.facts, "directors_present": 2})

    vote = Action(
        action_id="a1", actor_id="chair", kind="vote",
        payload={"matter_id": "related_party_contract", "outcome": "approved"},
    )
    result = sim.step(state, vote)
    assert result.blocked is True
    assert "Quorum" in result.narration


def test_synthesise_duty_of_care_does_not_block_a_clean_vote():
    """The board can proceed even though s174 is raised - it's judgment, not a gate."""
    sim = make_sim()
    state = initial_state()

    vote = Action(
        action_id="a1", actor_id="ned_1", kind="vote",
        payload={"matter_id": "routine_matter", "outcome": "approved"},
    )
    result = sim.step(state, vote)
    assert result.blocked is False   # WARN mode never blocks
    # confirm the duty was still raised in the results, just not blocking
    warn_results = [r for r in result.results if r.rule_id == "CARE_174"]
    assert len(warn_results) == 1
    assert warn_results[0].status.value == "warn"


def test_vote_blocked_when_neds_have_left_the_room():
    """
    The genuine branching case: same conflict resolved the same way
    (declared, authorised), but the NEDs have left the room, so the
    independent-majority gate now blocks a vote that would otherwise
    have succeeded. Composition, not just conduct, is checked.
    """
    sim = make_sim()
    state = initial_state()

    state = sim.step(state, Action(
        action_id="a1", actor_id="exec_director", kind="declare_interest",
        payload={"matter_id": "related_party_contract"},
    )).state
    state = sim.step(state, Action(
        action_id="a2", actor_id="chair", kind="authorise_participation",
        payload={"matter_id": "related_party_contract"},
    )).state

    # Both NEDs leave the room
    state = sim.step(state, Action(action_id="a3", actor_id="ned_1", kind="leave_room")).state
    state = sim.step(state, Action(action_id="a4", actor_id="ned_2", kind="leave_room")).state

    result = sim.step(state, Action(
        action_id="a5", actor_id="exec_director", kind="vote",
        payload={"matter_id": "related_party_contract", "outcome": "approved"},
    ))
    assert result.blocked is True
    blocking_ids = [r.rule_id for r in result.results if r.status.value == "block"]
    assert "INDMAJ_001" in blocking_ids


def test_full_scenario_branches_through_filing_and_capital_maintenance():
    """
    The complete 8-step narrative: declare, authorise, vote (full board
    present, so independent majority holds), trigger a filing
    requirement as a CONSEQUENCE of the vote, get blocked closing
    before filing, file, close successfully, get blocked overpaying,
    then pay correctly within reserves.
    """
    sim = make_sim()
    state = initial_state()

    # 1. Declare + 2. authorise
    state = sim.step(state, Action(
        action_id="a1", actor_id="exec_director", kind="declare_interest",
        payload={"matter_id": "related_party_contract"},
    )).state
    state = sim.step(state, Action(
        action_id="a2", actor_id="chair", kind="authorise_participation",
        payload={"matter_id": "related_party_contract"},
    )).state

    # 3. Vote succeeds (full board present -> independent majority holds)
    r3 = sim.step(state, Action(
        action_id="a3", actor_id="exec_director", kind="vote",
        payload={"matter_id": "related_party_contract", "outcome": "approved"},
    ))
    assert r3.blocked is False
    state = r3.state
    # 4. Consequence: filing now required, because contract_value (750k) > threshold (500k)
    assert state.facts["filing_required"] is True
    assert state.facts["notification_filed"] is False

    # 5. Attempt to close before filing -> blocked (sequence constraint)
    r5 = sim.step(state, Action(action_id="a4", actor_id="chair", kind="close_contract", payload={}))
    assert r5.blocked is True
    assert "FILING_001" in [r.rule_id for r in r5.results if r.status.value == "block"]
    # state must not have advanced - the close did NOT happen
    assert r5.state.facts.get("contract_closed", False) is False

    # 6. File notification
    state = sim.step(state, Action(action_id="a5", actor_id="chair", kind="file_notification", payload={})).state
    assert state.facts["notification_filed"] is True

    # Close now succeeds
    r6 = sim.step(state, Action(action_id="a6", actor_id="chair", kind="close_contract", payload={}))
    assert r6.blocked is False
    state = r6.state
    assert state.facts["contract_closed"] is True

    # 7. Attempt to pay the full 750k -> blocked (capital maintenance: only 200k reserves)
    r7 = sim.step(state, Action(
        action_id="a7", actor_id="cfo", kind="authorise_payment", payload={"amount": 750_000},
    ))
    assert r7.blocked is True
    assert "CAPITAL_001" in [r.rule_id for r in r7.results if r.status.value == "block"]

    # 8. Authorise a payment within reserves -> succeeds
    r8 = sim.step(state, Action(
        action_id="a8", actor_id="cfo", kind="authorise_payment", payload={"amount": 150_000},
    ))
    assert r8.blocked is False
    assert r8.state.facts["payment_authorised_amount"] == 150_000


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

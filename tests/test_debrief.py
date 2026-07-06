import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constraints import ConstraintResult, ConstraintStatus, Mode
from core.debrief import build_debrief
from core.actions import Action
from knowledge.outcomes import OUTCOMES, RULE_OUTCOME_MAP
from simulate.simulation import Simulation
from llm.interface import Narrator
from scenarios.board_crisis import initial_state, build_engine, simple_transition


OUTCOME_TEXT = OUTCOMES["board_crisis_related_party_v2"]


def pass_result(rule_id, mode=Mode.GATE):
    return ConstraintResult(rule_id=rule_id, status=ConstraintStatus.PASS, mode=mode, applies=True)


def block_result(rule_id, mode=Mode.GATE):
    return ConstraintResult(rule_id=rule_id, status=ConstraintStatus.BLOCK, mode=mode, applies=True, message="blocked")


def warn_result(rule_id, mode=Mode.SYNTHESISE):
    return ConstraintResult(rule_id=rule_id, status=ConstraintStatus.WARN, mode=mode, applies=True, message="raised")


def not_applied_result(rule_id, mode=Mode.GATE):
    return ConstraintResult(rule_id=rule_id, status=ConstraintStatus.PASS, mode=mode, applies=False)


def test_clean_pass_on_first_attempt_yields_clean_tier():
    """The case the whole applies fix exists for: doing it right first time must earn credit."""
    results = [pass_result("DECLARE_177")]
    debrief = build_debrief(results, OUTCOME_TEXT, RULE_OUTCOME_MAP)

    assert debrief.compliance_demonstrated is True
    entry = debrief.compliance_evidence[0]
    assert entry.rule_id == "DECLARE_177"
    assert entry.tier == "clean"


def test_blocked_then_passed_yields_corrected_not_clean():
    results = [block_result("CONFLICT_175"), pass_result("CONFLICT_175")]
    debrief = build_debrief(results, OUTCOME_TEXT, RULE_OUTCOME_MAP)

    assert debrief.law_demonstrated is True
    entry = debrief.law_evidence[0]
    assert entry.rule_id == "CONFLICT_175"
    assert entry.tier == "corrected"


def test_synthesise_rule_only_ever_warns_yields_raised_tier():
    results = [warn_result("CARE_174"), warn_result("CARE_174")]
    debrief = build_debrief(results, OUTCOME_TEXT, RULE_OUTCOME_MAP)

    assert debrief.law_demonstrated is True
    entry = debrief.law_evidence[0]
    assert entry.rule_id == "CARE_174"
    assert entry.tier == "raised"


def test_rule_that_never_applies_produces_no_entry():
    results = [not_applied_result("INDMAJ_001")]
    debrief = build_debrief(results, OUTCOME_TEXT, RULE_OUTCOME_MAP)

    assert debrief.law_demonstrated is False
    assert debrief.compliance_demonstrated is False
    assert len(debrief.law_evidence) == 0
    assert len(debrief.compliance_evidence) == 0


def test_same_rule_firing_multiple_times_dedupes_to_one_entry():
    results = [pass_result("QUORUM_001"), pass_result("QUORUM_001"), pass_result("QUORUM_001")]
    debrief = build_debrief(results, OUTCOME_TEXT, RULE_OUTCOME_MAP)

    matching = [e for e in debrief.compliance_evidence if e.rule_id == "QUORUM_001"]
    assert len(matching) == 1


def test_unmapped_rule_id_is_ignored_without_crashing():
    results = [pass_result("SOME_UNKNOWN_RULE_999")]
    debrief = build_debrief(results, OUTCOME_TEXT, RULE_OUTCOME_MAP)

    assert debrief.law_demonstrated is False
    assert debrief.compliance_demonstrated is False


def test_empty_results_gives_both_outcomes_undemonstrated():
    debrief = build_debrief([], OUTCOME_TEXT, RULE_OUTCOME_MAP)

    assert debrief.law_demonstrated is False
    assert debrief.compliance_demonstrated is False
    assert debrief.law_outcome_text == OUTCOME_TEXT["law"]
    assert debrief.compliance_outcome_text == OUTCOME_TEXT["compliance"]


def test_full_board_crisis_run_end_to_end_produces_non_empty_debrief():
    """
    Integration check: run the full 8-step branching scenario (the same
    one exercised in tests/test_simulation.py), feed every result
    produced along the way into build_debrief, and confirm both
    outcomes end up demonstrated from a real run.
    """
    sim = Simulation(engine=build_engine(), transition=simple_transition, narrator=Narrator())
    state = initial_state()
    all_results = []

    def step(action):
        nonlocal state
        result = sim.step(state, action)
        all_results.extend(result.results)
        if not result.blocked:
            state = result.state
        return result

    step(Action(action_id="a1", actor_id="exec_director", kind="declare_interest",
                payload={"matter_id": "related_party_contract"}))
    step(Action(action_id="a2", actor_id="chair", kind="authorise_participation",
                payload={"matter_id": "related_party_contract"}))
    step(Action(action_id="a3", actor_id="exec_director", kind="vote",
                payload={"matter_id": "related_party_contract", "outcome": "approved"}))
    step(Action(action_id="a4", actor_id="chair", kind="close_contract", payload={}))
    step(Action(action_id="a5", actor_id="chair", kind="file_notification", payload={}))
    step(Action(action_id="a6", actor_id="chair", kind="close_contract", payload={}))
    step(Action(action_id="a7", actor_id="cfo", kind="authorise_payment", payload={"amount": 750_000}))
    step(Action(action_id="a8", actor_id="cfo", kind="authorise_payment", payload={"amount": 150_000}))

    debrief = build_debrief(all_results, OUTCOME_TEXT, RULE_OUTCOME_MAP)

    assert debrief.law_demonstrated is True
    assert debrief.compliance_demonstrated is True
    assert len(debrief.law_evidence) > 0
    assert len(debrief.compliance_evidence) > 0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

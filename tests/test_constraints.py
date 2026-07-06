import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import DecisionState, ActorState, DecisionMode
from core.actions import Action
from core.constraints import ConstraintStatus, Mode
from knowledge.rules import (
    QuorumRequired, DeclareInterest, ConflictOfInterestVote, ProperPurpose, DutyOfCare,
    IndependentMajorityRequired, MaterialityFilingRequired, CapitalMaintenanceCheck,
)


def base_state(**fact_overrides):
    actors = frozenset({
        ActorState(actor_id="chair", role="chair"),
        ActorState(actor_id="ned_1", role="non_executive_director"),
        ActorState(
            actor_id="exec_director",
            role="executive_director",
            conflicts=frozenset({"deal_x"}),
        ),
    })
    facts = {"directors_present": 3, "quorum_required": 3, "conflict_participation_authorised": frozenset()}
    facts.update(fact_overrides)
    return DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=actors, facts=facts,
    )


def test_quorum_passes_when_met():
    state = base_state(directors_present=3, quorum_required=3)
    action = Action(action_id="a1", actor_id="chair", kind="vote", payload={"matter_id": "deal_x"})
    result = QuorumRequired.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS
    assert result.applies is True


def test_quorum_blocks_when_not_met():
    state = base_state(directors_present=2, quorum_required=3)
    action = Action(action_id="a1", actor_id="chair", kind="vote", payload={"matter_id": "deal_x"})
    result = QuorumRequired.evaluate(state, action)
    assert result.status == ConstraintStatus.BLOCK
    assert "Quorum" in result.message


def test_declare_interest_blocks_when_conflicted_and_not_declared():
    state = base_state()
    action = Action(action_id="a1", actor_id="exec_director", kind="propose", payload={"matter_id": "deal_x"})
    result = DeclareInterest.evaluate(state, action)
    assert result.status == ConstraintStatus.BLOCK
    assert "s177" in result.message


def test_declare_interest_passes_once_declared():
    actors = frozenset({
        ActorState(
            actor_id="exec_director", role="executive_director",
            conflicts=frozenset({"deal_x"}), declarations=frozenset({"deal_x"}),
        ),
    })
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=actors,
        facts={"directors_present": 3, "quorum_required": 3, "conflict_participation_authorised": frozenset()},
    )
    action = Action(action_id="a1", actor_id="exec_director", kind="propose", payload={"matter_id": "deal_x"})
    result = DeclareInterest.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS
    assert result.applies is True


def test_conflicted_director_cannot_vote_without_authorisation():
    state = base_state()
    action = Action(action_id="a1", actor_id="exec_director", kind="vote", payload={"matter_id": "deal_x"})
    result = ConflictOfInterestVote.evaluate(state, action)
    assert result.status == ConstraintStatus.BLOCK
    assert "s175" in result.message


def test_conflicted_director_can_vote_once_board_authorises():
    """Tests the defeater: explicit board authorisation withdraws the default block."""
    state = base_state(conflict_participation_authorised=frozenset({"deal_x"}))
    action = Action(action_id="a1", actor_id="exec_director", kind="vote", payload={"matter_id": "deal_x"})
    result = ConflictOfInterestVote.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS
    assert result.applies is True  # rule applied - the defeater is what let it pass


def test_unconflicted_director_vote_unaffected_by_conflict_rule():
    state = base_state()
    action = Action(action_id="a1", actor_id="ned_1", kind="vote", payload={"matter_id": "deal_x"})
    result = ConflictOfInterestVote.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS  # rule does not even apply
    assert result.applies is False


def test_proper_purpose_blocks_when_flagged():
    state = base_state()
    action = Action(
        action_id="a1", actor_id="chair", kind="propose",
        payload={"matter_id": "deal_x", "improper_purpose_flag": True},
    )
    result = ProperPurpose.evaluate(state, action)
    assert result.status == ConstraintStatus.BLOCK
    assert "s171" in result.message


def test_duty_of_care_always_raised_never_scored():
    """SYNTHESISE-mode rule: raised for judgment, never silently passed, never a hard block."""
    state = base_state()
    action = Action(action_id="a1", actor_id="chair", kind="vote", payload={"matter_id": "deal_x"})
    result = DutyOfCare.evaluate(state, action)
    assert result.status == ConstraintStatus.WARN   # raised, not blocked
    assert result.mode == Mode.SYNTHESISE
    assert "s174" in result.message


# --- IndependentMajorityRequired: a composition gate ---

def related_party_state(present_ids):
    actors = frozenset({
        ActorState(actor_id="chair", role="chair"),
        ActorState(actor_id="ned_1", role="non_executive_director"),
        ActorState(actor_id="ned_2", role="non_executive_director"),
        ActorState(actor_id="cfo", role="cfo"),
        ActorState(actor_id="exec_director", role="executive_director",
                   conflicts=frozenset({"related_party_contract"})),
    })
    return DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=actors,
        facts={
            "present_actor_ids": frozenset(present_ids),
            "related_party_matters": frozenset({"related_party_contract"}),
        },
    )


def test_independent_majority_passes_with_full_board_present():
    state = related_party_state({"chair", "ned_1", "ned_2", "cfo", "exec_director"})
    action = Action(action_id="a1", actor_id="chair", kind="vote",
                     payload={"matter_id": "related_party_contract", "outcome": "approved"})
    result = IndependentMajorityRequired.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS  # chair+ned_1+ned_2 = 3/5, majority
    assert result.applies is True


def test_independent_majority_blocks_when_neds_have_left():
    """The genuine branching case: same board, different composition, different outcome."""
    state = related_party_state({"chair", "cfo", "exec_director"})  # NEDs absent
    action = Action(action_id="a1", actor_id="chair", kind="vote",
                     payload={"matter_id": "related_party_contract", "outcome": "approved"})
    result = IndependentMajorityRequired.evaluate(state, action)
    assert result.status == ConstraintStatus.BLOCK  # only chair independent = 1/3, not majority


def test_independent_majority_does_not_apply_to_non_related_party_matter():
    state = related_party_state({"chair", "cfo", "exec_director"})
    action = Action(action_id="a1", actor_id="chair", kind="vote",
                     payload={"matter_id": "routine_matter", "outcome": "approved"})
    result = IndependentMajorityRequired.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS  # rule doesn't even apply
    assert result.applies is False


# --- MaterialityFilingRequired: a sequence constraint ---

def test_materiality_filing_blocks_close_before_filed():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"filing_required": True, "notification_filed": False},
    )
    action = Action(action_id="a1", actor_id="chair", kind="close_contract", payload={})
    result = MaterialityFilingRequired.evaluate(state, action)
    assert result.status == ConstraintStatus.BLOCK


def test_materiality_filing_passes_once_filed():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"filing_required": True, "notification_filed": True},
    )
    action = Action(action_id="a1", actor_id="chair", kind="close_contract", payload={})
    result = MaterialityFilingRequired.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS
    assert result.applies is True


def test_materiality_filing_does_not_apply_when_not_material():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"filing_required": False, "notification_filed": False},
    )
    action = Action(action_id="a1", actor_id="chair", kind="close_contract", payload={})
    result = MaterialityFilingRequired.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS  # never triggered - not material
    assert result.applies is False


# --- CapitalMaintenanceCheck: a genuinely computed rule ---

def test_capital_maintenance_blocks_payment_exceeding_reserves():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"distributable_reserves": 200_000},
    )
    action = Action(action_id="a1", actor_id="cfo", kind="authorise_payment", payload={"amount": 750_000})
    result = CapitalMaintenanceCheck.evaluate(state, action)
    assert result.status == ConstraintStatus.BLOCK
    assert result.mode == Mode.COMPUTE


def test_capital_maintenance_passes_payment_within_reserves():
    state = DecisionState(
        scenario_id="test", mode=DecisionMode.SIMULATE, step=0, actors=frozenset(),
        facts={"distributable_reserves": 200_000},
    )
    action = Action(action_id="a1", actor_id="cfo", kind="authorise_payment", payload={"amount": 150_000})
    result = CapitalMaintenanceCheck.evaluate(state, action)
    assert result.status == ConstraintStatus.PASS
    assert result.applies is True


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

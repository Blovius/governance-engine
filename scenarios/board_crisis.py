"""
scenarios/board_crisis.py

Board Crisis: Related Party Contract - the fuller version.

Setup: A five-person board (independent Chair, two independent NEDs,
CFO, and one executive director) is voting on a GBP 750,000 related-
party contract - the counterparty is the executive director's
spouse's company. Distributable reserves are only GBP 200,000.

The scenario now branches genuinely, not just repeats the same gate:

  1. Vote attempted without declaring  -> blocked (s177 + s175 + s174 raised)
  2. Declare, authorise, but NEDs have left the room -> blocked
     (independent-majority gate fails on WHO is present)
  3. Declare, authorise, full board present -> vote succeeds
  4. Value exceeds materiality threshold -> a filing requirement is
     triggered as a CONSEQUENCE of the vote, not a precondition of it
  5. Attempt to close the contract before filing -> blocked
     (sequence constraint: an earlier action gates a later one)
  6. File notification -> now closing is permitted
  7. Attempt to pay the full contract value -> blocked
     (capital maintenance: a computed fact, not a checkbox - the
     amount genuinely exceeds distributable reserves)
  8. Authorise a payment within reserves -> succeeds

This is one scenario, one story, with consequences that follow from
earlier choices - the "richer branching structure" the demo needed,
built from three additional rules rather than more of the same gate.
"""
from core.state import DecisionState, ActorState, DecisionMode
from core.actions import Action
from knowledge.rules import ALL_RULES
from core.engine import ConstraintEngine


SCENARIO_ID = "board_crisis_related_party_v2"

ALL_ACTOR_IDS = frozenset({"chair", "ned_1", "ned_2", "cfo", "exec_director"})


def initial_state() -> DecisionState:
    actors = frozenset({
        ActorState(actor_id="chair", role="chair"),
        ActorState(actor_id="ned_1", role="non_executive_director"),
        ActorState(actor_id="ned_2", role="non_executive_director"),
        ActorState(actor_id="cfo", role="cfo"),
        ActorState(
            actor_id="exec_director",
            role="executive_director",
            conflicts=frozenset({"related_party_contract"}),
        ),
    })
    return DecisionState(
        scenario_id=SCENARIO_ID,
        mode=DecisionMode.SIMULATE,
        step=0,
        actors=actors,
        facts={
            "directors_present": 5,
            "quorum_required": 3,
            "present_actor_ids": ALL_ACTOR_IDS,
            "conflict_participation_authorised": frozenset(),
            "related_party_matters": frozenset({"related_party_contract"}),
            "contract_value": 750_000,
            "materiality_threshold": 500_000,
            "distributable_reserves": 200_000,
            "filing_required": False,
            "notification_filed": False,
            "contract_closed": False,
        },
        history=(),
    )


def build_engine() -> ConstraintEngine:
    return ConstraintEngine(ALL_RULES)


def _replace_actor(state: DecisionState, actor_id: str, **changes) -> frozenset:
    actor = state.actor(actor_id)
    new_actor = ActorState(
        actor_id=actor.actor_id,
        role=actor.role,
        conflicts=changes.get("conflicts", actor.conflicts),
        declarations=changes.get("declarations", actor.declarations),
    )
    return frozenset(new_actor if a.actor_id == actor_id else a for a in state.actors)


def simple_transition(state: DecisionState, action: Action) -> DecisionState:
    facts = dict(state.facts)

    if action.kind == "declare_interest":
        actor = state.actor(action.actor_id)
        matter_id = action.payload.get("matter_id")
        new_actors = _replace_actor(
            state, action.actor_id, declarations=actor.declarations | {matter_id}
        )
        return state.evolve(actors=new_actors, step=state.step + 1)

    if action.kind == "authorise_participation":
        matter_id = action.payload.get("matter_id")
        authorised = facts.get("conflict_participation_authorised", frozenset())
        facts["conflict_participation_authorised"] = authorised | {matter_id}
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "leave_room":
        present = facts.get("present_actor_ids", frozenset())
        facts["present_actor_ids"] = present - {action.actor_id}
        facts["directors_present"] = len(facts["present_actor_ids"])
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "enter_room":
        present = facts.get("present_actor_ids", frozenset())
        facts["present_actor_ids"] = present | {action.actor_id}
        facts["directors_present"] = len(facts["present_actor_ids"])
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "vote":
        outcome = action.payload.get("outcome", "unrecorded")
        facts["last_vote_outcome"] = outcome
        matter_id = action.payload.get("matter_id")
        if (
            outcome == "approved"
            and matter_id in facts.get("related_party_matters", frozenset())
            and facts.get("contract_value", 0) > facts.get("materiality_threshold", 0)
        ):
            facts["filing_required"] = True
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "file_notification":
        facts["notification_filed"] = True
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "close_contract":
        facts["contract_closed"] = True
        return state.evolve(facts=facts, step=state.step + 1)

    if action.kind == "authorise_payment":
        facts["payment_authorised_amount"] = action.payload.get("amount", 0)
        return state.evolve(facts=facts, step=state.step + 1)

    return state.evolve(step=state.step + 1)

"""
api.py

Minimal FastAPI wrapper around the governance engine, so it can be
hosted and demonstrated over the web rather than only run locally.

Exposes:
  GET  /api/health                    - health check + list of scenarios
  GET  /                              - the click-through demo front end
  GET  /scenario/{slug}                - fresh initial state for a scenario
  POST /scenario/{slug}/step           - take one action, get the result

This is a thin transport layer. It does not change the engine at all -
it just serialises DecisionState/Action in and StepResult out. All the
reasoning still happens in core/, knowledge/, simulate/.

Scenarios are registered in _SCENARIOS below; adding a new one is
adding one entry there, not touching any route.
"""
from dataclasses import asdict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import os

from core.state import DecisionState, ActorState, DecisionMode
from core.actions import Action
from simulate.simulation import Simulation
from llm.interface import Narrator
import scenarios.board_crisis as board_crisis
import scenarios.loan_capital_dissolution as loan_capital_dissolution


app = FastAPI(title="Governance Engine Demo API")

# Permissive CORS for a demo. Tighten this (specific origins) before any
# real client data ever touches this instance.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registry: slug -> (module, Simulation). Both scenarios share the same
# transport code below; only the module differs. Add a new scenario by
# adding one entry here.
_SCENARIOS = {
    "board-crisis": (
        board_crisis,
        Simulation(engine=board_crisis.build_engine(), transition=board_crisis.simple_transition, narrator=Narrator()),
    ),
    "loan-capital-dissolution": (
        loan_capital_dissolution,
        Simulation(
            engine=loan_capital_dissolution.build_engine(),
            transition=loan_capital_dissolution.simple_transition,
            narrator=Narrator(),
        ),
    ),
}

# Fact keys that are sets rather than scalars/lists, across all
# scenarios. JSON has no set type, so these round-trip as lists and
# must be converted back to frozenset before re-entering the engine -
# several transitions (e.g. leave_room's set-difference) require it.
_FROZENSET_FACT_KEYS = {
    "conflict_participation_authorised",
    "present_actor_ids",
    "related_party_matters",
}

_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _state_to_dict(state: DecisionState) -> Dict[str, Any]:
    return {
        "scenario_id": state.scenario_id,
        "mode": state.mode.value,
        "step": state.step,
        "actors": [
            {
                "actor_id": a.actor_id, "role": a.role,
                "conflicts": sorted(a.conflicts), "declarations": sorted(a.declarations),
            }
            for a in state.actors
        ],
        "facts": {
            k: (sorted(v) if isinstance(v, frozenset) else v)
            for k, v in state.facts.items()
        },
        "history": list(state.history),
    }


def _dict_to_state(d: Dict[str, Any]) -> DecisionState:
    actors = frozenset({
        ActorState(
            actor_id=a["actor_id"], role=a["role"],
            conflicts=frozenset(a.get("conflicts", [])),
            declarations=frozenset(a.get("declarations", [])),
        )
        for a in d["actors"]
    })
    facts = dict(d["facts"])
    for key in _FROZENSET_FACT_KEYS:
        if key in facts:
            facts[key] = frozenset(facts[key])
    return DecisionState(
        scenario_id=d["scenario_id"], mode=DecisionMode(d["mode"]), step=d["step"],
        actors=actors, facts=facts, history=tuple(d["history"]),
    )


class ActionIn(BaseModel):
    action_id: str
    actor_id: str
    kind: str
    payload: Dict[str, Any] = {}


class StepIn(BaseModel):
    state: Dict[str, Any]
    action: ActionIn


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "governance_engine v0", "scenarios": list(_SCENARIOS.keys())}


@app.get("/")
def index():
    """Serves the click-through demo front end at the site root."""
    return FileResponse(os.path.join(_static_dir, "index.html"))


@app.get("/scenario/{slug}")
def new_scenario(slug: str):
    """Returns a fresh initial state for the named scenario."""
    module, _ = _SCENARIOS[slug]
    return _state_to_dict(module.initial_state())


@app.post("/scenario/{slug}/step")
def step_scenario(slug: str, body: StepIn):
    """
    Takes the current state + one action, returns the new state,
    whether it was blocked, the rule results, and the narration.
    Stateless: the caller holds the state between calls (fine for a
    demo; a real deployment would persist state server-side by
    session id).
    """
    _, sim = _SCENARIOS[slug]
    state = _dict_to_state(body.state)
    action = Action(
        action_id=body.action.action_id, actor_id=body.action.actor_id,
        kind=body.action.kind, payload=body.action.payload,
    )
    result = sim.step(state, action)
    return {
        "state": _state_to_dict(result.state),
        "blocked": result.blocked,
        "narration": result.narration,
        "results": [
            {"rule_id": r.rule_id, "status": r.status.value, "mode": r.mode.value, "message": r.message}
            for r in result.results
        ],
    }

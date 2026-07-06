"""
core/state.py

The shared state object for both engine modes. Immutable (frozen).
Assess mode evaluates one instance. Simulation mode produces a chain
of these via evolve(), so the run history is auditable after the fact.
"""
from dataclasses import dataclass, field, replace
from typing import Any, Dict, FrozenSet
from enum import Enum


class DecisionMode(Enum):
    ASSESS = "assess"      # frozen time: evaluate one state
    SIMULATE = "simulate"  # running time: evolve a chain of states


@dataclass(frozen=True)
class ActorState:
    """An actor (role instance) participating in the decision."""
    actor_id: str
    role: str                                  # e.g. "chair", "ned", "cfo"
    conflicts: FrozenSet[str] = frozenset()    # matter_ids this actor is conflicted on
    declarations: FrozenSet[str] = frozenset() # matter_ids this actor has declared an interest in


@dataclass(frozen=True)
class DecisionState:
    """A point-in-time governance decision context."""
    scenario_id: str
    mode: DecisionMode
    step: int
    actors: FrozenSet[ActorState]
    facts: Dict[str, Any] = field(default_factory=dict)
    history: tuple = field(default_factory=tuple)  # ids of resolved actions, in order

    def actor(self, actor_id: str) -> ActorState:
        for a in self.actors:
            if a.actor_id == actor_id:
                return a
        raise KeyError(f"No actor '{actor_id}' in state")

    def evolve(self, **changes) -> "DecisionState":
        """Return a new state with changes applied. Never mutates in place."""
        return replace(self, **changes)

    def with_history(self, action_id: str) -> "DecisionState":
        return self.evolve(history=self.history + (action_id,))

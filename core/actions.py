"""
core/actions.py

What an actor attempts. Validated against constraints before it is
allowed to change state.
"""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class Action:
    action_id: str
    actor_id: str
    kind: str                                   # "vote", "declare_interest", "propose", "escalate", ...
    payload: Dict[str, Any] = field(default_factory=dict)

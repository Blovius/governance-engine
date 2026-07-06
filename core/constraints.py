"""
core/constraints.py

The heart of the engine. A constraint is a governance rule: it knows
whether it applies to a given action, whether it is satisfied, and how
to explain itself when it bites. Never imports an LLM.

Includes the defeasible-rule shape: a rule has a default conclusion,
applicability conditions, explicit exception (defeater) conditions,
and a priority for conflict resolution. Plain constraints (no
exceptions yet) are the common case for a first build; the defeasible
fields exist so exceptions can be added without restructuring later.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Tuple

from .state import DecisionState
from .actions import Action


class Mode(str, Enum):
    """Which of the three reasoning modes this rule belongs to."""
    GATE = "gate"
    COMPUTE = "compute"
    SYNTHESISE = "synthesise"


class ConstraintStatus(str, Enum):
    PASS = "pass"
    BLOCK = "block"
    WARN = "warn"          # synthesise-mode: raised for judgment, does not block


@dataclass(frozen=True)
class ConstraintResult:
    rule_id: str
    status: ConstraintStatus
    mode: Mode
    message: str = ""              # populated only when status != PASS
    remediable: bool = False
    remediation: Optional[str] = None

    @property
    def applies(self) -> bool:
        return self.status != ConstraintStatus.PASS or self.message != ""


Predicate = Callable[[DecisionState, Action], bool]


@dataclass(frozen=True)
class DefeasibleRule:
    """
    A governance rule with a default conclusion that can be defeated
    by explicit exceptions. Deterministic: given the full facts and
    priority ordering, the outcome is determinate.
    """
    rule_id: str
    mode: Mode
    scope: dict                                # {"jurisdiction": "UK", "entity": "ltd", ...}
    applies_when: Predicate                    # is this rule in play at all?
    check: Callable[[DecisionState, Action], bool]   # True = satisfied
    defeated_when: Tuple[Predicate, ...] = ()  # explicit exceptions that withdraw the default
    priority: int = 0                          # higher wins in conflict
    message: str = ""                          # explanation when it bites
    remediable: bool = False
    remediation: Optional[str] = None

    def evaluate(self, state: DecisionState, action: Action) -> ConstraintResult:
        if not self.applies_when(state, action):
            return ConstraintResult(self.rule_id, ConstraintStatus.PASS, self.mode)

        if any(defeater(state, action) for defeater in self.defeated_when):
            # An exception fired: the default conclusion is withdrawn.
            return ConstraintResult(self.rule_id, ConstraintStatus.PASS, self.mode)

        satisfied = self.check(state, action)
        if satisfied:
            return ConstraintResult(self.rule_id, ConstraintStatus.PASS, self.mode)

        status = ConstraintStatus.WARN if self.mode == Mode.SYNTHESISE else ConstraintStatus.BLOCK
        return ConstraintResult(
            self.rule_id, status, self.mode,
            message=self.message, remediable=self.remediable, remediation=self.remediation,
        )

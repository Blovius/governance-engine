"""
core/engine.py

Runs every rule against an attempted action. Reports which apply and
which are violated (BLOCK) or raised for judgment (WARN). This is
"governance runs silently underneath and surfaces only when it
constrains", expressed as code.
"""
from typing import List

from .state import DecisionState
from .actions import Action
from .constraints import DefeasibleRule, ConstraintResult, ConstraintStatus


class ConstraintEngine:
    def __init__(self, rules: List[DefeasibleRule]):
        self._rules = rules

    def evaluate(self, state: DecisionState, action: Action) -> List[ConstraintResult]:
        return [rule.evaluate(state, action) for rule in self._rules]

    def blocking(self, results: List[ConstraintResult]) -> List[ConstraintResult]:
        return [r for r in results if r.status == ConstraintStatus.BLOCK]

    def warnings(self, results: List[ConstraintResult]) -> List[ConstraintResult]:
        return [r for r in results if r.status == ConstraintStatus.WARN]

    def is_blocked(self, results: List[ConstraintResult]) -> bool:
        return any(r.status == ConstraintStatus.BLOCK for r in results)

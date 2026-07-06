"""
llm/interface.py

The ONLY module that would ever import an LLM SDK. Generates prose and
nothing else. Makes NO governance decisions - it is handed the
constraint results the symbolic engine already produced, and only
words them.

This is a stub Narrator: deterministic, template-based, no network
call. It proves the boundary works (remove it entirely and the
governance reasoning is still fully present in ConstraintResult
strings) and gives you something runnable today. Swap in a real LLM
client behind the same interface later - nothing else in the engine
changes.
"""
from typing import List
from core.state import DecisionState
from core.actions import Action
from core.constraints import ConstraintResult


class Narrator:
    def explain_block(self, blocking_results: List[ConstraintResult]) -> str:
        lines = [r.message for r in blocking_results if r.message]
        prefix = "The board cannot proceed:"
        return prefix + " " + " ".join(lines)

    def describe(self, before: DecisionState, action: Action, after: DecisionState) -> str:
        return (
            f"[step {after.step}] {action.actor_id} took action '{action.kind}'. "
            f"The board's position moves forward."
        )

    def raise_synthesis(self, warn_results: List[ConstraintResult]) -> str:
        if not warn_results:
            return ""
        lines = [r.message for r in warn_results if r.message]
        return "For the board to consider (no automatic answer): " + " ".join(lines)

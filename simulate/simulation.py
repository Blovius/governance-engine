"""
simulate/simulation.py

Running time. The step loop validates an attempted action against the
constraint engine, and either blocks it with an explanation or resolves
it into a new state. The narrator (LLM) is injected and used only to
describe what happened in prose - it makes NO governance decisions.
"""
from dataclasses import dataclass
from typing import List, Callable, Optional

from core.state import DecisionState
from core.actions import Action
from core.engine import ConstraintEngine
from core.constraints import ConstraintResult


@dataclass
class StepResult:
    state: DecisionState
    blocked: bool
    results: List[ConstraintResult]
    narration: str = ""


# transition_fn: (DecisionState, Action) -> DecisionState
TransitionFn = Callable[[DecisionState, Action], DecisionState]


class Simulation:
    def __init__(
        self,
        engine: ConstraintEngine,
        transition: TransitionFn,
        narrator: Optional["Narrator"] = None,   # llm.interface.Narrator, injected; optional
    ):
        self.engine = engine
        self.transition = transition
        self.narrator = narrator

    def step(self, state: DecisionState, action: Action) -> StepResult:
        results = self.engine.evaluate(state, action)

        if self.engine.is_blocked(results):
            narration = ""
            if self.narrator:
                narration = self.narrator.explain_block(self.engine.blocking(results))
            return StepResult(state=state, blocked=True, results=results, narration=narration)

        new_state = self.transition(state, action).with_history(action.action_id)

        narration = ""
        if self.narrator:
            narration = self.narrator.describe(state, action, new_state)

        return StepResult(state=new_state, blocked=False, results=results, narration=narration)

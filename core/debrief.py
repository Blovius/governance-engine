"""
core/debrief.py

Builds an end-of-session debrief from every ConstraintResult produced
across a run. Pure summarisation - no new governance decisions, no
state changes. Scenario-agnostic: takes the outcome text and the
rule->outcome mapping as data.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .constraints import ConstraintResult, ConstraintStatus


@dataclass
class DebriefEntry:
    rule_id: str
    label: str
    outcome: str   # "law" | "compliance"
    tier: str      # "clean" | "corrected" | "raised"


@dataclass
class Debrief:
    law_outcome_text: str
    compliance_outcome_text: str
    law_evidence: List[DebriefEntry] = field(default_factory=list)
    compliance_evidence: List[DebriefEntry] = field(default_factory=list)

    @property
    def law_demonstrated(self) -> bool:
        return len(self.law_evidence) > 0

    @property
    def compliance_demonstrated(self) -> bool:
        return len(self.compliance_evidence) > 0


def build_debrief(
    all_results: List[ConstraintResult],
    outcome_text: Dict[str, str],
    rule_outcome_map: Dict[str, Tuple[str, str]],
) -> Debrief:
    """
    all_results: every ConstraintResult produced across every step of
    the session, in order (including PASS results - they are needed
    to detect the 'clean' tier). Results where applies=False are
    ignored entirely.
    """
    debrief = Debrief(
        law_outcome_text=outcome_text["law"],
        compliance_outcome_text=outcome_text["compliance"],
    )

    best_tier: Dict[str, str] = {}  # rule_id -> best tier seen so far

    def tier_of(result: ConstraintResult) -> str:
        if result.status == ConstraintStatus.BLOCK:
            return "corrected"   # will read as "corrected" once resolved; if never
                                  # resolved it simply won't appear (student didn't
                                  # complete the run cleanly - nothing to credit yet)
        if result.status == ConstraintStatus.WARN:
            return "raised"
        return "clean"

    for result in all_results:
        if not result.applies:
            continue
        if result.rule_id not in rule_outcome_map:
            continue

        new_tier = tier_of(result)
        prior = best_tier.get(result.rule_id)

        if prior is None:
            best_tier[result.rule_id] = new_tier
        elif prior == "clean" and new_tier != "clean":
            # was clean, now blocking/warning on a later attempt - not clean anymore
            best_tier[result.rule_id] = new_tier
        elif prior == "corrected" and new_tier == "clean":
            # was blocked earlier, now passes - keep "corrected", not "clean"
            best_tier[result.rule_id] = "corrected"
        # else: keep prior (e.g. "raised" stays "raised" every time it recurs)

    for rule_id, tier in best_tier.items():
        outcome, label = rule_outcome_map[rule_id]
        entry = DebriefEntry(rule_id=rule_id, label=label, outcome=outcome, tier=tier)
        if outcome == "law":
            debrief.law_evidence.append(entry)
        else:
            debrief.compliance_evidence.append(entry)

    return debrief

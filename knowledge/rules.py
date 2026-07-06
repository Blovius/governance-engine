"""
knowledge/rules.py

The constraint library for the board-crisis scenario. Drawn from the
Companies Act 2006 general duties (Part 10, Chapter 2), standard
governance process (quorum, board composition), and capital
maintenance. Each rule is a few lines: a predicate for when it
applies, a check for satisfaction, and a plain-language explanation
for when it bites.

Eight rules spanning all three reasoning modes:
  GATE       - QuorumRequired, DeclareInterest, ConflictOfInterestVote,
               ProperPurpose, IndependentMajorityRequired, MaterialityFilingRequired
  COMPUTE    - CapitalMaintenanceCheck (a genuinely calculated lawfulness fact)
  SYNTHESISE - DutyOfCare (raised for judgment, never scored, never blocks)

Two of the gates are point constraints (fire on a single action).
IndependentMajorityRequired is a composition constraint (depends on
WHO is present, not just what one actor did). MaterialityFilingRequired
is a sequence constraint (fires on a LATER action, conditioned on an
EARLIER one) - the process primitive from the design, in its simplest
form.

This is illustrative domain content, not exhaustive.
"""
from core.constraints import DefeasibleRule, Mode
from core.state import DecisionState
from core.actions import Action


def _is_vote(state: DecisionState, action: Action) -> bool:
    return action.kind == "vote"


def _is_exercise_of_power(state: DecisionState, action: Action) -> bool:
    return action.kind in ("vote", "propose", "approve")


# --- 1. Quorum required (standard governance process; gate) ---

def _quorum_check(state: DecisionState, action: Action) -> bool:
    present = state.facts.get("directors_present", 0)
    required = state.facts.get("quorum_required", 0)
    return present >= required


QuorumRequired = DefeasibleRule(
    rule_id="QUORUM_001",
    mode=Mode.GATE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_is_vote,
    check=_quorum_check,
    priority=10,
    message="Quorum not met: insufficient directors present for a valid vote.",
    remediable=True,
    remediation="Adjourn and reconvene once quorum is achieved.",
)


# --- 2. Conflict must be declared before acting (CA2006 s177; gate) ---

def _conflict_applies(state: DecisionState, action: Action) -> bool:
    if not _is_exercise_of_power(state, action):
        return False
    actor = state.actor(action.actor_id)
    matter_id = action.payload.get("matter_id")
    return matter_id in actor.conflicts


def _conflict_declared_check(state: DecisionState, action: Action) -> bool:
    actor = state.actor(action.actor_id)
    matter_id = action.payload.get("matter_id")
    return matter_id in actor.declarations


DeclareInterest = DefeasibleRule(
    rule_id="DECLARE_177",
    mode=Mode.GATE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_conflict_applies,
    check=_conflict_declared_check,
    priority=20,
    message="s177: director has an interest in this matter and has not declared it before acting.",
    remediable=True,
    remediation="Director must declare the nature and extent of the interest before the transaction proceeds.",
)


# --- 3. Conflicted director should not vote on the matter (s175; gate) ---
# Defeasible: the default is "conflicted directors cannot vote", but the
# board's articles may permit it once the conflict is declared and the
# board authorises participation. That authorisation is the defeater.

def _conflict_vote_applies(state: DecisionState, action: Action) -> bool:
    if action.kind != "vote":
        return False
    actor = state.actor(action.actor_id)
    matter_id = action.payload.get("matter_id")
    return matter_id in actor.conflicts


def _board_authorised_participation(state: DecisionState, action: Action) -> bool:
    matter_id = action.payload.get("matter_id")
    authorised = state.facts.get("conflict_participation_authorised", frozenset())
    return matter_id in authorised


ConflictOfInterestVote = DefeasibleRule(
    rule_id="CONFLICT_175",
    mode=Mode.GATE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_conflict_vote_applies,
    check=lambda state, action: False,   # default: conflicted director may not vote
    defeated_when=(_board_authorised_participation,),   # unless the board has authorised it
    priority=15,
    message="s175: conflicted director must not vote on this matter without board authorisation.",
    remediable=True,
    remediation="Either the conflicted director withdraws from the vote, or the board formally authorises participation.",
)


# --- 4. Proper purpose (s171; gate) ---
# Illustrative simplification: checks a flag the scenario sets when an
# action is being taken for a purpose outside the powers conferred.

def _proper_purpose_check(state: DecisionState, action: Action) -> bool:
    return not action.payload.get("improper_purpose_flag", False)


ProperPurpose = DefeasibleRule(
    rule_id="PURPOSE_171",
    mode=Mode.GATE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_is_exercise_of_power,
    check=_proper_purpose_check,
    priority=15,
    message="s171: this exercise of power appears to be for a purpose outside the constitution.",
    remediable=False,
)


# --- 5. Duty of care, skill and diligence (s174; SYNTHESISE, not gated) ---
# The engine raises this duty whenever a substantive board decision is
# taken. It never scores it. The narrator surfaces the duty as a
# prompt for reasoning; the human addresses it.

def _duty_of_care_applies(state: DecisionState, action: Action) -> bool:
    return action.kind in ("vote", "propose", "approve")


DutyOfCare = DefeasibleRule(
    rule_id="CARE_174",
    mode=Mode.SYNTHESISE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_duty_of_care_applies,
    check=lambda state, action: False,   # SYNTHESISE rules always raise; never silently pass
    priority=5,
    message="s174: has this decision been taken with the care, skill and diligence a reasonably diligent director would exercise? Consider the general knowledge, skill and experience the director has and reasonably ought to have.",
)


# --- 6. Independent majority for related-party matters (gate) ---
# A composition check, not a point check: it looks at WHO is in the
# room, not just what one actor did. Uses `present_actor_ids` (who is
# actually present) rather than the bare `directors_present` count, so
# it can fail differently depending on which directors are present -
# this is what makes the scenario genuinely branch rather than just
# gate the same actor twice.

INDEPENDENT_ROLES = {"chair", "non_executive_director"}


def _independent_majority_applies(state: DecisionState, action: Action) -> bool:
    if action.kind != "vote":
        return False
    matter_id = action.payload.get("matter_id")
    related_party_matters = state.facts.get("related_party_matters", frozenset())
    return matter_id in related_party_matters


def _independent_majority_check(state: DecisionState, action: Action) -> bool:
    present_ids = state.facts.get("present_actor_ids", frozenset())
    present_actors = [a for a in state.actors if a.actor_id in present_ids]
    if not present_actors:
        return False
    independent_count = sum(1 for a in present_actors if a.role in INDEPENDENT_ROLES)
    return independent_count > len(present_actors) / 2


IndependentMajorityRequired = DefeasibleRule(
    rule_id="INDMAJ_001",
    mode=Mode.GATE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_independent_majority_applies,
    check=_independent_majority_check,
    priority=18,
    message="A related-party matter requires a majority of independent directors (chair or NED) among those present. The current composition does not meet that bar.",
    remediable=True,
    remediation="Ensure enough independent non-executive directors are present before the vote proceeds, or adjourn.",
)


# --- 7. Materiality-triggered filing requirement (gate) ---
# A SEQUENCE constraint, not a point constraint: it doesn't fire on the
# vote itself, it fires on a LATER action (closing the contract) and
# depends on what an even earlier action (the vote) established. This
# is the process/sequence primitive from the design: track progress,
# flag a step attempted out of order.

def _filing_required_applies(state: DecisionState, action: Action) -> bool:
    return action.kind == "close_contract" and state.facts.get("filing_required", False)


def _filing_done_check(state: DecisionState, action: Action) -> bool:
    return state.facts.get("notification_filed", False)


MaterialityFilingRequired = DefeasibleRule(
    rule_id="FILING_001",
    mode=Mode.GATE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_filing_required_applies,
    check=_filing_done_check,
    priority=12,
    message="This contract exceeds the materiality threshold and requires notification to be filed before it can be closed.",
    remediable=True,
    remediation="File the notification, then attempt to close the contract again.",
)


# --- 8. Capital maintenance: lawful distribution (compute mode) ---
# Genuinely computable, not just a checkbox: the rule calculates
# whether the payment is covered by distributable reserves. This is
# the finance-compute layer from the reasoning-engine design, in its
# simplest possible form - a real number compared to a real number,
# never left to an LLM to estimate.

def _capital_maintenance_applies(state: DecisionState, action: Action) -> bool:
    return action.kind == "authorise_payment"


def _capital_maintenance_check(state: DecisionState, action: Action) -> bool:
    amount = action.payload.get("amount", 0)
    reserves = state.facts.get("distributable_reserves", 0)
    return amount <= reserves


CapitalMaintenanceCheck = DefeasibleRule(
    rule_id="CAPITAL_001",
    mode=Mode.COMPUTE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_capital_maintenance_applies,
    check=_capital_maintenance_check,
    priority=25,   # highest priority: a computed lawfulness fact should not be overridden
    message="This payment exceeds distributable reserves and would be an unlawful distribution under the capital maintenance rules.",
    remediable=True,
    remediation="Reduce the payment to within distributable reserves, or increase reserves before authorising.",
)


ALL_RULES = [
    QuorumRequired,
    DeclareInterest,
    ConflictOfInterestVote,
    ProperPurpose,
    DutyOfCare,
    IndependentMajorityRequired,
    MaterialityFilingRequired,
    CapitalMaintenanceCheck,
]


# --- 9. Creditor duty consideration (SYNTHESISE) ---
# The classic common-law creditor duty (West Mercia Safetywear v Dodd),
# confirmed and clarified by the Supreme Court in BTI 2014 LLC v Sequana
# SE [2022] UKSC 25: once a company is insolvent, or bordering on
# insolvency, or insolvent liquidation is probable, directors must have
# regard to creditors' interests. This is judgment, not a checkable
# rule - the engine raises it whenever solvency has failed, and does
# not decide whether the board weighed it correctly. `solvent` is a
# COMPUTED fact (see scenarios/loan_capital_dissolution.py), not
# something this rule calculates itself - this rule only reads it.

def _creditor_duty_applies(state: DecisionState, action: Action) -> bool:
    if action.kind not in ("vote", "propose", "approve", "incur_new_credit"):
        return False
    return state.facts.get("solvent", True) is False


CreditorDutyConsideration = DefeasibleRule(
    rule_id="CREDITOR_DUTY_SEQUANA",
    mode=Mode.SYNTHESISE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_creditor_duty_applies,
    check=lambda state, action: False,   # SYNTHESISE: always raised, never scored
    priority=6,
    message="BTI 2014 LLC v Sequana [2022] UKSC 25: the company is insolvent or bordering on it. "
            "Directors must now have regard to creditors' interests, not only members'. "
            "Has this decision been weighed against that shift?",
)


# --- 10. Wrongful trading (GATE, with a defeater) ---
# Insolvency Act 1986 s.214. Default: a director may not incur further
# credit once there is no reasonable prospect of avoiding insolvent
# liquidation. Defeated if the director has taken the steps s.214(3)
# treats as mitigating - here, modelled simply as having sought
# professional advice before continuing. This is deliberately a
# simplification of a fact-heavy statutory test, for teaching purposes.

def _wrongful_trading_applies(state: DecisionState, action: Action) -> bool:
    if action.kind != "incur_new_credit":
        return False
    return (
        state.facts.get("solvent", True) is False
        and state.facts.get("no_reasonable_prospect", False) is True
    )


def _advice_sought_defeater(state: DecisionState, action: Action) -> bool:
    return state.facts.get("advice_sought", False) is True


WrongfulTradingGate = DefeasibleRule(
    rule_id="WRONGFUL_TRADING_S214",
    mode=Mode.GATE,
    scope={"jurisdiction": "UK", "entity": "ltd"},
    applies_when=_wrongful_trading_applies,
    check=lambda state, action: False,   # default: blocked
    defeated_when=(_advice_sought_defeater,),
    priority=22,
    message="s.214 Insolvency Act 1986: there is no reasonable prospect of avoiding insolvent "
            "liquidation. Incurring further credit now, without having taken steps to minimise "
            "loss to creditors, risks personal liability for wrongful trading.",
    remediable=True,
    remediation="Seek professional insolvency advice before any further credit is incurred.",
)


ALL_RULES = ALL_RULES + [
    CreditorDutyConsideration,
    WrongfulTradingGate,
]

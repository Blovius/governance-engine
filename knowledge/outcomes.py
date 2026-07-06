"""
knowledge/outcomes.py

Maps each rule to the stated module learning outcome it evidences,
per scenario. Outcome text is verbatim from
Organisational_Law_and_Compliance_Teaching_Sequence.xlsx and must not
be paraphrased - it is what the lecturer grades against.
"""

OUTCOMES = {
    "board_crisis_related_party_v2": {
        "law": "Apply fiduciary duties and s.172 reasoning to complex real-world problems.",
        "compliance": "Translate legal duties into operational tools to support compliant governance.",
    },
    "loan_capital_dissolution_v1": {
        "law": "Apply insolvency and loan capital rules to a realistic financial crisis.",
        "compliance": "Operationalise legal requirements for loan capital into a workable process.",
    },
}

# rule_id -> ("law" | "compliance", short human-readable label for the debrief)
RULE_OUTCOME_MAP = {
    # board_crisis_related_party_v2
    "QUORUM_001": ("compliance", "Recognised the quorum requirement for a valid vote"),
    "DECLARE_177": ("compliance", "Applied the s177 duty to declare an interest before acting"),
    "CONFLICT_175": ("law", "Reasoned through the s175 conflicted-vote restriction and its board-authorisation exception"),
    "PURPOSE_171": ("law", "Identified an exercise of power outside the proper purpose under s171"),
    "CARE_174": ("law", "Engaged with the s174 duty of care as a live consideration"),
    "INDMAJ_001": ("law", "Reasoned about board composition and independence for a related-party decision"),
    "FILING_001": ("compliance", "Sequenced a regulatory filing correctly relative to closing the contract"),
    "CAPITAL_001": ("compliance", "Applied the capital maintenance rule to a proposed payment"),
    # loan_capital_dissolution_v1
    "CREDITOR_DUTY_SEQUANA": ("law", "Reasoned through the Sequana creditor-duty shift as solvency deteriorated"),
    "WRONGFUL_TRADING_S214": ("law", "Applied s214 wrongful trading exposure to a live credit decision"),
}

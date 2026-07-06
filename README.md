# Governance Engine — Working Build

A working symbolic governance engine: state, actions, defeasible constraints,
a simulation tick loop, and a stub narrator. No LLM call anywhere in the
reasoning path — the engine is fully deterministic and testable offline.

## Run it

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v      # 23 tests, all pass, no network
python3 demo.py                   # narrated three-part walkthrough
uvicorn api:app --reload          # serve it over HTTP at localhost:8000
```

See `HOSTING.md` for deploying this to a public URL for a live demo.

## What's here

- `core/` — state, actions, the defeasible-rule shape, the constraint engine.
  Pure Python. No LLM import anywhere.
- `knowledge/rules.py` — **ten rules spanning all three reasoning modes**,
  shared across both scenarios (a rule simply doesn't fire if the facts it
  needs aren't present):
  - **GATE**: quorum, s177 (declare interest), s175 (conflicted vote — with
    a worked defeater), s171 (proper purpose), independent-majority-for-
    related-party (a *composition* gate), materiality-triggered filing (a
    *sequence* gate), wrongful trading under s.214 Insolvency Act 1986 (a
    gate with a professional-advice defeater)
  - **COMPUTE**: capital maintenance (payment vs. distributable reserves)
  - **SYNTHESISE**: s174 duty of care; the creditor-duty consideration from
    *BTI 2014 LLC v Sequana* [2022] UKSC 25 — raised on every substantive
    decision once the company is insolvent, never scored
- `scenarios/board_crisis.py` — **Week 3, Board of Directors.** A related-
  party contract vote. Frozen-in-a-meeting story: composition, conduct,
  consequence.
- `scenarios/loan_capital_dissolution.py` — **Week 9, Loan Capital and
  Dissolution.** A genuinely RUNNING-TIME story: solvency is a *computed*
  fact (assets vs. liabilities), recalculated after every trading update,
  not asserted by any action. As it deteriorates, the creditor-duty
  consideration starts firing automatically on every decision, and past a
  further threshold, raising new credit is blocked under s.214 unless the
  board has first sought professional advice.
- `simulate/simulation.py` — the tick loop, scenario-agnostic.
- `llm/interface.py` — the ONLY module that would ever import an LLM SDK.
  Currently a deterministic stub (no network call).
- `api.py` — FastAPI wrapper. Scenarios are registered in one dict
  (`_SCENARIOS`); routes are generic (`/scenario/{slug}`), so adding a
  third scenario is one registry entry, not new routes.
- `static/index.html` — the click-through demo front end, styled as a
  numbered minute book. Now has a **scenario switcher** (two tabs) so both
  weeks are demonstrable from the same page without a redeploy.
- `Dockerfile`, `HOSTING.md` — deploy to Render for a live demo URL.
- `tests/` — **31 tests**: one per rule (including both defeaters), plus
  end-to-end tests for each scenario's full branching narrative, and a
  test confirming solvency is genuinely computed rather than asserted.
- `demo.py` — narrated three-part console transcript of Week 3.

## The story each scenario tells

**Week 3** is about composition and process within a single meeting: the
same conflict, correctly declared and authorised, still gets blocked if
the wrong people are in the room — governance checking who's present, not
just what one actor did.

**Week 9** is about a threshold that moves on its own. Nobody decides the
company becomes insolvent — the engine computes it from the numbers after
each trading update, and the creditor-duty consideration and the s.214
gate both key off that computed fact automatically. This is the running-
time mode doing something the frozen-meeting scenario structurally cannot:
a duty that changes mid-simulation because the facts changed, not because
anyone voted on it.

## The discipline this preserves

No LLM import anywhere except `llm/interface.py`. Every constraint and
transition runs in a unit test with no network call. Solvency, the one
genuinely quantitative fact in either scenario, is computed once in the
transition function and read by rules — never recomputed or asserted
by an LLM.

## Extending it

To add a rule: write a new `DefeasibleRule` in `knowledge/rules.py` and
add it to `ALL_RULES` — it's shared across all scenarios and only fires
where its `applies_when` predicate matches. To add a scenario: copy the
shape of either scenario file, then add one entry to `_SCENARIOS` in
`api.py`. To connect a real LLM: replace the body of `Narrator`'s methods
in `llm/interface.py`; the rest of the engine is untouched.


## The discipline this preserves

No LLM import anywhere except `llm/interface.py`. Every constraint and
transition runs in a unit test with no network call. If you ever add a
real LLM behind `Narrator`, the test suite should still pass unmodified —
if it doesn't, the LLM has leaked into a decision it shouldn't be making.

## Extending it

To add a rule: write a new `DefeasibleRule` in `knowledge/rules.py`
(predicate for when it applies, a check, optional defeaters, priority,
message) and add it to `ALL_RULES`. To add a scenario: copy the shape of
`scenarios/board_crisis.py`. To connect a real LLM: replace the body of
`Narrator`'s methods in `llm/interface.py`; the rest of the engine is
untouched.


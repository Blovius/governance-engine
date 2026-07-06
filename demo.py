"""
demo.py

Runs the full board-crisis scenario end-to-end, including the genuine
branch point (what happens if the NEDs leave the room) and the
consequence chain (vote -> filing requirement -> close -> payment).

Run: python3 demo.py
"""
from core.actions import Action
from simulate.simulation import Simulation
from llm.interface import Narrator
from scenarios.board_crisis import initial_state, build_engine, simple_transition


def show(label, result):
    print(f"\n--- {label} ---")
    print(f"Blocked: {result.blocked}")
    if result.narration:
        print(f"Narration: {result.narration}")
    for r in result.results:
        if r.status.value != "pass":
            print(f"  [{r.mode.value.upper()}] {r.rule_id}: {r.status.value} - {r.message}")


def make_sim():
    return Simulation(engine=build_engine(), transition=simple_transition, narrator=Narrator())


def part_one_the_wrong_way():
    print("\n" + "#" * 70)
    print("# PART ONE: Attempting the vote the wrong way")
    print("#" * 70)
    sim = make_sim()
    state = initial_state()

    print(
        "\nSetup: 5-person board. exec_director's spouse's company is the\n"
        "counterparty on a GBP 750,000 contract. Distributable reserves\n"
        "are only GBP 200,000. The conflict has not yet been declared."
    )

    result = sim.step(state, Action(
        action_id="a1", actor_id="exec_director", kind="vote",
        payload={"matter_id": "related_party_contract", "outcome": "approved"},
    ))
    show("exec_director tries to vote immediately", result)


def part_two_the_composition_branch():
    print("\n" + "#" * 70)
    print("# PART TWO: Declared and authorised - but who's in the room matters")
    print("#" * 70)
    sim = make_sim()
    state = initial_state()

    state = sim.step(state, Action(
        action_id="a1", actor_id="exec_director", kind="declare_interest",
        payload={"matter_id": "related_party_contract"},
    )).state
    state = sim.step(state, Action(
        action_id="a2", actor_id="chair", kind="authorise_participation",
        payload={"matter_id": "related_party_contract"},
    )).state
    print("\nexec_director has declared. The board has authorised participation.")
    print("Now both NEDs step out of the room before the vote...")

    state = sim.step(state, Action(action_id="a3", actor_id="ned_1", kind="leave_room")).state
    state = sim.step(state, Action(action_id="a4", actor_id="ned_2", kind="leave_room")).state

    result = sim.step(state, Action(
        action_id="a5", actor_id="exec_director", kind="vote",
        payload={"matter_id": "related_party_contract", "outcome": "approved"},
    ))
    show("Vote attempted with only chair, cfo, exec_director present", result)
    print(
        "\nSame conflict, properly declared and authorised - but the engine\n"
        "still blocks it, because a related-party matter requires an\n"
        "independent majority AMONG THOSE PRESENT, and with the NEDs gone\n"
        "only the chair is independent: 1 of 3."
    )


def part_three_the_full_journey():
    print("\n" + "#" * 70)
    print("# PART THREE: Done properly, through to consequence")
    print("#" * 70)
    sim = make_sim()
    state = initial_state()

    state = sim.step(state, Action(
        action_id="a1", actor_id="exec_director", kind="declare_interest",
        payload={"matter_id": "related_party_contract"},
    )).state
    state = sim.step(state, Action(
        action_id="a2", actor_id="chair", kind="authorise_participation",
        payload={"matter_id": "related_party_contract"},
    )).state

    result = sim.step(state, Action(
        action_id="a3", actor_id="exec_director", kind="vote",
        payload={"matter_id": "related_party_contract", "outcome": "approved"},
    ))
    show("Full board present: declared, authorised, vote proceeds", result)
    state = result.state
    print(f"\n  -> Consequence: filing_required is now {state.facts['filing_required']}"
          f" (contract value GBP {state.facts['contract_value']:,} exceeds the"
          f" GBP {state.facts['materiality_threshold']:,} threshold)")

    result = sim.step(state, Action(action_id="a4", actor_id="chair", kind="close_contract", payload={}))
    show("Attempt to close the contract before filing", result)
    state = result.state

    result = sim.step(state, Action(action_id="a5", actor_id="chair", kind="file_notification", payload={}))
    show("File the notification", result)
    state = result.state

    result = sim.step(state, Action(action_id="a6", actor_id="chair", kind="close_contract", payload={}))
    show("Close the contract, now that filing is done", result)
    state = result.state

    result = sim.step(state, Action(
        action_id="a7", actor_id="cfo", kind="authorise_payment", payload={"amount": 750_000},
    ))
    show("Attempt to authorise the full GBP 750,000 payment", result)

    result = sim.step(state, Action(
        action_id="a8", actor_id="cfo", kind="authorise_payment", payload={"amount": 150_000},
    ))
    show("Authorise GBP 150,000 instead - within distributable reserves", result)
    state = result.state

    print("\n" + "=" * 70)
    print(f"Final history: {state.history}")
    print(f"Contract closed: {state.facts.get('contract_closed')}")
    print(f"Payment authorised: GBP {state.facts.get('payment_authorised_amount'):,}")
    print("=" * 70)


def main():
    part_one_the_wrong_way()
    part_two_the_composition_branch()
    part_three_the_full_journey()


if __name__ == "__main__":
    main()

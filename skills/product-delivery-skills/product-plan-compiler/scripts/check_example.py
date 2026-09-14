#!/usr/bin/env python3
"""Exhaustively check the bundled order-lifecycle abstraction.

This is a portability fallback for the README example. It does not replace
running the TLA+ model with TLC; it mirrors the same finite transition system
so the example's expected counterexample and repaired result are reproducible.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class State:
    status: str
    paid: bool
    has_shipment: bool


Transition = tuple[str, State]


def invariant(state: State) -> bool:
    return not (state.status == "Cancelled" and state.has_shipment)


def common_transitions(state: State) -> list[Transition]:
    out: list[Transition] = []
    if state.status == "Created":
        out.append(("Pay", State("Paid", True, state.has_shipment)))
    if state.status == "Paid" and state.paid:
        out.append(("CreateShipment", State("Shipped", state.paid, True)))
    if state.status == "Shipped" and state.has_shipment:
        out.append(("Deliver", State("Delivered", state.paid, state.has_shipment)))
    return out


def buggy_transitions(state: State) -> Iterable[Transition]:
    out = common_transitions(state)
    if state.status in {"Created", "Paid", "Shipped"}:
        out.append(("CancelBad", State("Cancelled", state.paid, state.has_shipment)))
    return out


def fixed_transitions(state: State) -> Iterable[Transition]:
    out = common_transitions(state)
    if state.status in {"Created", "Paid"} and not state.has_shipment:
        out.append(("Cancel", State("Cancelled", state.paid, state.has_shipment)))
    return out


def explore(step: Callable[[State], Iterable[Transition]]) -> tuple[set[State], list[tuple[str, State]] | None]:
    initial = State("Created", False, False)
    queue = deque([(initial, [])])
    seen = {initial}
    while queue:
        state, trace = queue.popleft()
        if not invariant(state):
            return seen, trace
        for action, nxt in step(state):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, trace + [(action, nxt)]))
    return seen, None


def format_trace(trace: list[tuple[str, State]] | None) -> str:
    if trace is None:
        return "none"
    lines = []
    for index, (action, state) in enumerate(trace, start=1):
        lines.append(
            f"  {index}. {action}: status={state.status}, "
            f"paid={state.paid}, hasShipment={state.has_shipment}"
        )
    return "\n".join(lines)


def main() -> int:
    buggy_states, buggy_trace = explore(buggy_transitions)
    fixed_states, fixed_trace = explore(fixed_transitions)

    print("Buggy model")
    print(f"  reachable states before/including first violation: {len(buggy_states)}")
    print("  shortest invariant-violating trace:")
    print(format_trace(buggy_trace))
    print()
    print("Fixed model")
    print(f"  reachable states: {len(fixed_states)}")
    print(f"  invariant violation: {'yes' if fixed_trace else 'no'}")

    if buggy_trace is None:
        raise SystemExit("Expected buggy model to violate the invariant")
    if fixed_trace is not None:
        raise SystemExit("Expected fixed model to satisfy the invariant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

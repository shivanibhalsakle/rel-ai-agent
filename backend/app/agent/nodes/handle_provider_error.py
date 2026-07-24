"""
handle_provider_error node (design doc Step 4) — the central error node
every tool node's conditional edge routes to on failure. Decides retry vs.
user-facing failure message based on retry_counts and whether the error was
marked retryable (design doc: "one automatic retry per tool node on
transient failure... permanent failures... do not retry").

Tool nodes report failures by appending a ProviderError to state["errors"]
(see geocode_location.py / search_places.py's `_error` helpers) — this node
reads the most recent one and decides what happens next; it never calls a
provider itself.
"""
from typing import Literal

from app.agent.state import AgentState

MAX_RETRIES_PER_NODE = 1
# ^ design doc: "one automatic retry per tool node on transient failure"


def handle_provider_error(state: AgentState) -> dict:
    """If the latest error is retryable and hasn't been retried yet for its
    node, removes it from `errors` (rather than leaving it as a standing
    failure) and bumps retry_counts — the graph routes back to the failed
    node next (see route_after_error). Otherwise leaves `errors` untouched
    so the API layer can surface an honest "X unavailable" message (design
    doc: "the state's errors list is always surfaced to the frontend")."""
    errors = list(state.get("errors", []))
    if not errors:
        return {}

    latest = errors[-1]
    retry_counts = dict(state.get("retry_counts", {}))
    attempts_so_far = retry_counts.get(latest["node"], 0)

    if latest["retryable"] and attempts_so_far < MAX_RETRIES_PER_NODE:
        retry_counts[latest["node"]] = attempts_so_far + 1
        return {"errors": errors[:-1], "retry_counts": retry_counts}

    return {}


def route_after_error(state: AgentState, failed_node: str) -> Literal["retry", "degrade"]:
    """Conditional-edge routing function for M4.9, run right after
    handle_provider_error. `failed_node` is bound per-edge (the same
    handle_provider_error node serves every tool node, so each wiring site
    tells this function which node it's guarding).

    Distinguishes "just decided to retry" from "already gave up" by
    whether the failed node's error is still the latest entry in `errors`:
    handle_provider_error removes it when retrying, leaves it in place
    when degrading. No separate transient flag needed — one field, one
    source of truth."""
    errors = state.get("errors", [])
    if errors and errors[-1]["node"] == failed_node:
        return "degrade"
    return "retry"

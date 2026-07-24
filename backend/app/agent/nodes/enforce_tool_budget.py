"""
enforce_tool_budget (design doc Step 4, "graph guard") — checked before
every tool node. Split into a node (check_tool_budget, increments the
count) and a routing predicate (is_within_budget) rather than one function,
because in LangGraph a "guard" is naturally a conditional edge: a node runs
and returns a state update, then a separate routing function decides where
to go next based on the new state. Wiring check_tool_budget immediately
before every tool node in agent/graph.py (M4.9) means every tool call gets
counted in exactly one place, instead of retrofitting a counter increment
into geocode_location/search_places/fetch_place_details individually.
"""
from app.agent.state import AgentState


def check_tool_budget(state: AgentState) -> dict:
    """The actual graph node. Increments unconditionally — the routing
    decision (proceed vs. short-circuit) happens separately in
    is_within_budget, run right after this node by the graph's conditional
    edge."""
    return {"tool_call_count": state["tool_call_count"] + 1}


def is_within_budget(state: AgentState) -> bool:
    """Routing predicate used in a conditional edge immediately after
    check_tool_budget. True -> proceed to the intended tool node. False ->
    the graph should route to a "narrow your request" response instead
    (design doc: "short-circuits to a 'narrow your request' response
    instead of looping")."""
    return state["tool_call_count"] <= state["tool_call_budget"]

"""
request_user_approval node (design doc Step 4 node table: "Used for
calendar-event creation only; graph pauses until explicit confirm/reject").

Pure interrupt -- mirrors ask_user's split into a side-effecting node
(generate_clarifying_question / here, prepare_calendar_proposal) and a
pure-interrupt node (ask_user / here, request_user_approval). See
ask_user.py's docstring for why: LangGraph re-runs a node's body from the
top on every resume, so a node with real work before its interrupt() call
would repeat that work each time. This node has nothing before interrupt()
-- prepare_calendar_proposal already built and stored the payload in
pending_approval on the turn before this node first ran -- so a resume
just re-reads that same already-computed payload and re-calls interrupt(),
which is exactly what LangGraph expects.

This is the design doc's named structural safeguard for calendar writes
("approval is a graph interrupt, not a prompt instruction... must be
structurally impossible" to bypass): create_calendar_event (M8.6) is only
reachable via the one conditional edge that reads approval_decision
(_route_after_approval, agent/graph.py) -- and this is the ONLY node in
the entire graph that ever sets approval_decision. M8.8 tests that
invariant directly.
"""
from langgraph.types import interrupt

from app.agent.state import AgentState


def request_user_approval(state: AgentState) -> dict:
    approval = state["pending_approval"]
    decision = interrupt({"kind": approval["kind"], "payload": approval["payload"]})
    return {"approval_decision": bool(decision)}

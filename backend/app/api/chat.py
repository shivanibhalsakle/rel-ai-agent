"""
POST /v1/chat and POST /v1/chat/{sessionId}/resume -- the HTTP surface over
the M4 LangGraph agent (app/agent/graph.py).

Session/thread model: LangGraph's checkpointer keys state by a
`thread_id` in the invoke config. We use our own `session_id` as that
thread_id directly, so "does this session exist" and "is it paused" are
both just questions we ask the checkpointer via graph.get_state(), not
something we track ourselves.

/v1/chat auto-detects whether the session is currently paused on an
ask_user() interrupt and, if so, treats the incoming message as the
answer (Command(resume=...)) rather than requiring the client to know to
call the separate /resume endpoint. This matches how a real chat UI
behaves -- the user just keeps typing in one box. /resume exists as an
explicit alternative for a client that already knows it's answering a
specific question (and wants a 409 if that assumption turns out to be
wrong, rather than silent reinterpretation).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agent.graph import get_graph
from app.agent.state import new_agent_state
from app.auth.dependencies import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse, Recommendation, ResumeRequest

router = APIRouter()

# Per-turn fields reset before invoking an EXISTING, not-currently-paused
# session with a new message. user_id, session_id, and tool_call_budget are
# deliberately excluded (they don't change turn to turn); messages is
# excluded too (add_messages appends rather than replacing). Anything left
# out of this dict just keeps its prior value, which is what we want for
# the identity fields but would be wrong for stale results like
# scored_results or explanations from a previous, unrelated question.
_PER_TURN_RESET_FIELDS = (
    "intent",
    "extracted_preferences",
    "missing_fields",
    "location_query",
    "resolved_location",
    "places_results",
    "workspace_amenities",
    "route_candidates",
    "scored_results",
    "explanations",
    "explanation",
    "pending_approval",
    "tool_call_count",
    "errors",
    "retry_counts",
)


def _turn_reset_input(message: str) -> dict:
    fresh = new_agent_state(user_id="", session_id="")
    reset = {field: fresh[field] for field in _PER_TURN_RESET_FIELDS}
    reset["messages"] = [HumanMessage(content=message)]
    return reset


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _build_response(session_id: str, result: dict) -> ChatResponse:
    if "__interrupt__" in result:
        question = result["__interrupt__"][0].value
        return ChatResponse(session_id=session_id, status="awaiting_input", question=question)

    recommendations = [
        Recommendation(
            rank=i + 1,
            place_id=scored.item.place_id,
            name=scored.item.name,
            score=scored.total_score,
            score_breakdown={c.factor: c.score for c in scored.components},
            explanation=result.get("explanations", {}).get(scored.item.place_id),
            lat=scored.item.lat,
            lng=scored.item.lng,
        )
        for i, scored in enumerate(result.get("scored_results") or [])
    ]

    return ChatResponse(
        session_id=session_id,
        status="completed",
        intent=result.get("intent"),
        recommendations=recommendations,
        message=result.get("explanation"),
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)) -> ChatResponse:
    graph = get_graph()
    session_id = request.session_id or str(uuid.uuid4())
    config = _config(session_id)

    if request.session_id:
        snapshot = graph.get_state(config)
        session_exists = bool(snapshot.values)
        is_paused = bool(snapshot.next)
    else:
        session_exists = False
        is_paused = False

    if is_paused:
        graph_input = Command(resume=request.message)
    elif session_exists:
        graph_input = _turn_reset_input(request.message)
    else:
        initial_state = new_agent_state(user_id=user["uid"], session_id=session_id)
        initial_state["messages"] = [HumanMessage(content=request.message)]
        graph_input = initial_state

    result = await graph.ainvoke(graph_input, config)
    return _build_response(session_id, result)


@router.post("/chat/{session_id}/resume", response_model=ChatResponse)
async def resume(
    session_id: str, request: ResumeRequest, user: dict = Depends(get_current_user)
) -> ChatResponse:
    graph = get_graph()
    config = _config(session_id)
    snapshot = graph.get_state(config)

    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not snapshot.next:
        raise HTTPException(status_code=409, detail="Session is not awaiting input.")

    resume_value = request.answer if request.answer is not None else request.approved
    result = await graph.ainvoke(Command(resume=resume_value), config)
    return _build_response(session_id, result)

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

As of M8.5, a session can also be paused on request_user_approval's
calendar-event interrupt -- a fundamentally different kind of pause that
must NEVER be auto-resumed from free text (see the `pending_approval`
checks in both chat() and resume() below): a non-empty string is truthy
in Python, so naively forwarding a typed message as the interrupt's
resume value could accidentally confirm a calendar write the user never
explicitly approved. Both endpoints tell the two interrupt kinds apart by
checking `pending_approval` on the paused state, not by any client-
supplied hint.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agent.graph import get_graph
from app.agent.state import new_agent_state
from app.auth.dependencies import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse, ProposedEvent, Recommendation, ResumeRequest
from app.scoring.base import item_display_name, item_id, item_polyline

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
    "approval_decision",
    "tool_call_count",
    "errors",
    "retry_counts",
    # last_weather_recommendation is deliberately NOT in this list -- see
    # agent/state.py's field comment. M8.5's "add to calendar" needs it to
    # survive into a later turn, unlike everything else here.
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
        value = result["__interrupt__"][0].value
        # request_user_approval (M8.5) interrupts with a dict payload;
        # ask_user (M4.4) interrupts with a plain question string. Telling
        # them apart here, not by tracking "which node paused us"
        # separately, keeps this the one place that has to know both
        # interrupt shapes exist.
        if isinstance(value, dict) and value.get("kind") == "calendar_event":
            return ChatResponse(
                session_id=session_id,
                status="awaiting_approval",
                proposed_event=ProposedEvent(**value["payload"]),
            )
        return ChatResponse(session_id=session_id, status="awaiting_input", question=value)

    recommendations = [
        Recommendation(
            rank=i + 1,
            place_id=item_id(scored.item),
            name=item_display_name(scored.item),
            score=scored.total_score,
            score_breakdown={c.factor: c.score for c in scored.components},
            explanation=result.get("explanations", {}).get(item_id(scored.item)),
            # None for RouteCandidate/HourlyForecast -- see Recommendation's
            # own field comment (schemas/chat.py) for why that's correct,
            # not a bug.
            lat=getattr(scored.item, "lat", None),
            lng=getattr(scored.item, "lng", None),
            # M6.7: polyline is RouteCandidate-only, start_time is
            # HourlyForecast-only -- both None for fitness/workspace results.
            polyline=item_polyline(scored.item),
            start_time=getattr(scored.item, "start_time", None),
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
        if snapshot.values.get("pending_approval"):
            # M8.5: never let a free-text message resolve a calendar
            # approval, even coincidentally (e.g. typing "no" -- a
            # non-empty string is truthy in Python, which would wrongly
            # confirm the write if this endpoint naively forwarded it as
            # the interrupt's resume value). The approval card (M8.7)
            # must use /resume with an explicit `approved` boolean
            # instead -- see that endpoint for why this isn't just
            # pushed there either.
            raise HTTPException(
                status_code=409,
                detail=(
                    "This session is awaiting a calendar approval decision -- "
                    'use POST /v1/chat/{sessionId}/resume with {"approved": true|false}.'
                ),
            )
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

    if snapshot.values.get("pending_approval"):
        # M8.5: require `approved` explicitly rather than falling back to
        # `answer` the way the clarifying-question case does below --
        # never coerce an arbitrary value (e.g. a stray `answer` string)
        # into the approval decision. Pydantic already guarantees
        # `approved` is a real bool or None at the request-schema level
        # (see ResumeRequest), so there is no "truthy string" path into
        # request_user_approval's interrupt() resume value at all.
        if request.approved is None:
            raise HTTPException(
                status_code=422,
                detail='This session is awaiting a calendar approval decision -- send {"approved": true|false}.',
            )
        resume_value = request.approved
    else:
        resume_value = request.answer

    result = await graph.ainvoke(Command(resume=resume_value), config)
    return _build_response(session_id, result)

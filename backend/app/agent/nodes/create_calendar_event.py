"""
create_calendar_event node (design doc Step 4 node table: "Executes only
after request_user_approval returns confirmed"). The one and only place
in this entire codebase that calls CalendarProvider.create_event -- M8.8's
test asserts exactly that no other code path reaches it without
state["approval_decision"] being True, which only request_user_approval's
interrupt() resume ever sets (see that node's docstring).

calendar_rejected lives here too, not its own file -- it's the direct
counterpart to create_calendar_event (the other branch
_route_after_approval, agent/graph.py, can take), not a separate concern.
"""
import time

from app.agent.state import AgentState
from app.db.repositories import calendar_action_repository, calendar_repository
from app.providers.calendar_provider import CalendarProvider


def calendar_rejected(state: AgentState) -> dict:
    """Reached when the user explicitly declines the proposal
    (approval_decision is False) -- a normal, expected outcome, not an
    error. No Firestore record is written for a rejected proposal -- see
    calendar_action_repository's module docstring for why "rejected"
    isn't a state worth persisting here."""
    return {"explanation": "No problem -- I won't add that to your calendar."}


async def create_calendar_event(
    state: AgentState,
    provider: CalendarProvider | None = None,
    repo=calendar_repository,
    actions=calendar_action_repository,
) -> dict:
    uid = state["user_id"]
    payload = state["pending_approval"]["payload"]

    # Written BEFORE the Google Calendar API call, not after -- so a
    # crash or timeout mid-call still leaves an honest "confirmed"
    # record instead of no record at all (see calendar_action_repository's
    # record_confirmed docstring).
    action_id = actions.record_confirmed(uid, payload)

    tokens = repo.get_tokens(uid)
    if tokens is None:
        # Disconnected between proposing and confirming -- rare, but real
        # (design doc: revoking must immediately stop all calendar writes,
        # and this is the window where that matters most).
        actions.mark_failed(uid, action_id, "Calendar was disconnected before this could be created.")
        return {
            "explanation": (
                "Your calendar got disconnected before I could add this -- "
                "reconnect it in Settings and try again."
            )
        }

    provider = provider or CalendarProvider()
    try:
        if tokens.expires_at <= time.time():
            tokens = await provider.refresh(tokens.refresh_token)
            repo.save_tokens(uid, tokens)

        event_id = await provider.create_event(
            tokens.access_token,
            title=payload["title"],
            start=payload["start"],
            end=payload["end"],
            location=payload.get("location"),
        )
    except Exception as exc:  # noqa: BLE001 -- reported honestly, not silently swallowed
        actions.mark_failed(uid, action_id, str(exc))
        return {"explanation": f"I couldn't add that to your calendar: {exc}"}

    actions.mark_created(uid, action_id, event_id)
    return {"explanation": f"Added to your calendar: {payload['title']}."}

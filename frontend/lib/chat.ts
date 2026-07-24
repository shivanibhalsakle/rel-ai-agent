/**
 * Types and API calls for POST /v1/chat and POST /v1/chat/{sessionId}/resume
 * (see backend app/schemas/chat.py / app/api/chat.py, Milestone 4.10 + M8.5).
 *
 * Through M7, `/resume` was never actually called from the frontend -- the
 * backend auto-detects a paused session from sessionId alone (M4.10's whole
 * point), so sendChatMessage was the only call the UI needed, whether it
 * was starting a conversation, answering a clarifying question, or asking
 * a follow-up. M8.5 changes that for exactly one case: a paused calendar
 * approval. The backend deliberately REFUSES to auto-resume that from free
 * text (a non-empty string is truthy in Python -- see app/api/chat.py's
 * module docstring for why that's a real bug it closes, not caution for
 * its own sake), so confirming/rejecting a proposed event has to go
 * through sendApprovalDecision -> /resume with an explicit boolean.
 */
import { apiFetch } from "./api-client";

export interface Recommendation {
  rank: number;
  placeId: string;
  name: string;
  score: number;
  scoreBreakdown: Record<string, number>;
  explanation: string | null;
  // Optional as of M6: only fitness/workspace results (real places) have
  // a single point. Route results are a path, not a point (M6.7 renders
  // those via polyline instead), and weather results have no location of
  // their own. RecommendationMap already filters non-finite coordinates
  // (M5.5), so this degrades to "no pin" rather than a broken marker.
  lat: number | null;
  lng: number | null;
  // Added for M6.7 (route map overlay + weather timeline). polyline is
  // RouteCandidate-only (an encoded path, drawn via RecommendationMap's
  // Polyline overlay instead of a pin -- see lat/lng's comment above for
  // why a route has no single point). startTime is HourlyForecast-only
  // (raw ISO 8601 UTC, e.g. "2026-07-24T14:00:00Z") -- `name` is already
  // a human-formatted version of this for display in a card, but
  // WeatherTimeline needs the raw value to sort/plot chronologically.
  // Both None for fitness/workspace results.
  polyline: string | null;
  startTime: string | null;
}

// M8.5/M8.7: the calendar-event proposal request_user_approval's interrupt
// pauses on. Mirrors backend ProposedEvent (schemas/chat.py) exactly.
export interface ProposedEvent {
  title: string;
  start: string;
  end: string;
  location: string | null;
}

export interface ChatResponse {
  sessionId: string;
  status: "completed" | "awaiting_input" | "awaiting_approval";
  intent: string | null;
  question: string | null;
  // Set only when status === "awaiting_approval".
  proposedEvent: ProposedEvent | null;
  recommendations: Recommendation[];
  message: string | null;
}

/**
 * Thrown by sendChatMessage on any non-2xx response, carrying the HTTP
 * status so callers can branch on it (e.g. redirect to sign-in on 401)
 * without string-matching a message.
 *
 * Note on scope: the design doc's original API contract sketch (Step 7)
 * described 422 tool_budget_exceeded and 502 provider_unavailable as
 * dedicated error codes. The agent as actually built (M4.8/M4.9) handles
 * both cases INSIDE the graph instead -- budget_exceeded and
 * handle_provider_error's degrade path both return a normal 200 with an
 * explanatory `message`, not an HTTP error -- because a graceful
 * in-conversation reply is better UX than a raw error for something the
 * agent already knows how to talk about. So in practice the only
 * status this UI needs to treat specially is 401; everything else
 * (a real 5xx, a genuinely unexpected failure) just gets a generic
 * "something went wrong" fallback.
 */
export class ChatApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ChatApiError";
    this.status = status;
  }
}

export async function sendChatMessage(
  idToken: string | null,
  sessionId: string | null,
  message: string
): Promise<ChatResponse> {
  const res = await apiFetch("/v1/chat", idToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId: sessionId ?? undefined, message }),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const text = detail.detail
      ? typeof detail.detail === "string"
        ? detail.detail
        : JSON.stringify(detail.detail)
      : `Error ${res.status}`;
    throw new ChatApiError(res.status, text);
  }

  return res.json();
}

/**
 * Confirms or rejects the calendar-event proposal a session is currently
 * paused on. Unlike sendChatMessage, this always targets an EXISTING,
 * already-paused sessionId -- there's no "start fresh" branch here, since
 * an approval decision only ever makes sense as a reply to a specific
 * pending proposal. The backend enforces that too (a 422 if `approved`
 * wasn't a real boolean, a 409 if nothing's actually pending) -- this
 * function surfaces either as a ChatApiError the same way sendChatMessage
 * does, rather than a distinct error type.
 */
export async function sendApprovalDecision(
  idToken: string | null,
  sessionId: string,
  approved: boolean
): Promise<ChatResponse> {
  const res = await apiFetch(`/v1/chat/${encodeURIComponent(sessionId)}/resume`, idToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const text = detail.detail
      ? typeof detail.detail === "string"
        ? detail.detail
        : JSON.stringify(detail.detail)
      : `Error ${res.status}`;
    throw new ChatApiError(res.status, text);
  }

  return res.json();
}

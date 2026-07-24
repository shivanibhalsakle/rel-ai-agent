/**
 * Types and API call for POST /v1/chat (see backend app/schemas/chat.py /
 * app/api/chat.py, Milestone 4.10). `/v1/chat/{sessionId}/resume` isn't
 * called from the frontend -- the backend auto-detects a paused session
 * from sessionId alone (M4.10's whole point), so the UI only ever needs
 * this one call, whether it's starting a conversation, answering a
 * clarifying question, or asking a follow-up.
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
}

export interface ChatResponse {
  sessionId: string;
  status: "completed" | "awaiting_input" | "awaiting_approval";
  intent: string | null;
  question: string | null;
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

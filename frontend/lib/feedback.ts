/**
 * Types and API call for POST /v1/recommendations/{recommendationId}/feedback
 * (Milestone 7 -- see backend app/schemas/feedback.py / app/api/feedback.py).
 *
 * scoreBreakdown is sent straight from the Recommendation the user is
 * reacting to (see chat.ts) -- the same factor->score map already
 * rendered on the card, not re-derived here. That mirrors the backend
 * schema's own reasoning (feedback.py's module docstring): it's what the
 * user actually saw when they acted, and the backend has nothing durable
 * to re-fetch it from between turns anyway.
 */
import { apiFetch } from "./api-client";

export type FeedbackAction = "accepted" | "rejected";

export interface FeedbackPayload {
  sessionId: string;
  intent: string;
  action: FeedbackAction;
  reason?: string;
  scoreBreakdown: Record<string, number>;
}

export async function sendFeedback(
  idToken: string | null,
  recommendationId: string,
  payload: FeedbackPayload
): Promise<void> {
  const res = await apiFetch(`/v1/recommendations/${encodeURIComponent(recommendationId)}/feedback`, idToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const text = detail.detail
      ? typeof detail.detail === "string"
        ? detail.detail
        : JSON.stringify(detail.detail)
      : `Error ${res.status}`;
    throw new Error(text);
  }
}

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
}

export interface ChatResponse {
  sessionId: string;
  status: "completed" | "awaiting_input" | "awaiting_approval";
  intent: string | null;
  question: string | null;
  recommendations: Recommendation[];
  message: string | null;
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
    throw new Error(detail.detail ? JSON.stringify(detail.detail) : `Error ${res.status}`);
  }

  return res.json();
}

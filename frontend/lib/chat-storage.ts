/**
 * Persists the active chat thread (messages + sessionId) to localStorage,
 * scoped per signed-in user, so a page reload doesn't lose an
 * awaiting_input conversation -- exactly the bug hit testing M5.1/M5.2.
 *
 * Known limit, not solved here: this only helps within the backend's
 * current process lifetime. LangGraph's checkpointer is in-memory (see
 * backend app/agent/graph.py's own docstring on that), so a backend
 * restart loses the actual agent state even though the frontend still
 * "remembers" the sessionId and prior messages. If that happens, the
 * next /v1/chat call for that sessionId is treated as a fresh start
 * server-side (M4.10's documented behavior for an unknown thread id) --
 * the restored, displayed history would then be stale relative to what
 * the backend actually knows about. A durable (Firestore-backed)
 * checkpointer is the real fix; it's already tracked as a known gap in
 * graph.py, not something to duplicate here.
 */
import { Recommendation } from "./chat";

export interface ThreadMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  recommendations?: Recommendation[];
}

export interface StoredThread {
  sessionId: string | null;
  messages: ThreadMessage[];
}

const EMPTY_THREAD: StoredThread = { sessionId: null, messages: [] };

function storageKey(uid: string): string {
  return `relocation-copilot:chat:${uid}`;
}

export function loadThread(uid: string): StoredThread {
  if (typeof window === "undefined") return EMPTY_THREAD;
  try {
    const raw = window.localStorage.getItem(storageKey(uid));
    if (!raw) return EMPTY_THREAD;
    const parsed = JSON.parse(raw);
    return {
      sessionId: typeof parsed.sessionId === "string" ? parsed.sessionId : null,
      messages: Array.isArray(parsed.messages) ? parsed.messages : [],
    };
  } catch {
    // Malformed/corrupted storage shouldn't break the page -- start fresh.
    return EMPTY_THREAD;
  }
}

export function saveThread(uid: string, thread: StoredThread): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey(uid), JSON.stringify(thread));
}

export function clearThread(uid: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(storageKey(uid));
}

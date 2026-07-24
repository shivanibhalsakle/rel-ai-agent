"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ChatApiError, ChatResponse, Recommendation, sendApprovalDecision, sendChatMessage } from "@/lib/chat";
import { ThreadMessage, clearThread, loadThread, saveThread } from "@/lib/chat-storage";
import { FeedbackAction, sendFeedback } from "@/lib/feedback";
import { RecommendationList } from "@/components/recommendation-cards/RecommendationList";
import { RecommendationMap } from "@/components/map/RecommendationMap";
import { WeatherTimeline } from "@/components/weather/WeatherTimeline";
import { ApprovalCard } from "@/components/calendar/ApprovalCard";

export default function ChatPage() {
  const { user, loading, getIdToken } = useAuth();
  const router = useRouter();

  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Guards against saving an empty thread back over a real persisted one
  // before the initial load-from-storage effect has run.
  const hydrated = useRef(false);

  useEffect(() => {
    if (!user) return;
    const stored = loadThread(user.uid);
    // Syncing render state from an external store (localStorage) keyed on
    // a value that itself resolves asynchronously (Firebase auth's user)
    // is exactly the "adopt external state when a dependency changes"
    // case effects exist for -- there's no synchronous alternative here,
    // since `user` isn't known until the auth context resolves. The two
    // setState calls below are batched into a single re-render by React
    // (automatic batching, effects included, since React 18) despite the
    // rule's generic "cascading renders" warning, so there's no real perf
    // cost being traded away here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMessages(stored.messages);
    setSessionId(stored.sessionId);
    hydrated.current = true;
  }, [user]);

  useEffect(() => {
    if (!user || !hydrated.current) return;
    saveThread(user.uid, { sessionId, messages });
  }, [user, sessionId, messages]);

  if (loading) return null;

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center p-8 text-center">
        <p className="text-slate-600">
          Please{" "}
          <Link href="/" className="underline">
            sign in
          </Link>{" "}
          first.
        </p>
      </main>
    );
  }

  function appendAssistantReply(response: ChatResponse) {
    const text =
      response.status === "awaiting_input"
        ? response.question ?? "Could you say a bit more?"
        : response.status === "awaiting_approval"
        ? `Want me to add "${response.proposedEvent?.title ?? "this"}" to your calendar?`
        : response.message ?? (response.recommendations.length ? "Here's what I found:" : "Done.");

    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        text,
        recommendations: response.recommendations.length ? response.recommendations : undefined,
        intent: response.intent,
        proposedEvent: response.proposedEvent,
      },
    ]);
  }

  // M8.5/M8.7: confirms or rejects the proposal on whichever ApprovalCard
  // the user clicked -- always targets the CURRENT sessionId, same
  // reasoning as handleFeedback (one session per thread, no per-message
  // snapshot needed). Reuses handleSubmit's error handling shape (401 ->
  // sign-in, everything else -> inline error) rather than duplicating it,
  // since sendApprovalDecision throws the same ChatApiError sendChatMessage
  // does.
  async function handleApprovalDecision(approved: boolean) {
    if (!sessionId) return;
    try {
      const idToken = await getIdToken();
      const response = await sendApprovalDecision(idToken, sessionId, approved);
      appendAssistantReply(response);
    } catch (err) {
      if (err instanceof ChatApiError && err.status === 401) {
        if (user) clearThread(user.uid);
        router.push("/");
        return;
      }
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      throw err; // lets ApprovalCard's own try/catch show its retry UI too
    }
  }

  // Attaches feedback to whichever session/intent were active when this
  // card's message arrived. This app keeps exactly one sessionId per
  // conversation thread (only "New conversation" ever resets it), so the
  // current sessionId state is correct for any message still on screen --
  // no need to snapshot it per-message.
  async function handleFeedback(
    recommendation: Recommendation,
    intent: string | null,
    action: FeedbackAction,
    reason?: string
  ) {
    const idToken = await getIdToken();
    await sendFeedback(idToken, recommendation.placeId, {
      sessionId: sessionId ?? "",
      intent: intent ?? "general",
      action,
      reason,
      scoreBreakdown: recommendation.scoreBreakdown,
    });
  }

  function startNewConversation() {
    setMessages([]);
    setSessionId(null);
    setError(null);
    if (user) clearThread(user.uid);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", text }]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const idToken = await getIdToken();
      const response = await sendChatMessage(idToken, sessionId, text);
      setSessionId(response.sessionId);
      appendAssistantReply(response);
    } catch (err) {
      if (err instanceof ChatApiError && err.status === 401) {
        // Token's no longer valid -- nothing left to persist under this
        // (soon to be wrong) uid, and the sign-in page is the only useful
        // next step.
        if (user) clearThread(user.uid);
        router.push("/");
        return;
      }
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Chat</h1>
          <p className="mt-1 text-sm text-slate-600">
            Ask for a gym, a workspace, or anything else — I&apos;ll ask a follow-up if I need more to go on.
          </p>
        </div>
        {messages.length > 0 && (
          <button onClick={startNewConversation} className="shrink-0 text-sm text-slate-500 underline">
            New conversation
          </button>
        )}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto rounded-md border border-slate-200 p-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400">Try &quot;find me a yoga studio&quot; to get started.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              className={
                "inline-block max-w-[85%] rounded-lg px-3 py-2 text-left text-sm " +
                (m.role === "user" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-800")
              }
            >
              <p>{m.text}</p>
            </div>
            {m.recommendations && m.intent === "weather" && (
              // Weather gets its own chronological view instead of
              // RecommendationList/RecommendationMap (M6.7) -- neither a
              // rank-first card list nor a map fits an hourly forecast
              // (there's no location to pin; see Recommendation.lat/lng's
              // comment), and "which hour is #1" matters less here than
              // "how does the day look."
              <div className="mt-2 text-left">
                <WeatherTimeline recommendations={m.recommendations} />
              </div>
            )}
            {m.recommendations && m.intent !== "weather" && (
              <div className="mt-2 space-y-2 text-left">
                <RecommendationList
                  recommendations={m.recommendations}
                  onFeedback={(rec, action, reason) => handleFeedback(rec, m.intent ?? null, action, reason)}
                />
                <RecommendationMap recommendations={m.recommendations} />
              </div>
            )}
            {m.proposedEvent && (
              <div className="text-left">
                <ApprovalCard proposedEvent={m.proposedEvent} onDecide={handleApprovalDecision} />
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="text-left">
            <div className="inline-block animate-pulse rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-500">
              Thinking…
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600">
          {error} <button onClick={() => setError(null)} className="underline">Dismiss</button>
        </p>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={sending}
          placeholder="Message"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </form>
    </main>
  );
}

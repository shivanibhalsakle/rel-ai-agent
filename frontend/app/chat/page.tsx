"use client";

import { FormEvent, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { ChatResponse, Recommendation, sendChatMessage } from "@/lib/chat";

interface ThreadMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  recommendations?: Recommendation[];
}

export default function ChatPage() {
  const { user, loading, getIdToken } = useAuth();
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState("");
  // In-memory only for now -- surviving a page reload mid-conversation is
  // M5.3's job (session persistence), not this step's.
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loading) return null;

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center p-8 text-center">
        <p className="text-slate-600">
          Please{" "}
          <a href="/" className="underline">
            sign in
          </a>{" "}
          first.
        </p>
      </main>
    );
  }

  function appendAssistantReply(response: ChatResponse) {
    const text =
      response.status === "awaiting_input"
        ? response.question ?? "Could you say a bit more?"
        : response.message ?? (response.recommendations.length ? "Here's what I found:" : "Done.");

    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        text,
        recommendations: response.recommendations.length ? response.recommendations : undefined,
      },
    ]);
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
      setError((err as Error).message);
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 p-8">
      <div>
        <h1 className="text-2xl font-semibold">Chat</h1>
        <p className="mt-1 text-sm text-slate-600">
          Ask for a gym, a workspace, or anything else — I&apos;ll ask a follow-up if I need more to go on.
        </p>
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
              {/* Minimal list rendering for now -- the real recommendation
                  card component is M5.2's job. */}
              {m.recommendations && (
                <ol className="mt-2 space-y-1">
                  {m.recommendations.map((r) => (
                    <li key={r.placeId} className="border-t border-slate-300 pt-1 first:border-t-0 first:pt-0">
                      <span className="font-medium">
                        {r.rank}. {r.name}
                      </span>{" "}
                      <span className="text-slate-500">({r.score}/100)</span>
                      {r.explanation && <p className="text-slate-600">{r.explanation}</p>}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

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

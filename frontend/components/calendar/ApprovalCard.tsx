"use client";

import { useState } from "react";
import { ProposedEvent } from "@/lib/chat";

type ApprovalStatus = "idle" | "submitting" | "done" | "error";

function formatEventTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

// M8.5/M8.7: the frontend half of the "structurally impossible to bypass"
// requirement. There is exactly one way this card can lead to a calendar
// write -- clicking Confirm calls onDecide(true), which the chat page
// wires to sendApprovalDecision (lib/chat.ts), which is the ONLY caller
// of POST /v1/chat/{sessionId}/resume with an `approved` body in this
// codebase. No other button, keystroke, or typed message can reach it --
// the free-text input box is structurally incapable of resolving this
// interrupt (see app/api/chat.py's 409 guard).
export function ApprovalCard({
  proposedEvent,
  onDecide,
}: {
  proposedEvent: ProposedEvent;
  onDecide: (approved: boolean) => Promise<void>;
}) {
  const [status, setStatus] = useState<ApprovalStatus>("idle");
  const [decision, setDecision] = useState<boolean | null>(null);

  async function decide(approved: boolean) {
    setStatus("submitting");
    setDecision(approved);
    try {
      await onDecide(approved);
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="mt-2 max-w-sm rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Add to calendar?</p>
      <h3 className="mt-1 font-medium text-slate-900">{proposedEvent.title}</h3>
      <p className="mt-1 text-sm text-slate-600">
        {formatEventTime(proposedEvent.start)} – {formatEventTime(proposedEvent.end)}
      </p>
      {proposedEvent.location && <p className="text-sm text-slate-600">{proposedEvent.location}</p>}

      {status === "idle" && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => decide(true)}
            className="rounded-full bg-slate-900 px-3 py-1 text-xs text-white hover:bg-slate-700"
          >
            Confirm
          </button>
          <button
            onClick={() => decide(false)}
            className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            No thanks
          </button>
        </div>
      )}

      {status === "submitting" && (
        <p className="mt-3 text-xs text-slate-400">{decision ? "Adding…" : "Okay…"}</p>
      )}

      {status === "done" && <p className="mt-3 text-xs text-slate-400">Done — see the reply below.</p>}

      {status === "error" && (
        <div className="mt-3 flex items-center gap-2">
          <p className="text-xs text-red-600">Something went wrong.</p>
          <button onClick={() => setStatus("idle")} className="text-xs underline text-slate-500">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}

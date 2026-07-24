import { useState } from "react";
import { Recommendation } from "@/lib/chat";
import { FeedbackAction } from "@/lib/feedback";

function humanizeFactor(factor: string): string {
  return factor
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function scoreTone(score: number): string {
  if (score >= 75) return "bg-emerald-100 text-emerald-800";
  if (score >= 50) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}

type FeedbackStatus = "idle" | "confirming-reject" | "submitting" | "done" | "error";

export function RecommendationCard({
  recommendation,
  onFeedback,
}: {
  recommendation: Recommendation;
  // Optional -- a card rendered somewhere with no session/intent context
  // to attach feedback to (or in a test) just omits the accept/reject UI
  // entirely rather than needing a no-op stub passed in.
  onFeedback?: (action: FeedbackAction, reason?: string) => Promise<void>;
}) {
  const { rank, name, score, scoreBreakdown, explanation } = recommendation;
  const factors = Object.entries(scoreBreakdown);

  const [status, setStatus] = useState<FeedbackStatus>("idle");
  const [reason, setReason] = useState("");

  async function submit(action: FeedbackAction, withReason?: string) {
    if (!onFeedback) return;
    setStatus("submitting");
    try {
      await onFeedback(action, withReason);
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  return (
    <li className="list-none rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-medium text-white">
            {rank}
          </span>
          <h3 className="font-medium text-slate-900">{name}</h3>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${scoreTone(score)}`}>
          {score}/100
        </span>
      </div>

      {explanation && <p className="mt-2 text-sm text-slate-600">{explanation}</p>}

      {/* Factor breakdown -- this IS deterministic and real (M3's
          ScoreComponent, straight off scoreBreakdown), unlike a
          verified/estimated/unavailable confidence badge would be. See
          RecommendationList's docstring for why there's no badge here. */}
      {factors.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {factors.map(([factor, value]) => (
            <div key={factor} className="flex items-center gap-2 text-xs text-slate-500">
              <span className="w-28 shrink-0 truncate">{humanizeFactor(factor)}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-slate-400"
                  style={{ width: `${Math.round(value * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Milestone 7: accept/reject feedback. Each card only ever submits
          once -- there's no "undo" UI here, matching the append-only
          feedback log this writes to (feedback_repository.py's own
          comment: an event log, not something updated in place). */}
      {onFeedback && (
        <div className="mt-3 border-t border-slate-100 pt-2">
          {status === "idle" && (
            <div className="flex gap-2">
              <button
                onClick={() => submit("accepted")}
                className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
              >
                👍 Helpful
              </button>
              <button
                onClick={() => setStatus("confirming-reject")}
                className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
              >
                👎 Not helpful
              </button>
            </div>
          )}

          {status === "confirming-reject" && (
            <div className="flex flex-col gap-2">
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="What wasn't a fit? (optional)"
                className="rounded-md border border-slate-300 px-2 py-1 text-xs"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => submit("rejected", reason.trim() || undefined)}
                  className="rounded-full bg-slate-900 px-3 py-1 text-xs text-white hover:bg-slate-700"
                >
                  Submit
                </button>
                <button
                  onClick={() => setStatus("idle")}
                  className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-500"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {status === "submitting" && <p className="text-xs text-slate-400">Saving…</p>}

          {status === "done" && <p className="text-xs text-slate-400">Thanks — saved.</p>}

          {status === "error" && (
            <div className="flex items-center gap-2">
              <p className="text-xs text-red-600">Couldn&apos;t save that.</p>
              <button onClick={() => setStatus("idle")} className="text-xs underline text-slate-500">
                Try again
              </button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

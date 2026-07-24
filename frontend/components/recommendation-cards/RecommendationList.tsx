import { Recommendation } from "@/lib/chat";
import { FeedbackAction } from "@/lib/feedback";
import { RecommendationCard } from "./RecommendationCard";

/**
 * Renders a ranked list of recommendations from a completed /v1/chat
 * response.
 *
 * Deliberately no per-field confidence badges (design doc Step 3/6's
 * "verified/estimated/unavailable" dataConfidence map, also listed as an
 * M5 feature) -- the backend doesn't produce that data today. M4.10's
 * schemas/chat.py already flagged this on the way in: "a real per-field
 * confidence map needs its own design pass, not a guess." Faking a
 * confidence label from data that was never actually assessed for
 * confidence would be worse than the gap it's meant to fill, so this
 * renders exactly what the API returns instead -- a deterministic score,
 * its real factor breakdown (see RecommendationCard), and an LLM-phrased
 * explanation grounded in that breakdown. Revisit once dataConfidence
 * exists on the wire.
 */
export function RecommendationList({
  recommendations,
  onFeedback,
}: {
  recommendations: Recommendation[];
  // Optional, threaded straight through to each card (Milestone 7) --
  // omit it and the list renders exactly as it did before feedback
  // existed, which is what every pre-M7 caller (and RecommendationCard's
  // own tests) still expects.
  onFeedback?: (recommendation: Recommendation, action: FeedbackAction, reason?: string) => Promise<void>;
}) {
  if (recommendations.length === 0) return null;

  return (
    <ol className="space-y-2">
      {recommendations.map((r) => (
        <RecommendationCard
          key={r.placeId}
          recommendation={r}
          onFeedback={onFeedback ? (action, reason) => onFeedback(r, action, reason) : undefined}
        />
      ))}
    </ol>
  );
}

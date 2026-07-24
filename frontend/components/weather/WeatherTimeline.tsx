import { Recommendation } from "@/lib/chat";

function scoreTone(score: number): string {
  if (score >= 75) return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (score >= 50) return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-red-200 bg-red-50 text-red-800";
}

/**
 * A chronological strip of hourly comfort scores -- deliberately not just
 * RecommendationList re-rendered. Weather is the one domain here where
 * "when" matters more than "which ranks #1": someone asking "best time to
 * run today" wants to see the whole day's shape (is it getting better or
 * worse from now), not a rank-ordered top-5 that scrambles the hours out
 * of sequence. Sorted by startTime (M6.7's new field on Recommendation,
 * raw ISO 8601 UTC -- see lib/chat.ts's comment on why `name`, the
 * human-formatted version, can't be sorted the same way), not by rank.
 *
 * Recommendations with no startTime are filtered out rather than shown
 * out of place -- defensive against stale pre-M6.7 localStorage history,
 * same pattern as RecommendationMap's plottable/routable filters.
 */
export function WeatherTimeline({ recommendations }: { recommendations: Recommendation[] }) {
  const hours = recommendations
    .filter((r): r is Recommendation & { startTime: string } => typeof r.startTime === "string")
    .slice()
    .sort((a, b) => a.startTime.localeCompare(b.startTime));

  if (hours.length === 0) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {hours.map((hour) => (
        <div
          key={hour.startTime}
          className={`w-36 shrink-0 rounded-lg border p-2 text-xs ${scoreTone(hour.score)}`}
        >
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-medium">{hour.name}</span>
            <span className="shrink-0 text-[11px] opacity-80">{hour.score}/100</span>
          </div>
          {hour.explanation && <p className="mt-1 line-clamp-3 text-[11px] opacity-90">{hour.explanation}</p>}
        </div>
      ))}
    </div>
  );
}

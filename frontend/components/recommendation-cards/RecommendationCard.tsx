import { Recommendation } from "@/lib/chat";

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

export function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  const { rank, name, score, scoreBreakdown, explanation } = recommendation;
  const factors = Object.entries(scoreBreakdown);

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
    </li>
  );
}

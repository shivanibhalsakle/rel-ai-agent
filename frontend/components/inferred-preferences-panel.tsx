"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";

interface InferredAdjustment {
  importanceDelta: Record<string, number>;
  reasons: string[];
}

function humanizeFactor(factor: string): string {
  return factor
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * "Why we think this" panel (Milestone 7) -- shows the feedback-derived
 * adjustment on top of the explicit sliders above it on this page,
 * fetched from GET /v1/preferences/inferred as its own separate resource
 * (app/db/repositories/preference_repository.py's module docstring
 * explains why explicit and inferred are kept as two different Firestore
 * documents rather than one merged value: it's what makes a panel like
 * this able to show a real diff instead of guessing at one).
 *
 * Self-contained (fetches its own data given just a way to get an ID
 * token) rather than threading fetched state down from the settings
 * page, the same shape RecommendationMap uses for its own Google Maps
 * fetch.
 */
export function InferredPreferencesPanel({ getIdToken }: { getIdToken: () => Promise<string | null> }) {
  const [adjustment, setAdjustment] = useState<InferredAdjustment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const idToken = await getIdToken();
        const res = await apiFetch("/v1/preferences/inferred", idToken);
        if (!res.ok) {
          if (!cancelled) setError(`Couldn't load this (error ${res.status}).`);
          return;
        }
        const data: InferredAdjustment = await res.json();
        if (!cancelled) setAdjustment(data);
      } catch {
        if (!cancelled) setError("Couldn't load this.");
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const factors = adjustment ? Object.entries(adjustment.importanceDelta) : [];

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h2 className="text-sm font-medium text-slate-900">Why we think this</h2>
      <p className="mt-1 text-xs text-slate-500">
        Beyond what you&apos;ve set above, accepting or rejecting recommendations in chat nudges how we
        weigh a few factors. This is everything currently nudged, and why.
      </p>

      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}

      {!adjustment && !error && <p className="mt-3 text-xs text-slate-400">Loading…</p>}

      {adjustment && factors.length === 0 && (
        <p className="mt-3 text-xs text-slate-400">
          Nothing adjusted yet — keep using the accept/reject buttons on recommendations and this will
          fill in once a clear pattern shows up.
        </p>
      )}

      {factors.length > 0 && (
        <ul className="mt-3 space-y-2">
          {factors.map(([factor, delta]) => (
            <li key={factor} className="text-xs text-slate-700">
              <span className="font-medium">
                {humanizeFactor(factor)} +{delta}
              </span>
            </li>
          ))}
        </ul>
      )}

      {adjustment && adjustment.reasons.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-slate-200 pt-2">
          {adjustment.reasons.map((reason, i) => (
            <li key={i} className="text-xs text-slate-500">
              {reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

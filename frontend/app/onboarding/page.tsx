"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api-client";

const ACTIVITY_OPTIONS = [
  "gym",
  "yoga",
  "pilates",
  "running",
  "cycling",
  "swimming",
  "classes",
];

const WORKOUT_TIME_OPTIONS = ["morning", "midday", "evening", "weekends"];

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export default function OnboardingPage() {
  const { user, loading, getIdToken } = useAuth();
  const router = useRouter();

  const [activities, setActivities] = useState<string[]>([]);
  const [budgetMax, setBudgetMax] = useState<string>("");
  const [maxTravelMinutes, setMaxTravelMinutes] = useState<string>("20");
  const [travelMode, setTravelMode] = useState("walk");
  const [minRating, setMinRating] = useState("4");
  const [workoutTimes, setWorkoutTimes] = useState<string[]>([]);
  const [wifi, setWifi] = useState(false);
  const [outlets, setOutlets] = useState(false);
  const [quiet, setQuiet] = useState(false);
  const [indoorOutdoor, setIndoorOutdoor] = useState<"indoor" | "outdoor" | "either">("either");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  if (loading) return null;

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center p-8 text-center">
        <p className="text-slate-600">
          Please <a href="/" className="underline">sign in</a> first.
        </p>
      </main>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const body = {
      activities,
      budgetBand: budgetMax
        ? { min: 0, max: Number(budgetMax), currency: "USD", period: "month" as const }
        : null,
      maxTravelMinutes: maxTravelMinutes ? Number(maxTravelMinutes) : null,
      travelMode,
      minRating: Number(minRating),
      workspaceNeeds: { wifi, outlets, quiet, food: false },
      preferredWorkoutTimes: workoutTimes,
      indoorOutdoorPreference: indoorOutdoor,
      accessibilityRequirements: [],
    };

    try {
      const idToken = await getIdToken();
      const res = await apiFetch("/v1/onboarding", idToken, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ? JSON.stringify(detail.detail) : `Error ${res.status}`);
      }
      setSaved(true);
      setTimeout(() => router.push("/"), 1200);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">Tell us how you like to move and work</h1>
        <p className="mt-1 text-sm text-slate-600">
          Skip anything you're not sure about — you can change these anytime in Settings.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Activities you're interested in</legend>
          <div className="flex flex-wrap gap-2">
            {ACTIVITY_OPTIONS.map((activity) => (
              <button
                type="button"
                key={activity}
                onClick={() => setActivities((prev) => toggle(prev, activity))}
                className={`rounded-full border px-3 py-1 text-sm capitalize ${
                  activities.includes(activity)
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 text-slate-700"
                }`}
              >
                {activity}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="grid grid-cols-2 gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Monthly budget (USD, max)
            <input
              type="number"
              min={0}
              value={budgetMax}
              onChange={(e) => setBudgetMax(e.target.value)}
              placeholder="e.g. 80"
              className="rounded-md border border-slate-300 px-3 py-2"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Max travel time (minutes)
            <input
              type="number"
              min={0}
              value={maxTravelMinutes}
              onChange={(e) => setMaxTravelMinutes(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Preferred travel mode
            <select
              value={travelMode}
              onChange={(e) => setTravelMode(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="walk">Walk</option>
              <option value="bike">Bike</option>
              <option value="transit">Transit</option>
              <option value="drive">Drive</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Minimum rating you'll consider
            <select
              value={minRating}
              onChange={(e) => setMinRating(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              {["3", "3.5", "4", "4.5"].map((r) => (
                <option key={r} value={r}>
                  {r}+
                </option>
              ))}
            </select>
          </label>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-medium">When do you usually work out?</legend>
          <div className="flex flex-wrap gap-2">
            {WORKOUT_TIME_OPTIONS.map((time) => (
              <button
                type="button"
                key={time}
                onClick={() => setWorkoutTimes((prev) => toggle(prev, time))}
                className={`rounded-full border px-3 py-1 text-sm capitalize ${
                  workoutTimes.includes(time)
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 text-slate-700"
                }`}
              >
                {time}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-sm font-medium">For focused work, I need</legend>
          <div className="flex flex-col gap-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={wifi} onChange={(e) => setWifi(e.target.checked)} />
              Reliable Wi-Fi
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={outlets} onChange={(e) => setOutlets(e.target.checked)} />
              Power outlets
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={quiet} onChange={(e) => setQuiet(e.target.checked)} />
              Quiet space
            </label>
          </div>
        </fieldset>

        <label className="flex flex-col gap-1 text-sm">
          Indoor or outdoor?
          <select
            value={indoorOutdoor}
            onChange={(e) => setIndoorOutdoor(e.target.value as typeof indoorOutdoor)}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            <option value="either">No preference</option>
            <option value="indoor">Prefer indoor</option>
            <option value="outdoor">Prefer outdoor</option>
          </select>
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {saved && <p className="text-sm text-green-600">Saved — taking you back home…</p>}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-slate-900 px-4 py-2 text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {submitting ? "Saving…" : "Save preferences"}
        </button>
      </form>
    </main>
  );
}

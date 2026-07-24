"use client";

import { useState } from "react";
import { PreferencesFormValues } from "@/lib/preferences";

const ACTIVITY_OPTIONS = ["gym", "yoga", "pilates", "running", "cycling", "swimming", "classes"];
const WORKOUT_TIME_OPTIONS = ["morning", "midday", "evening", "weekends"];

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

interface Props {
  initialValues: PreferencesFormValues;
  submitLabel: string;
  onSubmit: (values: PreferencesFormValues) => Promise<void>;
}

export function PreferencesForm({ initialValues, submitLabel, onSubmit }: Props) {
  const [values, setValues] = useState(initialValues);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function set<K extends keyof PreferencesFormValues>(key: K, value: PreferencesFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSaved(false);
    try {
      await onSubmit(values);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <fieldset>
        <legend className="mb-2 text-sm font-medium">Activities you&apos;re interested in</legend>
        <div className="flex flex-wrap gap-2">
          {ACTIVITY_OPTIONS.map((activity) => (
            <button
              type="button"
              key={activity}
              onClick={() => set("activities", toggle(values.activities, activity))}
              className={`rounded-full border px-3 py-1 text-sm capitalize ${
                values.activities.includes(activity)
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
            value={values.budgetMax}
            onChange={(e) => set("budgetMax", e.target.value)}
            placeholder="e.g. 80"
            className="rounded-md border border-slate-300 px-3 py-2"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Max travel time (minutes)
          <input
            type="number"
            min={0}
            value={values.maxTravelMinutes}
            onChange={(e) => set("maxTravelMinutes", e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Preferred travel mode
          <select
            value={values.travelMode}
            onChange={(e) => set("travelMode", e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            <option value="walk">Walk</option>
            <option value="bike">Bike</option>
            <option value="transit">Transit</option>
            <option value="drive">Drive</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Minimum rating you&apos;ll consider
          <select
            value={values.minRating}
            onChange={(e) => set("minRating", e.target.value)}
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
              onClick={() => set("workoutTimes", toggle(values.workoutTimes, time))}
              className={`rounded-full border px-3 py-1 text-sm capitalize ${
                values.workoutTimes.includes(time)
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
            <input type="checkbox" checked={values.wifi} onChange={(e) => set("wifi", e.target.checked)} />
            Reliable Wi-Fi
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={values.outlets}
              onChange={(e) => set("outlets", e.target.checked)}
            />
            Power outlets
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={values.quiet} onChange={(e) => set("quiet", e.target.checked)} />
            Quiet space
          </label>
        </div>
      </fieldset>

      <label className="flex flex-col gap-1 text-sm">
        Indoor or outdoor?
        <select
          value={values.indoorOutdoor}
          onChange={(e) => set("indoorOutdoor", e.target.value as PreferencesFormValues["indoorOutdoor"])}
          className="rounded-md border border-slate-300 px-3 py-2"
        >
          <option value="either">No preference</option>
          <option value="indoor">Prefer indoor</option>
          <option value="outdoor">Prefer outdoor</option>
        </select>
      </label>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {saved && <p className="text-sm text-green-600">Saved.</p>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-slate-900 px-4 py-2 text-white hover:bg-slate-700 disabled:opacity-50"
      >
        {submitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}

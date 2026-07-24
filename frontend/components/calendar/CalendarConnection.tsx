"use client";

import { useEffect, useState } from "react";
import { connectCalendar, disconnectCalendar, getCalendarStatus } from "@/lib/calendar";

type LoadState = "loading" | "ready" | "error";

/**
 * Settings-page connect/disconnect control (M8.7). Self-contained --
 * fetches its own status given just a way to get an ID token, same shape
 * InferredPreferencesPanel uses for its own fetch.
 *
 * Connecting is a full-page redirect (window.location.href =
 * authorizationUrl returned by POST /v1/calendar/connect), not something
 * this component's own state machine can complete -- the browser leaves
 * this page entirely for Google's consent screen and comes back via the
 * backend's /oauth/callback redirect (see app/api/calendar.py), landing
 * back here with a ?calendar=connected|cancelled query param. `notice`
 * below reads that once, on mount, to show a one-time confirmation
 * rather than silently reflecting only the polled /status result.
 */
export function CalendarConnection({ getIdToken }: { getIdToken: () => Promise<string | null> }) {
  const [state, setState] = useState<LoadState>("loading");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const calendarParam = params.get("calendar");
    if (calendarParam === "connected") setNotice("Google Calendar connected.");
    else if (calendarParam === "cancelled") setNotice("Calendar connection was cancelled.");
    if (calendarParam) {
      params.delete("calendar");
      const query = params.toString();
      window.history.replaceState({}, "", query ? `${window.location.pathname}?${query}` : window.location.pathname);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const idToken = await getIdToken();
        const status = await getCalendarStatus(idToken);
        if (!cancelled) {
          setConnected(status.connected);
          setState("ready");
        }
      } catch {
        if (!cancelled) setState("error");
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleConnect() {
    setBusy(true);
    setError(null);
    try {
      const idToken = await getIdToken();
      const { authorizationUrl } = await connectCalendar(idToken);
      window.location.href = authorizationUrl;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start calendar connection.");
      setBusy(false);
    }
  }

  async function handleDisconnect() {
    setBusy(true);
    setError(null);
    try {
      const idToken = await getIdToken();
      await disconnectCalendar(idToken);
      setConnected(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't disconnect calendar.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h2 className="text-sm font-medium text-slate-900">Google Calendar</h2>
      <p className="mt-1 text-xs text-slate-500">
        Connect your calendar so weather suggestions can skip times you&apos;re busy, and so I can offer
        to add a pick to your calendar with your explicit confirmation each time -- I never add anything
        without asking first.
      </p>

      {notice && <p className="mt-3 text-xs text-emerald-700">{notice}</p>}
      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}

      {state === "loading" && <p className="mt-3 text-xs text-slate-400">Loading…</p>}

      {state === "error" && <p className="mt-3 text-xs text-red-600">Couldn&apos;t check calendar status.</p>}

      {state === "ready" && (
        <div className="mt-3">
          {connected ? (
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-emerald-700">Connected</span>
              <button
                onClick={handleDisconnect}
                disabled={busy}
                className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              >
                {busy ? "Disconnecting…" : "Disconnect"}
              </button>
            </div>
          ) : (
            <button
              onClick={handleConnect}
              disabled={busy}
              className="rounded-full bg-slate-900 px-3 py-1 text-xs text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {busy ? "Connecting…" : "Connect Google Calendar"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

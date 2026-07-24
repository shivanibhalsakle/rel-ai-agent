/**
 * Types and API calls for Google Calendar connect/disconnect/status
 * (M8.3/M8.7 -- see backend app/api/calendar.py).
 *
 * connectCalendar does NOT itself perform the OAuth redirect -- it only
 * fetches the authorizationUrl from the backend. The caller (settings
 * page) is responsible for navigating the browser there
 * (window.location.href = authorizationUrl), since that's a full-page
 * navigation to Google's own domain, not something a fetch call can do.
 * See app/api/calendar.py's module docstring for why /connect can't just
 * return `{"status": "connected"}` synchronously the way /disconnect can.
 */
import { apiFetch } from "./api-client";

export interface CalendarStatus {
  connected: boolean;
}

export async function getCalendarStatus(idToken: string | null): Promise<CalendarStatus> {
  const res = await apiFetch("/v1/calendar/status", idToken);
  if (!res.ok) throw new Error(`Couldn't check calendar connection (error ${res.status}).`);
  return res.json();
}

export async function connectCalendar(idToken: string | null): Promise<{ authorizationUrl: string }> {
  const res = await apiFetch("/v1/calendar/connect", idToken, { method: "POST" });
  if (!res.ok) throw new Error(`Couldn't start calendar connection (error ${res.status}).`);
  return res.json();
}

export async function disconnectCalendar(idToken: string | null): Promise<void> {
  const res = await apiFetch("/v1/calendar/disconnect", idToken, { method: "POST" });
  if (!res.ok) throw new Error(`Couldn't disconnect calendar (error ${res.status}).`);
}

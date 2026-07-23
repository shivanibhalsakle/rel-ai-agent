const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Calls the backend with the given Firebase ID token attached as a Bearer token. */
export async function apiFetch(
  path: string,
  idToken: string | null,
  init: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (idToken) headers.set("Authorization", `Bearer ${idToken}`);
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}

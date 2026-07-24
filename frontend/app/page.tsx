"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api-client";

export default function HomePage() {
  const { user, loading, signInWithGoogle, signOut, getIdToken } = useAuth();
  const [backendResult, setBackendResult] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function checkBackend() {
    setChecking(true);
    setBackendResult(null);
    try {
      const idToken = await getIdToken();
      const res = await apiFetch("/v1/me", idToken);
      const body = await res.json();
      setBackendResult(res.ok ? JSON.stringify(body) : `Error ${res.status}: ${JSON.stringify(body)}`);
    } catch (err) {
      setBackendResult(`Request failed: ${(err as Error).message}`);
    } finally {
      setChecking(false);
    }
  }

  async function copyIdToken() {
    const idToken = await getIdToken();
    if (!idToken) return;
    await navigator.clipboard.writeText(idToken);
    setBackendResult("ID token copied to clipboard.");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-slate-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-3xl font-semibold">Relocation & Routine Copilot</h1>

      {!user ? (
        <button
          onClick={() => signInWithGoogle()}
          className="rounded-md bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
        >
          Sign in with Google
        </button>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <p className="text-slate-600">Signed in as {user.email}</p>
          <Link
            href="/chat"
            className="rounded-md bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
          >
            Open chat
          </Link>
          <Link
            href="/onboarding"
            className="rounded-md bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
          >
            Set up my preferences
          </Link>
          <Link href="/settings" className="text-sm text-slate-500 underline">
            Edit my preferences
          </Link>
          <button
            onClick={checkBackend}
            disabled={checking}
            className="rounded-md bg-slate-900 px-4 py-2 text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {checking ? "Checking…" : "Verify backend sees my token"}
          </button>
          {backendResult && (
            <p className="max-w-md break-words text-sm text-slate-600">{backendResult}</p>
          )}
          <button onClick={copyIdToken} className="text-sm text-slate-500 underline">
            Copy my ID token (for testing /docs)
          </button>
          <button onClick={() => signOut()} className="text-sm text-slate-500 underline">
            Sign out
          </button>
        </div>
      )}
    </main>
  );
}

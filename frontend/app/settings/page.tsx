"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api-client";
import { fromApiPreferences, PreferencesFormValues, toApiPayload } from "@/lib/preferences";
import { PreferencesForm } from "@/components/preferences-form";

export default function SettingsPage() {
  const { user, loading, getIdToken } = useAuth();
  const router = useRouter();

  const [initialValues, setInitialValues] = useState<PreferencesFormValues | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (loading || !user) return;

    (async () => {
      const idToken = await getIdToken();
      const res = await apiFetch("/v1/preferences", idToken);

      if (res.status === 404) {
        // Nothing saved yet — send them through onboarding instead of an empty settings form.
        router.push("/onboarding");
        return;
      }
      if (!res.ok) {
        setLoadError(`Couldn't load your preferences (error ${res.status}).`);
        return;
      }
      const data = await res.json();
      setInitialValues(fromApiPreferences(data));
    })();
  }, [loading, user, getIdToken, router]);

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

  async function handleSubmit(values: PreferencesFormValues) {
    const idToken = await getIdToken();
    const res = await apiFetch("/v1/preferences", idToken, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toApiPayload(values)),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ? JSON.stringify(detail.detail) : `Error ${res.status}`);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">Your preferences</h1>
        <p className="mt-1 text-sm text-slate-600">Update anything — changes save immediately.</p>
      </div>

      {loadError && <p className="text-sm text-red-600">{loadError}</p>}

      {!initialValues && !loadError && <p className="text-slate-500">Loading your preferences…</p>}

      {initialValues && (
        <PreferencesForm initialValues={initialValues} submitLabel="Save changes" onSubmit={handleSubmit} />
      )}
    </main>
  );
}

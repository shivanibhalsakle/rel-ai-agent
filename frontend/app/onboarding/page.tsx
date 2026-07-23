"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api-client";
import { DEFAULT_PREFERENCES_FORM_VALUES, PreferencesFormValues, toApiPayload } from "@/lib/preferences";
import { PreferencesForm } from "@/components/preferences-form";

export default function OnboardingPage() {
  const { user, loading, getIdToken } = useAuth();
  const router = useRouter();

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
    const res = await apiFetch("/v1/onboarding", idToken, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toApiPayload(values)),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ? JSON.stringify(detail.detail) : `Error ${res.status}`);
    }
    setTimeout(() => router.push("/"), 1200);
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">Tell us how you like to move and work</h1>
        <p className="mt-1 text-sm text-slate-600">
          Skip anything you're not sure about — you can change these anytime in Settings.
        </p>
      </div>
      <PreferencesForm
        initialValues={DEFAULT_PREFERENCES_FORM_VALUES}
        submitLabel="Save preferences"
        onSubmit={handleSubmit}
      />
    </main>
  );
}

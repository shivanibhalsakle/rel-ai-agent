/**
 * Shared shape used by the onboarding and settings forms, plus conversion
 * to/from the API's camelCase UserPreferences JSON (see backend
 * app/schemas/preferences.py). Keeping the form's internal representation
 * (strings for number inputs, etc.) separate from the wire format avoids
 * fighting controlled-input quirks while still round-tripping cleanly.
 */
export interface PreferencesFormValues {
  activities: string[];
  budgetMax: string;
  maxTravelMinutes: string;
  travelMode: string;
  minRating: string;
  workoutTimes: string[];
  wifi: boolean;
  outlets: boolean;
  quiet: boolean;
  indoorOutdoor: "indoor" | "outdoor" | "either";
}

export const DEFAULT_PREFERENCES_FORM_VALUES: PreferencesFormValues = {
  activities: [],
  budgetMax: "",
  maxTravelMinutes: "20",
  travelMode: "walk",
  minRating: "4",
  workoutTimes: [],
  wifi: false,
  outlets: false,
  quiet: false,
  indoorOutdoor: "either",
};

/** Form state -> the JSON body /v1/onboarding and PUT /v1/preferences expect. */
export function toApiPayload(values: PreferencesFormValues) {
  return {
    activities: values.activities,
    budgetBand: values.budgetMax
      ? { min: 0, max: Number(values.budgetMax), currency: "USD", period: "month" as const }
      : null,
    maxTravelMinutes: values.maxTravelMinutes ? Number(values.maxTravelMinutes) : null,
    travelMode: values.travelMode,
    minRating: Number(values.minRating),
    workspaceNeeds: { wifi: values.wifi, outlets: values.outlets, quiet: values.quiet, food: false },
    preferredWorkoutTimes: values.workoutTimes,
    indoorOutdoorPreference: values.indoorOutdoor,
    accessibilityRequirements: [],
  };
}

/** GET /v1/preferences response -> form state, for pre-filling the settings page. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function fromApiPreferences(data: any): PreferencesFormValues {
  return {
    activities: data.activities ?? [],
    budgetMax: data.budgetBand?.max != null ? String(data.budgetBand.max) : "",
    maxTravelMinutes: data.maxTravelMinutes != null ? String(data.maxTravelMinutes) : "",
    travelMode: data.travelMode ?? "walk",
    minRating: data.minRating != null ? String(data.minRating) : "4",
    workoutTimes: data.preferredWorkoutTimes ?? [],
    wifi: data.workspaceNeeds?.wifi ?? false,
    outlets: data.workspaceNeeds?.outlets ?? false,
    quiet: data.workspaceNeeds?.quiet ?? false,
    indoorOutdoor: data.indoorOutdoorPreference ?? "either",
  };
}

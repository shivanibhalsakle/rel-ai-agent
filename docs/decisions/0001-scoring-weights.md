# 0001 — Deterministic scoring weights (Milestone 3)

**Status:** Accepted for MVP. Expect to revisit once real usage/feedback data exists
(see design doc Milestone 7 — feedback-driven weight adjustment).

## Why this doc exists

Milestone 3's completion criteria requires "documented weight rationale" alongside
unit test coverage. This is that document — one place that explains *why* each
scoring module weighs what it weighs, so a future change to a weight is a
deliberate decision against a written rationale, not a guess. All weights below
are also unit-tested for correct relative behavior (see `backend/tests/unit/`).

## Shared mechanics (`app/scoring/base.py`)

Every module produces a `ScoredResult`: a 0–100 `total_score` plus a list of
`ScoreComponent`s (factor, 0–1 normalized score, weight, human-readable detail).
Components are combined with a weighted average, so weights are plain, readable
numbers (not fractions that must sum to 1) — a component with weight 4 matters
roughly twice as much as one with weight 2, regardless of what else is present.

A component is only added when the underlying data is actually known. Missing
data means the factor is skipped, not scored as neutral/0.5 or penalized as
if-missing-means-bad — this matters because several data sources (workspace
amenities, route road-exposure, optional weather fields) are genuinely
unavailable a lot of the time, and the project's stated principle (design doc,
"Data limitations to design around") is to mark things unavailable rather than
invent or silently omit them.

## fitness_scoring

| Factor | Weight | Source | Rationale |
|---|---|---|---|
| Rating | 2.0 (fixed) | `PlaceCandidate.rating` | No "rating importance" slider exists in `UserPreferences` yet, so this is a flat baseline rather than a user-tunable weight — a candidate for a future preference field. |
| Review count | `importance.reviewCount` (1–5) | `PlaceCandidate.userRatingCount` | User-tunable directly via the onboarding form. Capped normalization at 500 reviews so one mega-gym with thousands of reviews doesn't dominate every comparison. |
| Distance | `importance.distance` (1–5) | caller-supplied `travelMinutes` | User-tunable. Not computed by this module (no network calls in scoring) — the caller (eventually the M4 agent) supplies travel times it already fetched from RouteProvider. |
| Affordability | `importance.affordability` (1–5) | `PlaceCandidate.priceLevel` | User-tunable. Approximates budget fit using Google's categorical price level, **not** a dollar comparison against `budgetBand` — Places doesn't return exact prices for fitness venues. Documented limitation, not silently assumed precise. |
| Setting (indoor/outdoor) | 1.0 (fixed) | `PlaceCandidate.types` vs. `indoorOutdoorPreference` | Small fixed bonus, only applied when the user expressed a preference AND the candidate's `types` give a recognizable signal. Absence of signal doesn't penalize. |

Candidates below `minRating` (or with no rating at all) are excluded before
scoring, not scored low — a missing rating is missing information, not a bad one.

## workspace_scoring

Same rating/review-count/distance/affordability treatment as fitness_scoring
(same weights, same rationale). The one addition:

| Factor | Weight | Source | Rationale |
|---|---|---|---|
| Amenity match (wifi/outlets/quiet/food) | 1.5 (fixed) per matched need | caller-supplied `amenities` dict | Only scored for needs the user explicitly turned ON, and only when real data is known for that place. **Known MVP gap:** `PlaceCandidate` doesn't carry these fields — Google's Places API only exposes them via a paid per-place Details fetch. This module is ready to score real data the moment that's wired up (Milestone 4), but scores nothing extra until then. See `app/scoring/review_signals.py` for a zero-marginal-cost alternative: scanning review text (once fetched) for amenity keywords, rather than paying for Google's structured atmosphere fields. |

## route_scoring

| Factor | Weight | Rationale |
|---|---|---|
| Distance-to-target | 4.0 | Usually the most literal thing a user asked for ("a 3 mile route") — weighted highest. |
| Duration-to-target | 3.0 | Same idea for "a 30 minute run." Distance and duration targets are scored independently; a request typically supplies one, not both. |
| Park coverage | 2.0 | Design doc Step 3.3: routes should be biased toward parks/green space where possible. |
| Road exposure | 3.0 | Weighted close to the target-accuracy factors deliberately — lower-traffic routing is a core differentiator, not an afterthought. **Explicitly never described as "safe"** — detail text always reads "lower-traffic based on available data ... not a safety guarantee," per the design doc's risk log on liability language. Unit-tested directly (`test_road_exposure_detail_never_claims_safety`). |
| Weather comfort | 2.0 | Optional, supplied by `weather_scoring` for the route's time window — kept as a separate module rather than duplicated, since "how comfortable is this weather" is identical logic to the weather-aware-scheduling flow (Step 3.5). |

Park coverage and road exposure aren't things RouteProvider returns — they're
heuristic ratios Milestone 6's route-generation step estimates from waypoint
biasing. The two are handled differently, revised once M6 actually built that
step and confronted what data is real: park coverage defaults to 0.0 and is
always shown, because M6's candidate generation always produces a genuine,
determined value for it (a candidate really was or wasn't routed through a
known park). Road exposure has no real data source at all yet (Routes API's
field mask has no road-classification data) — its ratio is `float | None`,
and the component is skipped entirely when `None` rather than defaulted to
0.0 and displayed, since showing "100% estimated non-major roads" with zero
actual signal behind it would be fabricating a favorable estimate, not
just omitting an unknown one. Originally this doc said both default to 0.0
and are always shown — that was written before M6 existed to check the claim
against, and turned out to be wrong for road exposure specifically.

## weather_scoring

| Factor | Weight | Rationale |
|---|---|---|
| Precipitation chance | 4.0 | Weighted highest — rain is the single biggest factor in whether an outdoor plan actually happens. |
| Temperature comfort | 3.0 | Full score inside a 12–24°C band, tapering to 0 at −5°C/35°C. A comfort band, not a personal preference — there's no per-user temperature preference field yet. |
| Wind | 1.5 | Minor discomfort factor relative to rain/temperature. Not unit-converted (see module docstring) — a documented simplification, not a precision claim. |
| Humidity | 1.0 | Minor factor. |
| UV index | 1.0 | Minor factor. |
| Daylight | 1.0 | After-dark hours score 0.5, not 0 — night runs are a legitimate preference, not automatically bad, so this is a mild nudge rather than an exclusion. |

This module doesn't read `UserPreferences` at all yet (the parameter exists only
for call-signature consistency with the other three modules) — weather comfort
is scored as a roughly objective property of the hour, since no personal
temperature/wind preference field exists in the schema today.

## Explicit non-goals for this pass

- No weight here has been tuned against real usage data — they're reasoned
  defaults, and Milestone 7 (feedback-driven adjustment) is where they start
  moving based on actual accept/reject behavior.
- Weights are not currently normalized to sum to any particular total within a
  module — `weighted_average()` normalizes by whatever weights are actually
  present per candidate, so this is intentional, not an oversight.

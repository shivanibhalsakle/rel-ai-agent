"""
Deterministic (not ML) preference-weight adjustment from feedback history
(design doc Milestone 7: "implicit preference weight adjustment based on
the feedback collection"). Pure function, no Firestore, no I/O -- same
"ranking-adjacent logic stays testable without external services" pattern
as every other module in app/scoring/.

Scope: only fitness/workspace feedback is ever considered here. Those are
the only two domains whose scoring reads UserPreferences.importance at
all -- fitness_scoring.py/workspace_scoring.py's own ScoreComponent
factor names ("review_count", "distance", "affordability") map 1:1 onto
Importance's three fields. route_scoring/weather_scoring use fixed
module-level weight constants, not anything from UserPreferences, so
there is nothing here for route/weather feedback to adjust -- it's
silently skipped, not mishandled.

Rule, deliberately simple and explainable rather than a learned model:
for each of the three adjustable factors, count how many of the user's
recent REJECTED items had that factor as their single weakest scored
component (the thing most likely to have driven the rejection), and how
many recent ACCEPTED items had it as their strongest (most likely to have
driven the acceptance). Both directions point the same way -- "this
factor matters to this user" -- so both nudge the same factor's weight
up, never down: this module only ever increases an importance weight,
never decreases one. A deterministic, small-sample-safe rule for "this
clearly matters more than assumed" is easy to state; a correspondingly
safe rule for "this matters less than assumed" is not (rejecting an item
for reasons unrelated to any scored factor at all -- e.g. it was simply
the wrong activity -- would produce a false "this factor doesn't matter"
signal), so decreases are out of scope for this milestone rather than
built on shaky ground.

Overcorrection guard (design doc's own named risk): a factor only moves
once ADJUSTMENT_THRESHOLD same-direction events show up in the recent
window (list_recent_feedback's bounded, newest-first slice) -- a single
reject never moves anything. The computed delta is also NOT accumulated
across repeated recomputes: every call to compute_adjustment is a pure
function of whatever feedback window it's given, so recomputing it twice
on an unchanged window yields the identical result rather than the
adjustment silently compounding over time. apply_adjustment additionally
clamps to Importance's own [1, 5] schema bound.
"""
from collections import defaultdict

from pydantic import Field

from app.schemas.preferences import CamelModel, Importance

ADJUSTMENT_THRESHOLD = 3
MAX_IMPORTANCE = 5
ADJUSTABLE_FACTORS = ("affordability", "review_count", "distance")
_ADJUSTABLE_INTENTS = ("fitness", "workspace")

_FACTOR_LABELS = {
    "affordability": "affordability",
    "review_count": "review count",
    "distance": "distance",
}


class InferredAdjustment(CamelModel):
    """importance_delta is always >= 0 per factor (see module docstring on
    why this never decreases a weight). reasons is a short, human-readable
    explanation per factor that moved -- exactly what the "why we think
    this" settings panel (M7.6) shows. A CamelModel (not a plain
    dataclass) so it round-trips through Firestore and the API response
    the same way every other schema in this codebase does, with no
    separate conversion layer."""

    importance_delta: dict[str, int] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.importance_delta


def compute_adjustment(feedback_records: list[dict]) -> InferredAdjustment:
    """`feedback_records` is the raw dict shape list_recent_feedback
    returns (camelCase keys, as stored) -- intentionally not re-validated
    through FeedbackRecord here, since this only reads a few specific
    keys and doesn't need the full model round-trip."""
    weakest_reject_counts: dict[str, int] = defaultdict(int)
    strongest_accept_counts: dict[str, int] = defaultdict(int)

    for record in feedback_records:
        if record.get("intent") not in _ADJUSTABLE_INTENTS:
            continue

        breakdown = record.get("scoreBreakdown") or {}
        adjustable = {k: v for k, v in breakdown.items() if k in ADJUSTABLE_FACTORS}
        if not adjustable:
            continue

        action = record.get("action")
        if action == "rejected":
            weakest = min(adjustable, key=adjustable.get)
            weakest_reject_counts[weakest] += 1
        elif action == "accepted":
            strongest = max(adjustable, key=adjustable.get)
            strongest_accept_counts[strongest] += 1

    delta: dict[str, int] = {}
    reasons: list[str] = []
    for factor in ADJUSTABLE_FACTORS:
        label = _FACTOR_LABELS[factor]
        bump = 0

        reject_hits = weakest_reject_counts.get(factor, 0)
        if reject_hits >= ADJUSTMENT_THRESHOLD:
            bump += 1
            reasons.append(
                f"You've rejected {reject_hits} recent options that scored low on {label} "
                f"— weighting it more heavily."
            )

        accept_hits = strongest_accept_counts.get(factor, 0)
        if accept_hits >= ADJUSTMENT_THRESHOLD:
            bump += 1
            reasons.append(
                f"You've accepted {accept_hits} recent options that scored especially well on {label} "
                f"— weighting it more heavily."
            )

        if bump:
            delta[factor] = bump

    return InferredAdjustment(importance_delta=delta, reasons=reasons)


def apply_adjustment(base: Importance, delta: dict[str, int]) -> Importance:
    """Applies a delta on top of the EXPLICIT importance sliders (what the
    user actually set in onboarding/settings), clamped to Importance's own
    [1, 5] bound. Never mutates `base` -- returns a new Importance, since
    the explicit profile this was computed from must stay untouched (see
    preference_repository.py's separate explicit/inferred docs, M7.4)."""
    if not delta:
        return base
    updates = {factor: min(MAX_IMPORTANCE, getattr(base, factor) + bump) for factor, bump in delta.items()}
    return base.model_copy(update=updates)

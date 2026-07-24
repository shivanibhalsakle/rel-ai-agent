"""
Shared scoring primitives used by every *_scoring module (fitness, workspace,
route, weather). Keeping this common means every domain produces the same
shape of output — a 0-100 score plus a transparent breakdown of what drove
it — so the frontend can render "why we recommend this" consistently, and
tests can assert on ranking order the same way across all four domains.

Deliberately pure Python / pydantic only — no I/O, no provider calls, no LLM.
That's the point of Milestone 3: ranking logic that's fully deterministic and
testable on its own.
"""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def clamp01(value: float) -> float:
    """Clamp a value into [0, 1]. Scoring math can overshoot (e.g. a rating
    slightly above the assumed max) — clamping keeps every component
    comparable regardless of how its normalize() call was set up."""
    return max(0.0, min(1.0, value))


def normalize(value: float, low: float, high: float, invert: bool = False) -> float:
    """Linearly map `value` from [low, high] to a [0, 1] score, clamped at
    both ends.

    invert=True flips the direction — use it for factors where *lower* raw
    values are better (e.g. distance, wait time). Without inversion, higher
    raw values score higher (e.g. rating, review count).

    If low == high (a degenerate range, e.g. every candidate has the same
    value), everything scores 1.0 rather than dividing by zero — a factor
    that doesn't vary across candidates shouldn't be the thing that zeroes
    someone out.
    """
    if high == low:
        return 1.0
    score = (value - low) / (high - low)
    score = clamp01(score)
    return 1 - score if invert else score


class ScoreComponent(BaseModel):
    """One factor that fed into a total score (e.g. "rating", "distance").
    `score` is always normalized to [0, 1] so components stay comparable
    across factors with very different raw units (stars vs. meters vs.
    minutes). `detail` is the human-readable reason shown to the user."""

    factor: str
    score: float = Field(ge=0, le=1)
    weight: float = Field(ge=0)
    detail: str


class ScoredResult(BaseModel, Generic[T]):
    """A candidate item plus its computed score. Generic over the candidate
    type so the same model serves PlaceCandidate, RouteResult, and
    HourlyForecast without duplication."""

    item: T
    total_score: float = Field(ge=0, le=100)
    components: list[ScoreComponent]

    @property
    def explanation(self) -> list[str]:
        """Human-readable reasons, ordered by how much each factor
        contributed (weight * score) — the biggest driver of the score
        comes first, which is what a "why we recommend this" UI wants."""
        ordered = sorted(self.components, key=lambda c: c.weight * c.score, reverse=True)
        return [c.detail for c in ordered]


def weighted_average(components: list[ScoreComponent]) -> float:
    """Combine components into a single [0, 1] score via weighted average.
    Weights don't need to sum to 1 — they're normalized here — so each
    scoring module can express weights as plain, readable numbers (e.g.
    rating=3, distance=2, budget=1) instead of fractions that must add up."""
    total_weight = sum(c.weight for c in components)
    if total_weight <= 0:
        return 0.0
    return sum(c.score * c.weight for c in components) / total_weight


def to_scored_result(item: T, components: list[ScoreComponent]) -> ScoredResult[T]:
    """Build a ScoredResult from an item and its components, converting the
    [0, 1] weighted average into the [0, 100] scale used in total_score."""
    return ScoredResult[T](
        item=item,
        total_score=round(weighted_average(components) * 100, 1),
        components=components,
    )


def rank(results: list[ScoredResult[T]]) -> list[ScoredResult[T]]:
    """Sort scored results highest-first. A separate function (not baked
    into to_scored_result) so callers can score a batch, then rank, without
    re-sorting on every single insert."""
    return sorted(results, key=lambda r: r.total_score, reverse=True)

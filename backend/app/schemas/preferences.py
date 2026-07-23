"""
Preference schemas. Field names are camelCase on the wire (matching the
Firestore document shape from the design doc and what the frontend sends),
snake_case internally in Python — Pydantic's alias handling bridges the two.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(snake: str) -> str:
    first, *rest = snake.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class BudgetBand(CamelModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)
    currency: str = "USD"
    period: Literal["month", "class"] = "month"


class Importance(CamelModel):
    affordability: int = Field(default=3, ge=1, le=5)
    review_count: int = Field(default=3, ge=1, le=5)
    distance: int = Field(default=3, ge=1, le=5)


class WorkspaceNeeds(CamelModel):
    wifi: bool = False
    outlets: bool = False
    quiet: bool = False
    food: bool = False


class UserPreferences(CamelModel):
    """Matches users/{userId}/preferences/profile in Firestore (see design doc, Step 6)."""

    activities: list[str] = Field(default_factory=list)
    budget_band: BudgetBand | None = None
    max_travel_minutes: int | None = Field(default=None, ge=0)
    travel_mode: Literal["walk", "bike", "transit", "drive"] = "walk"
    min_rating: float = Field(default=0, ge=0, le=5)
    importance: Importance = Field(default_factory=Importance)
    workspace_needs: WorkspaceNeeds = Field(default_factory=WorkspaceNeeds)
    preferred_workout_times: list[str] = Field(default_factory=list)
    indoor_outdoor_preference: Literal["indoor", "outdoor", "either"] = "either"
    accessibility_requirements: list[str] = Field(default_factory=list)


class OnboardingRequest(UserPreferences):
    """What the onboarding form submits. Same shape as UserPreferences for now —
    kept as a separate type since the two are conceptually different requests
    (initial creation vs. later reads) and are likely to diverge later."""

    pass

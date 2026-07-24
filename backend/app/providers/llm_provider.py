"""
Wraps Anthropic's Messages API (Claude). Used directly by the agent's
Claude-backed nodes (understand_request, ask_user, generate_explanation —
Milestone 4). LLMProvider IS the abstraction layer here, the same pattern as
PlacesProvider/WeatherProvider/RouteProvider wrapping their respective
Google APIs directly — no extra framework (e.g. langchain-anthropic) sits
between this code and the API; see requirements.txt for why.

Defaults to Haiku 4.5 — the cheapest current model ($1 / $5 per million
input/output tokens, per rates checked in July 2026) — because every Claude
call this agent makes is intentionally narrow by design (design doc, Step 4:
"Claude handles... judgment/language understanding... every deterministic
step is plain Python"). Intent classification, slot extraction, and turning
already-computed scores into a sentence don't need a larger model. The model
is a constructor parameter, not hardcoded, so upgrading a specific call site
later is a one-line change.
"""
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.core.config import get_settings

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 1024

T = TypeVar("T", bound=BaseModel)


class LLMProvider:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        settings = get_settings()
        self._api_key = api_key or settings.anthropic_api_key
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def generate_structured(
        self,
        *,
        system: str,
        user_message: str,
        output_model: type[T],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> T:
        """Call Claude and get back a validated instance of `output_model`
        directly — no manual JSON parsing or retry-on-malformed-output loop.
        Uses Anthropic's structured-outputs feature (constrained decoding):
        the response is guaranteed to match the schema, not just usually
        close to it. This is what understand_request uses for intent
        classification + slot extraction (design doc: "Structured output
        (function-calling schema), not free text")."""
        response = await self._client.messages.parse(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            output_format=output_model,
        )
        return response.parsed_output

    async def generate_text(
        self,
        *,
        system: str,
        user_message: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        """Plain free-text generation — for ask_user's clarifying questions
        and generate_explanation's natural-language summaries, where the
        point is well-written prose, not a schema."""
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

"""
Manual verification for M4.2 — makes two REAL, paid calls to the Claude API
(unlike verify_scoring.py, which is pure/free). Both calls are small and
cheap (Haiku 4.5, short prompts, low max_tokens) — expect a fraction of a
cent total, and the script prints Anthropic's own token counts so you can
see exactly what you were charged for rather than trusting an estimate.

Usage (from backend/, with the venv activated, ANTHROPIC_API_KEY set):
    python -m scripts.verify_llm_provider
"""
import asyncio

from pydantic import BaseModel

from app.providers.llm_provider import LLMProvider


class DemoExtraction(BaseModel):
    """Deliberately similar to what understand_request (M4.3) will do —
    this previews that node's job: turning free text into structured
    slots, not just proving the API connection works."""

    activity: str
    max_budget_usd: float | None = None


async def main() -> None:
    llm = LLMProvider()

    print("=== generate_text ===")
    text = await llm.generate_text(
        system="You are a terse assistant. Reply in one short sentence.",
        user_message="Say hello and confirm you're working.",
    )
    print(text)

    print("\n=== generate_structured ===")
    extraction = await llm.generate_structured(
        system="Extract the requested fitness activity and budget from the user's message.",
        user_message="I'm looking for a yoga studio under $80 a month.",
        output_model=DemoExtraction,
    )
    print(extraction.model_dump_json(indent=2))

    print("\nIf both sections above printed real output with no errors, ")
    print("the API key and LLMProvider wrapper are working end to end.")


if __name__ == "__main__":
    asyncio.run(main())

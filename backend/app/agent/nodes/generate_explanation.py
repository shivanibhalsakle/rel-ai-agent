"""
generate_explanation node (design doc Step 4) — Claude reasons over the
already-computed, deterministic scores (M3) and phrases each one as a
natural sentence. Does NOT compute or invent facts — every detail in the
prompt comes straight from ScoredResult's own deterministic breakdown
(M3's ScoreComponent.detail strings via .explanation), matching the design
doc's explicit rule: "reasoning over given facts, not inventing new ones."

One Claude call per turn, not one per recommendation — batches all
top-ranked items into a single structured-output request. A separate call
per item would multiply cost and latency for no real benefit (design doc's
own "Latency stacking" risk) and eat into the tool-call budget for no
reason.

Also handles "general" intent (no search happened, nothing to score) by
generating a direct conversational reply into the singular `explanation`
field instead — the one case where a single overall string, not a per-item
dict, is the right shape (see state.py for why both fields exist).

Display name and dict key used to be `getattr(item, "name"/"place_id", ...)`
directly -- fine when fitness/workspace's PlaceCandidate was the only item
type this ever saw. M6 added route_scoring/weather_scoring results
(RouteCandidate has no `name`, only `label`; HourlyForecast has neither),
so both now go through app.scoring.base's item_display_name()/item_id(),
shared with the /v1/chat response layer so an item is identified the same
way in both places.
"""
from pydantic import BaseModel

from app.agent.state import AgentState
from app.providers.llm_provider import LLMProvider
from app.scoring.base import item_display_name, item_id

TOP_N_EXPLANATIONS = 5
# ^ only the results a UI would actually surface get an LLM-written
# sentence -- the rest still have M3's deterministic ScoredResult.explanation
# available if ever needed, just not further phrased by Claude. Keeps this
# node to one bounded call regardless of how many candidates were scored.

EXPLANATION_SYSTEM_PROMPT = """You turn a ranked list of already-scored \
recommendations into short, natural sentences. For each item you're given \
its name and the factual reasons behind its score, ordered by how much \
each one mattered. Write ONE short sentence per item using ONLY those \
facts — do not add ratings, prices, distances, or any other detail that \
wasn't given to you. Return exactly one explanation per item, in the same \
order they were given."""

GENERAL_REPLY_SYSTEM_PROMPT = """You are a relocation and routine copilot. \
Reply briefly and helpfully to the user's message. You have no search \
results for this turn — do not claim to have found or recommended \
anything specific."""


class _ExplanationBatch(BaseModel):
    explanations: list[str]


async def generate_explanation(state: AgentState, llm: LLMProvider | None = None) -> dict:
    llm = llm or LLMProvider()

    if state["intent"] == "general":
        last_message = state["messages"][-1].content if state["messages"] else ""
        reply = await llm.generate_text(
            system=GENERAL_REPLY_SYSTEM_PROMPT,
            user_message=last_message,
            max_tokens=200,
        )
        return {"explanation": reply}

    top_results = state.get("scored_results", [])[:TOP_N_EXPLANATIONS]
    if not top_results:
        # Reached with nothing to explain and an unresolved error means the
        # search pipeline degraded (geocoding/search failed and gave up
        # retrying, see handle_provider_error) rather than legitimately
        # finding zero results -- say so honestly instead of silently
        # returning nothing, which is what a graph wiring bug looks like
        # from the user's side.
        errors = state.get("errors", [])
        if errors:
            return {"explanation": f"I couldn't complete that search: {errors[-1]['message']}"}
        return {"explanations": {}}

    item_descriptions = []
    for result in top_results:
        name = item_display_name(result.item)
        facts = "; ".join(result.explanation)
        item_descriptions.append(f"- {name}: {facts}")

    batch = await llm.generate_structured(
        system=EXPLANATION_SYSTEM_PROMPT,
        user_message="\n".join(item_descriptions),
        output_model=_ExplanationBatch,
    )

    # zip() truncates to the shorter list if Claude returns a different
    # count than requested -- some items simply won't get a sentence
    # rather than the node crashing on a mismatch.
    explanations: dict[str, str] = {}
    for result, sentence in zip(top_results, batch.explanations):
        explanations[item_id(result.item)] = sentence

    return {"explanations": explanations}

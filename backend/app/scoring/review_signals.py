"""
Turns raw review text into amenity signals (wifi / outlets / quiet) by
keyword matching, with basic negation handling ("no wifi" shouldn't count
as a positive wifi mention).

This is deliberately the cheap half of the review-mining feature: it takes
review strings you already have and does pure-Python text scanning, no API
calls, no LLM. Actually *fetching* review text costs money — Google's Places
API only exposes `reviews` via Place Details (New), and requesting that
field triggers the Enterprise + Atmosphere SKU ($40 / 1,000 calls as of the
rates checked in July 2026 — the most expensive Places tier there is). That
live fetch is deliberately NOT wired up yet. It belongs in Milestone 4,
where the agent's tool-call budget enforcement can restrict it to a handful
of already-shortlisted candidates instead of running on every raw search
result. Until then, this module works on whatever review text a caller
supplies (real, once M4 exists, or hand-written in tests today).

Known limitation: negation detection is a simple "does a negation word
appear shortly before the keyword" check, not real NLP. It will miss
indirect phrasing ("wifi was down the whole time") and could misfire on
unusual sentence structure. Good enough for a first signal; revisit if it
proves unreliable against real review data.
"""
import re

from pydantic import BaseModel, Field

_POSITIVE_KEYWORDS: dict[str, list[str]] = {
    "wifi": ["wifi", "wi-fi", "internet"],
    "outlets": ["outlet", "outlets", "charging port", "charging ports", "power outlet", "plug"],
    "quiet": ["quiet", "peaceful", "calm"],
}

# Words that directly signal the *absence* of an amenity even without a
# negation word nearby (e.g. "noisy" already means "not quiet").
_NEGATIVE_SIGNAL_KEYWORDS: dict[str, list[str]] = {
    "quiet": ["noisy", "loud"],
}

_NEGATION_PATTERNS = ["no ", "not ", "without ", "n't have", "n't ", "lack of", "lacking"]
_NEGATION_WINDOW_CHARS = 15
_MAX_SAMPLE_QUOTES = 2
_MAX_QUOTE_LENGTH = 140


class AmenitySignal(BaseModel):
    amenity: str
    present: bool
    mention_count: int = Field(ge=0)
    negative_mention_count: int = Field(ge=0)
    sample_quotes: list[str] = Field(default_factory=list)


def _has_negation_before(text: str, match_start: int) -> bool:
    window_start = max(0, match_start - _NEGATION_WINDOW_CHARS)
    window = text[window_start:match_start]
    return any(pattern in window for pattern in _NEGATION_PATTERNS)


def _extract_sentence(text: str, match_start: int, match_end: int) -> str:
    """Grab the sentence containing the match, for use as a sample quote."""
    sentence_start = max(text.rfind(".", 0, match_start), text.rfind("!", 0, match_start), text.rfind("?", 0, match_start))
    sentence_start = sentence_start + 1 if sentence_start != -1 else 0
    sentence_end_candidates = [i for i in (text.find(".", match_end), text.find("!", match_end), text.find("?", match_end)) if i != -1]
    sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(text)
    quote = text[sentence_start:sentence_end].strip()
    if len(quote) > _MAX_QUOTE_LENGTH:
        quote = quote[:_MAX_QUOTE_LENGTH].rstrip() + "..."
    return quote


def extract_amenity_signals(review_texts: list[str]) -> dict[str, AmenitySignal]:
    """Scan a list of raw review strings for amenity mentions.

    Only amenities with at least one mention (positive or negative) appear
    in the returned dict — no mentions means no signal, which callers
    should treat the same as "we don't know" (see workspace_scoring, which
    already skips amenities missing from its `amenities` argument).

    `present` is a simple majority rule: True if positive mentions outnumber
    negative ones. Ties (including 0-0, which can't happen since the
    amenity wouldn't be in the dict) favor absence.
    """
    counts: dict[str, dict[str, int]] = {name: {"pos": 0, "neg": 0} for name in _POSITIVE_KEYWORDS}
    quotes: dict[str, list[str]] = {name: [] for name in _POSITIVE_KEYWORDS}

    for raw_text in review_texts:
        text = raw_text.lower()
        original = raw_text

        for amenity, keywords in _POSITIVE_KEYWORDS.items():
            for keyword in keywords:
                for match in re.finditer(re.escape(keyword), text):
                    if _has_negation_before(text, match.start()):
                        counts[amenity]["neg"] += 1
                    else:
                        counts[amenity]["pos"] += 1
                        if len(quotes[amenity]) < _MAX_SAMPLE_QUOTES:
                            quote = _extract_sentence(original, match.start(), match.end())
                            if quote and quote not in quotes[amenity]:
                                quotes[amenity].append(quote)

        for amenity, keywords in _NEGATIVE_SIGNAL_KEYWORDS.items():
            for keyword in keywords:
                for match in re.finditer(re.escape(keyword), text):
                    counts[amenity]["neg"] += 1
                    if len(quotes[amenity]) < _MAX_SAMPLE_QUOTES:
                        quote = _extract_sentence(original, match.start(), match.end())
                        if quote and quote not in quotes[amenity]:
                            quotes[amenity].append(quote)

    signals: dict[str, AmenitySignal] = {}
    for amenity, tally in counts.items():
        total = tally["pos"] + tally["neg"]
        if total == 0:
            continue
        signals[amenity] = AmenitySignal(
            amenity=amenity,
            present=tally["pos"] > tally["neg"],
            mention_count=tally["pos"],
            negative_mention_count=tally["neg"],
            sample_quotes=quotes[amenity],
        )

    return signals


def to_amenities_bool(signals: dict[str, AmenitySignal]) -> dict[str, bool]:
    """Convert to the plain {amenity: bool} shape workspace_scoring's
    `amenities` parameter expects, e.g. amenities={place_id: to_amenities_bool(signals)}."""
    return {amenity: signal.present for amenity, signal in signals.items()}

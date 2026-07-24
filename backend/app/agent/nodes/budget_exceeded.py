"""
budget_exceeded node — where the graph routes when is_within_budget (M4.8)
says no. Design doc: "short-circuits to a 'narrow your request' response
instead of looping." Fixed message, no Claude call needed.
"""
from app.agent.state import AgentState


def budget_exceeded(state: AgentState) -> dict:
    return {
        "explanation": (
            "That's a lot of searching for one turn — try narrowing your request "
            "(a more specific activity or location) and I'll take another look."
        )
    }

"""
ask_user (design doc Step 4) — implemented as two nodes instead of the
design doc's single node, on purpose.

LangGraph re-runs a node's body from the top every time it resumes from an
interrupt (see LangGraph docs: "the runtime restarts the entire node from
the beginning... any code that ran before interrupt() will execute again").
A single node that calls Claude to phrase a question AND THEN calls
interrupt() would re-run that Claude call on every resume, wasting a call
each time. LangGraph's own guidance is to separate side effects into their
own node so the interrupt-calling node has nothing before it to re-run:

  generate_clarifying_question  -- the Claude call, appends the question
                                    to `messages` (a real side effect)
  ask_user                      -- pure interrupt, no side effects before
                                    it, safe to re-run on resume

Both are needed on the graph's missing-info branch; see agent/graph.py
(M4.9) for how they're wired together.
"""
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt

from app.agent.state import AgentState
from app.providers.llm_provider import LLMProvider

CLARIFYING_QUESTION_SYSTEM_PROMPT = """You are a relocation and routine copilot. \
The user's request is missing information needed to help them. Ask ONE short, \
specific, friendly question about the single most important missing field. \
Do not ask about more than one thing at a time. Do not repeat information \
the user already gave you."""

# Plain-language description of each field check_missing_info can name, so
# the clarifying-question prompt reads naturally instead of echoing an
# internal field name like "activities" at the user.
_FIELD_DESCRIPTIONS = {
    "intent": (
        "what kind of help they're looking for -- a gym/fitness place, a workspace "
        "(cafe/coworking), a running or walking route, or weather-based scheduling advice"
    ),
    "activities": "what specific activity or type of fitness place they want (e.g. gym, yoga, running)",
    "location": "what city, neighborhood, or address they'd like to search near",
}


async def generate_clarifying_question(state: AgentState, llm: LLMProvider | None = None) -> dict:
    llm = llm or LLMProvider()
    missing_field = state["missing_fields"][0]
    field_description = _FIELD_DESCRIPTIONS.get(missing_field, missing_field)

    question = await llm.generate_text(
        system=CLARIFYING_QUESTION_SYSTEM_PROMPT,
        user_message=f"Ask the user about: {field_description}.",
        max_tokens=100,
    )
    return {"messages": [AIMessage(content=question)]}


def ask_user(state: AgentState) -> dict:
    """Pure interrupt -- no side effects before it, so a resume never
    re-triggers a Claude call (see module docstring). Not unit-tested in
    isolation: interrupt() only behaves correctly inside a real LangGraph
    run (it needs the runtime's task-local context to pause/resume
    correctly), so this node is covered by the M4.11 integration tests
    once the graph exists, not here."""
    question = state["messages"][-1].content
    answer = interrupt(question)
    return {"messages": [HumanMessage(content=answer)]}

"""agt_architect - Unified AI Architect Agent.

Single entry point with dual responsibilities:
1. Answer architecture questions directly
2. Review solution submissions via the review board (called as a tool)

The root agent triages incoming messages. For questions it answers directly.
For solution submissions it calls the run_review tool which runs the full
parallel review pipeline internally.
"""

import os
import warnings
from functools import lru_cache

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.models.lite_llm import LiteLlm

from .tools import RunReviewTool

# Pick up OPENROUTER_API_KEY etc. from agt_architect/.env when the agent is
# imported outside the ADK CLI (which loads it on its own).
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

MODEL = os.getenv("AGT_ARCHITECT_MODEL", "openrouter/qwen/qwen3.6-flash")

_PRINCIPLES_DIR = os.path.join(os.path.dirname(__file__), "principles")


@lru_cache(maxsize=None)
def _load_principles(domain: str) -> str:
    with open(os.path.join(_PRINCIPLES_DIR, f"{domain}.md"), encoding="utf-8") as f:
        return f.read()


def _architect(name: str, domain: str, title: str, focus: str) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=LiteLlm(model=MODEL),
        description=f"{title} - reviews solution submissions against {domain} principles.",
        instruction=(
            f"You are the {title} on an architecture review board.\n\n"
            f"{_load_principles(domain)}\n\n"
            "The user's message is a solution submission. Evaluate it against "
            "EVERY principle above, citing concrete evidence from the "
            "submission. If the submission says nothing about a principle, "
            "rate it CONCERN and note the missing information - do not assume "
            "the best or the worst.\n"
            f"{focus}\n"
            "Be specific and constructive: every CONCERN or FAIL must come "
            "with an actionable recommendation."
        ),
        output_key=f"{domain}_review",
    )


application_architect = _architect(
    name="application_architect",
    domain="application",
    title="Application Architect",
    focus="Focus on software design: components, APIs, data ownership, "
    "error handling, observability and testability.",
)

infrastructure_architect = _architect(
    name="infrastructure_architect",
    domain="infrastructure",
    title="Infrastructure Architect",
    focus="Focus on the platform: availability, scalability, security, "
    "networking, disaster recovery, cost and operations.",
)

consolidator = LlmAgent(
    name="consolidator",
    model=LiteLlm(model=MODEL),
    description="Merges the architects' reviews into a single board verdict.",
    instruction=(
        "You are the chief architect chairing the review board.\n\n"
        "Two architects have reviewed the same solution submission.\n\n"
        "Application Architect review:\n{application_review}\n\n"
        "Infrastructure Architect review:\n{infrastructure_review}\n\n"
        "Merge them into one board verdict:\n"
        "- overall_rating: the worst of the two overall ratings (a FAIL "
        "anywhere blocks approval).\n"
        "- summary: one paragraph covering both perspectives.\n"
        "- required_actions: every recommendation tied to a FAIL rating, "
        "deduplicated and phrased as imperatives.\n"
        "- recommendations: notable CONCERN-level improvements, deduplicated.\n"
        "Do not introduce findings that neither architect raised."
    ),
    output_key="verdict",
)

with warnings.catch_warnings():
    # SequentialAgent/ParallelAgent are deprecated in ADK 2.11 but remain the
    # working choice for fan-out/join state passing (see module docstring).
    warnings.simplefilter("ignore", DeprecationWarning)
    review_board = ParallelAgent(
        name="review_board",
        description="Runs the application and infrastructure reviews concurrently.",
        sub_agents=[application_architect, infrastructure_architect],
    )

root_agent = LlmAgent(
    name="agt_architect",
    model=LiteLlm(model=MODEL),
    description=(
        "Unified AI Architect: answers architecture questions directly, "
        "or delegates solution submissions to a review board of Application "
        "and Infrastructure Architects who evaluate against defined principles."
    ),
    instruction=(
        "You are an experienced software architect with two modes:\n\n"
        "MODE 1 - Answer questions: If the user asks an architecture question,\n"
        "answer it directly. Be clear, concise, and practical.\n\n"
        "MODE 2 - Review solutions: If the user submits a solution for evaluation,\n"
        "call the 'run_review' tool with the submission text. It will return\n"
        "Application Architect review, Infrastructure Architect review, and a\n"
        "consolidated verdict. Then summarize the results for the user.\n\n"
        "How to decide:\n"
        "- Questions like 'what is...', 'how do I...', 'explain...' → answer directly\n"
        "- Submissions like 'here is my design...', 'evaluate this...', 'review...' → call run_review\n"
        "- When unsure, ask the user to clarify\n\n"
        "Do NOT attempt to review a submission yourself — always use the tool."
    ),
    tools=[RunReviewTool()],
)

"""Tools for the unified architect agent."""

from __future__ import annotations

import json
import re
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.genai import types


def _parse_json(text: str) -> dict:
    """Strip markdown code fences and parse JSON."""
    cleaned = re.sub(r"```(?:json)?\s*\n?", "", text).strip()
    return json.loads(cleaned)


async def _run_review_pipeline(submission: str) -> dict:
    """Run the full review board pipeline and return structured output."""
    from dotenv import load_dotenv
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from .schemas import Review, Verdict
    from .agent import (
        application_architect,
        infrastructure_architect,
        consolidator,
        review_board,
    )

    svc = InMemorySessionService()
    session = await svc.create_session(app_name="agt_architect", user_id="tool")
    runner = Runner(agent=review_board, app_name="agt_architect", session_service=svc)

    msg = types.Content(role="user", parts=[types.Part.from_text(text=submission)])
    async for event in runner.run_async(user_id="tool", session_id=session.id, new_message=msg):
        pass

    # Now run the consolidator
    runner2 = Runner(agent=consolidator, app_name="agt_architect", session_service=svc)
    async for event in runner2.run_async(user_id="tool", session_id=session.id):
        pass

    final = await svc.get_session(app_name="agt_architect", user_id="tool", session_id=session.id)
    state = final.state if final else {}

    result: dict[str, Any] = {"application_review": {}, "infrastructure_review": {}, "verdict": {}}

    for key, target in (
        ("application_review", result["application_review"]),
        ("infrastructure_review", result["infrastructure_review"]),
    ):
        if key in state:
            try:
                parsed = _parse_json(state[key])
                validated = Review.model_validate(parsed)
                target.update(validated.model_dump())
            except Exception:
                target["raw"] = state[key]

    if "verdict" in state:
        try:
            parsed = _parse_json(state["verdict"])
            validated = Verdict.model_validate(parsed)
            result["verdict"].update(validated.model_dump())
        except Exception:
            result["verdict"]["raw"] = state["verdict"]

    return result


class RunReviewTool(BaseTool):
    """Delegates a solution submission to the architecture review board."""

    def __init__(self):
        super().__init__(
            name="run_review",
            description=(
                "Evaluate a solution submission against architecture principles. "
                "Returns Application Architect review, Infrastructure Architect review, "
                "and a consolidated verdict."
            ),
        )

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "submission": {
                        "type": "string",
                        "description": "The solution design to evaluate.",
                    }
                },
                "required": ["submission"],
            },
        )

    async def run_async(self, *, args: dict[str, Any], **kwargs: Any) -> str:
        submission: str = args.get("submission", "")
        result = await _run_review_pipeline(submission)
        return json.dumps(result, ensure_ascii=False)

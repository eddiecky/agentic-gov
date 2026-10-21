"""Offline tests for the unified architect agent - no API key or network needed."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agt_architect.agent import root_agent
from agt_architect.schemas import Finding, Rating, Review, Verdict
from agt_architect.tools import _parse_json


def test_root_agent_is_named_and_exposed() -> None:
    assert root_agent.name == "agt_architect"


def test_root_agent_has_review_tool() -> None:
    tools = root_agent.tools or []
    tool_names = [t.name for t in tools]
    assert "run_review" in tool_names


def test_review_tool_has_declaration() -> None:
    from agt_architect.tools import RunReviewTool

    tool = RunReviewTool()
    decl = tool._get_declaration()
    assert decl is not None
    assert decl.name == "run_review"
    assert "submission" in decl.parameters_json_schema["properties"]


def test_instruction_mentions_triage_modes() -> None:
    assert "MODE 1" in root_agent.instruction
    assert "MODE 2" in root_agent.instruction
    assert "run_review" in root_agent.instruction


def test_default_model_routes_through_openrouter() -> None:
    assert root_agent.model.model.startswith("openrouter/")


def test_parse_json_strips_markdown_fences() -> None:
    md = "```json\n{\"key\": \"value\"}\n```"
    parsed = _parse_json(md)
    assert parsed == {"key": "value"}

    # Plain JSON without fences also works
    plain = '{"key": "value"}'
    assert _parse_json(plain) == {"key": "value"}


def test_api_parses_markdown_output_into_structured_models() -> None:
    md = "```json\n{\"architect\": \"App\", \"summary\": \"ok\", \"overall_rating\": \"PASS\", \"findings\": []}\n```"
    parsed = _parse_json(md)
    review = Review.model_validate(parsed)
    assert review.architect == "App"
    assert review.overall_rating is Rating.PASS

    # Plain JSON without fences also works
    plain = '{"architect": "Infra", "summary": "x", "overall_rating": "FAIL", "findings": []}'
    parsed2 = _parse_json(plain)
    review2 = Review.model_validate(parsed2)
    assert review2.architect == "Infra"


def _finding(**overrides: object) -> Finding:
    payload = {
        "principle": "Statelessness of services",
        "rating": Rating.CONCERN,
        "observation": "Session state is kept in memory.",
        "recommendation": "Move sessions to a shared cache.",
    }
    return Finding(**(payload | overrides))


def test_review_schema_accepts_a_well_formed_payload() -> None:
    review = Review(
        architect="Application Architect",
        summary="Solid design with some statefulness concerns.",
        overall_rating=Rating.CONCERN,
        findings=[_finding()],
    )
    assert review.findings[0].rating is Rating.CONCERN


def test_review_schema_rejects_a_bad_rating() -> None:
    with pytest.raises(ValidationError):
        _finding(rating="MEH")


def test_review_schema_requires_findings() -> None:
    with pytest.raises(ValidationError):
        Review(
            architect="Application Architect",
            summary="x",
            overall_rating=Rating.PASS,
        )


def test_verdict_schema_accepts_a_well_formed_payload() -> None:
    verdict = Verdict(
        overall_rating=Rating.FAIL,
        summary="Infrastructure gaps block approval.",
        required_actions=["Add automated backups with a tested restore."],
        recommendations=["Consider multi-zone deployment for the cache."],
    )
    assert verdict.overall_rating is Rating.FAIL
    assert verdict.required_actions

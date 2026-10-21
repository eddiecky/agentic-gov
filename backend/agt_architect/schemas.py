"""Structured output schemas for the architecture review pipeline."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Rating(str, Enum):
    """How a finding (or a whole review) judges the submission."""

    PASS = "PASS"
    CONCERN = "CONCERN"
    FAIL = "FAIL"


class Finding(BaseModel):
    """One principle-by-principle observation from an architect's review."""

    principle: str = Field(description="Name of the principle being assessed.")
    rating: Rating
    observation: str = Field(
        description="What the submission does or fails to do for this principle."
    )
    recommendation: str = Field(
        default="",
        description="Concrete change that would raise the rating, if any.",
    )


class Review(BaseModel):
    """A single architect's structured review of a solution submission."""

    architect: str = Field(description="e.g. 'Application Architect'.")
    summary: str = Field(description="One-paragraph overall assessment.")
    overall_rating: Rating
    findings: list[Finding]


class Verdict(BaseModel):
    """The consolidated, board-level decision on the submission."""

    overall_rating: Rating
    summary: str = Field(
        description="One-paragraph merged assessment across all architects."
    )
    required_actions: list[str] = Field(
        description="Changes that MUST be made before the design is approved."
    )
    recommendations: list[str] = Field(
        description="Improvements that are advisable but not blocking."
    )

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RCAAssessment(BaseModel):
    root_cause: str = Field(
        description="Strongest evidence-backed root-cause hypothesis."
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0.",
    )

    evidence: list[str] = Field(
        default_factory=list,
        description="Concrete observations supporting the hypothesis.",
    )

    conflicting_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence that weakens or conflicts with the hypothesis.",
    )

    next_checks: list[str] = Field(
        default_factory=list,
        description="Additional diagnostic checks before remediation.",
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value):
        """
        Normalize model outputs such as:

        0.95  -> 0.95
        95    -> 0.95
        "95"  -> 0.95
        "95%" -> 0.95
        """

        if isinstance(value, str):
            value = value.strip()

            if value.endswith("%"):
                value = value[:-1].strip()

            try:
                value = float(value)
            except ValueError:
                raise ValueError(
                    "confidence must be numeric or a percentage"
                )

        if isinstance(value, (int, float)):
            value = float(value)

            # Model sometimes returns 95 instead of 0.95
            if 1 < value <= 100:
                value = value / 100.0

            return value

        raise ValueError("confidence must be a number")


class RemediationProposal(BaseModel):
    action: Literal[
        "restart_service",
        "scale_out",
        "no_action",
    ]

    reason: str

    risk: Literal[
        "low",
        "medium",
        "high",
    ]

    expected_impact: str

    requires_human_approval: bool = True

    

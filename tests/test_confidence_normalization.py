import pytest

from incident_commander.schemas import RCAAssessment


@pytest.mark.parametrize(
    "input_value, expected",
    [
        (0.95, 0.95),
        (95, 0.95),
        ("95", 0.95),
        ("95%", 0.95),
        (100, 1.0),
        (1.0, 1.0),
        ("80%", 0.80),
    ],
)
def test_confidence_normalization(input_value, expected):
    result = RCAAssessment(
        root_cause="Database connection pool saturation",
        confidence=input_value,
        evidence=["Connection pool utilization reached 96%"],
        conflicting_evidence=[],
        next_checks=["Check database health"],
    )

    assert result.confidence == pytest.approx(expected)

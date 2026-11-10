"""Unit tests for RFC 7807 problem details and environment configuration validation."""

import pytest
from pydantic import ValidationError

from packages.shared.config import AppSettings
from packages.shared.errors import (
    ConflictError,
    ProblemDetail,
    problem_detail_response,
)


def test_rfc7807_problem_detail_serialization() -> None:
    """Verifies that ProblemDetail serializes to standard RFC 7807 format."""
    detail = ProblemDetail(
        type="https://changescope.io/errors/resource-not-found",
        title="Resource Not Found",
        status=404,
        detail="Workspace 'order-prod' does not exist.",
        instance="/api/v1/workspaces/order-prod",
        request_id="req-12345",
    )
    dumped = detail.model_dump(exclude_none=True)
    assert dumped["status"] == 404
    assert dumped["type"] == "https://changescope.io/errors/resource-not-found"
    assert dumped["title"] == "Resource Not Found"
    assert dumped["detail"] == "Workspace 'order-prod' does not exist."
    assert dumped["request_id"] == "req-12345"


def test_problem_detail_response_formatter() -> None:
    """Verifies that problem_detail_response produces valid JSONResponse with application/problem+json media type."""
    exc = ConflictError("Unique constraint violated: workspace slug exists")
    response = problem_detail_response(exc, instance="/api/v1/workspaces", request_id="trace-abc")

    assert response.status_code == 409
    assert response.media_type == "application/problem+json"


def test_app_settings_validation() -> None:
    """Verifies that AppSettings enforces security invariants such as minimum secret length."""
    # Valid config
    valid_settings = AppSettings(
        JWT_SECRET="valid_secret_key_minimum_32_characters_long",
        ENVIRONMENT="test",
    )
    assert valid_settings.ENVIRONMENT == "test"

    # Insecure short JWT secret must raise ValidationError
    with pytest.raises(ValidationError):
        AppSettings(JWT_SECRET="short_secret")

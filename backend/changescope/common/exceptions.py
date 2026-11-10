"""ChangeScope Custom Exception Hierarchy."""

from typing import Any


class ChangeScopeException(Exception):
    """Base exception for all ChangeScope platform errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationError(ChangeScopeException):
    """Raised when authentication credentials or token validation fails."""


class TenantIsolationError(ChangeScopeException):
    """Raised when an operation attempts unauthorized cross-tenant data access."""


class IngestionError(ChangeScopeException):
    """Raised when repository cloning, file checkout, or diffing fails."""


class ParseError(ChangeScopeException):
    """Raised when AST parsing or contract decoding fails."""


class SemanticRuleViolationError(ChangeScopeException):
    """Raised when a semantic contract check encounters a fatal evaluation error."""


class GraphProjectionError(ChangeScopeException):
    """Raised when outbox reconciliation or Cypher projection fails."""


class InvalidProvenanceError(ChangeScopeException):
    """Raised when an edge creation lacks required provenance and evidence metadata."""

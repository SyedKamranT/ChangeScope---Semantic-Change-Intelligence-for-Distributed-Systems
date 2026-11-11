"""Graph Query Service enforcing tenant isolation across Neo4j and Knowledge Graph projections."""

from typing import Any

from packages.shared.errors import AuthorizationError
from packages.shared.impact.graph import DependencyKnowledgeGraph
from packages.shared.security.authorization import SecurityContext, TenantRole


class GraphQueryService:
    """Service layer ensuring graph queries and traversals remain strictly isolated to caller tenants."""

    @classmethod
    def assert_cypher_tenant_isolation(
        cls,
        context: SecurityContext,
        query: str,
        parameters: dict[str, Any],
    ) -> None:
        """Validates that a Cypher query explicitly binds and parameters supply the caller's tenant_id."""
        context.assert_role(TenantRole.VIEWER)

        # 1. Parameter Assertion
        tenant_param = parameters.get("tenant_id")
        if not tenant_param:
            raise AuthorizationError("Graph query error: Mandatory 'tenant_id' parameter is missing.")

        if tenant_param != context.tenant_id:
            raise AuthorizationError(
                f"Graph query tenant violation: Parameter tenant '{tenant_param}' does not match context '{context.tenant_id}'."
            )

        # 2. Query AST/Text Guard: Must contain tenant_id constraint
        q_lower = query.lower()
        if "tenant_id" not in q_lower and "$tenant_id" not in q_lower:
            raise AuthorizationError(
                "Graph query error: Cypher query does not enforce 'tenant_id' predicate filtering."
            )

    @classmethod
    def get_scoped_knowledge_graph(
        cls,
        context: SecurityContext,
    ) -> DependencyKnowledgeGraph:
        """Constructs an empty or tenant-bound DependencyKnowledgeGraph enforcing strict context isolation."""
        context.assert_role(TenantRole.VIEWER)
        return DependencyKnowledgeGraph(tenant_id=context.tenant_id)

    @classmethod
    def validate_graph_node_access(
        cls,
        context: SecurityContext,
        node_tenant_id: str,
    ) -> None:
        """Guards against unauthorized cross-tenant graph traversal."""
        if node_tenant_id != context.tenant_id:
            raise AuthorizationError(
                f"Unauthorized graph traversal: Node belonging to '{node_tenant_id}' cannot be accessed by '{context.tenant_id}'."
            )

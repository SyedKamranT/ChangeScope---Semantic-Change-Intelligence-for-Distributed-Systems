"""Pure Static Tree-sitter & Regex AST Extraction Engine for TypeScript and JavaScript.

Extracts classes, interfaces, functions, calls, imports, exports, API routes (Express, NestJS),
HTTP client calls (axios, fetch), process.env references, event producers/consumers,
and database patterns without executing any repository code.
"""

import re
from typing import Any

import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser

from packages.shared.ingestion.models import (
    CallRelationship,
    CodeSymbol,
    DatabasePattern,
    EnvVarReference,
    EventPattern,
    HttpClientCall,
    ImportExport,
    RouteDefinition,
)

TS_LANGUAGE = Language(tstypescript.language_typescript())


class TypeScriptExtractor:
    """Safe static analyzer for TypeScript and JavaScript source files."""

    def __init__(self) -> None:
        self.parser = Parser(TS_LANGUAGE)

    def extract_source(self, code_str: str, file_path: str) -> dict[str, Any]:
        """Parses TypeScript/JavaScript source code and extracts all structural and semantic constructs."""
        symbols: list[CodeSymbol] = []
        imports_exports: list[ImportExport] = []
        calls: list[CallRelationship] = []
        routes: list[RouteDefinition] = []
        client_calls: list[HttpClientCall] = []
        env_vars: list[EnvVarReference] = []
        events: list[EventPattern] = []
        db_patterns: list[DatabasePattern] = []

        code_bytes = code_str.encode("utf-8")
        try:
            tree = self.parser.parse(code_bytes)
            root = tree.root_node
        except Exception as err:
            return {
                "symbols": symbols,
                "imports_exports": imports_exports,
                "calls": calls,
                "routes": routes,
                "client_calls": client_calls,
                "env_vars": env_vars,
                "events": events,
                "db_patterns": db_patterns,
                "error": f"Failed parsing TypeScript AST: {err}",
            }

        # Traverse Tree-sitter AST nodes
        def visit(node):
            ntype = node.type

            # 1. Classes and Interfaces
            if ntype in {"class_declaration", "interface_declaration"}:
                sym_type = "class" if ntype == "class_declaration" else "interface"
                name_node = node.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node else "Anonymous"
                symbols.append(
                    CodeSymbol(
                        name=name,
                        symbol_type=sym_type,
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                    )
                )

                # Check for TypeORM @Entity('table_name')
                node_text = node.text.decode("utf-8", errors="ignore")
                entity_match = re.search(r"@Entity\(\s*['\"]([^'\"]+)['\"]\s*\)", node_text)
                if entity_match:
                    db_patterns.append(
                        DatabasePattern(
                            operation="MODEL_DEF",
                            table_or_model=entity_match.group(1),
                            file_path=file_path,
                            line_number=node.start_point.row + 1,
                            orm_framework="TypeORM",
                        )
                    )

            # 2. Functions and Methods
            elif ntype in {"function_declaration", "method_definition", "arrow_function"}:
                name_node = node.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node else "anonymous"
                symbols.append(
                    CodeSymbol(
                        name=name,
                        symbol_type="function" if ntype != "method_definition" else "method",
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                    )
                )

            # 3. Imports
            elif ntype == "import_statement":
                # import { a, b } from 'module';
                text = node.text.decode("utf-8", errors="ignore")
                match = re.search(r"import\s+(?:(?:\*\s+as\s+\w+|\{[^}]+\}|\w+)\s+from\s+)?['\"]([^'\"]+)['\"]", text)
                if match:
                    mod = match.group(1)
                    imports_exports.append(
                        ImportExport(
                            file_path=file_path,
                            kind="import",
                            module=mod,
                            start_line=node.start_point.row + 1,
                            is_external=not (mod.startswith(".") or mod.startswith("/")),
                        )
                    )

            # 4. Exports
            elif ntype == "export_statement":
                text = node.text.decode("utf-8", errors="ignore")
                imports_exports.append(
                    ImportExport(
                        file_path=file_path,
                        kind="export",
                        module=file_path,
                        start_line=node.start_point.row + 1,
                        is_external=False,
                    )
                )

            # 5. Call Expressions (Routes, Clients, DB, Events)
            elif ntype == "call_expression":
                text = node.text.decode("utf-8", errors="ignore")

                # API Routes (Express / NestJS): app.get('/path', ...), router.post('/path', ...)
                route_match = re.search(
                    r"(?:app|router)\.(get|post|put|delete|patch|options)\(\s*['\"`]([^'\"`]+)['\"`]",
                    text,
                    re.IGNORECASE,
                )
                if route_match:
                    routes.append(
                        RouteDefinition(
                            method=route_match.group(1).upper(),
                            path_template=route_match.group(2),
                            handler_name="express_handler",
                            file_path=file_path,
                            start_line=node.start_point.row + 1,
                            end_line=node.end_point.row + 1,
                            framework="Express",
                        )
                    )

                # HTTP Client Calls: axios.get/post, fetch('/url')
                axios_match = re.search(
                    r"axios\.(get|post|put|delete|patch)\(\s*(['\"`][^'\"`]+['\"`]|`[^`]+`)",
                    text,
                    re.IGNORECASE,
                )
                if axios_match:
                    method = axios_match.group(1).upper()
                    raw_target = axios_match.group(2).strip("'\"`")
                    client_calls.append(
                        HttpClientCall(
                            method=method,
                            url_or_path=raw_target,
                            client_library="axios",
                            file_path=file_path,
                            line_number=node.start_point.row + 1,
                            is_dynamic="${" in raw_target,
                        )
                    )

                fetch_match = re.search(r"fetch\(\s*([a-zA-Z0-9_$.]+|['\"`][^'\"`]+['\"`]|`[^`]+`)", text)
                if fetch_match:
                    raw_target = fetch_match.group(1).strip("'\"`")
                    method = "GET"
                    method_match = re.search(r"method\s*:\s*['\"](GET|POST|PUT|DELETE|PATCH)['\"]", text, re.IGNORECASE)
                    if method_match:
                        method = method_match.group(1).upper()
                    client_calls.append(
                        HttpClientCall(
                            method=method,
                            url_or_path=raw_target,
                            client_library="fetch",
                            file_path=file_path,
                            line_number=node.start_point.row + 1,
                            is_dynamic=not (
                                raw_target.startswith("http://")
                                or raw_target.startswith("https://")
                                or raw_target.startswith("/")
                            ),
                        )
                    )

                # Event producers/consumers: emit('event', data), on('event', handler)
                event_match = re.search(r"\.(emit|on)\(\s*['\"]([^'\"]+)['\"]", text)
                if event_match:
                    ev_kind = "producer" if event_match.group(1) == "emit" else "consumer"
                    events.append(
                        EventPattern(
                            pattern_type=ev_kind,
                            event_name_or_topic=event_match.group(2),
                            file_path=file_path,
                            line_number=node.start_point.row + 1,
                            framework="EventEmitter",
                        )
                    )

                # Prisma database queries: prisma.<model>.findMany/create
                prisma_match = re.search(r"prisma\.(\w+)\.(findMany|findUnique|create|update|delete)\(", text)
                if prisma_match:
                    db_patterns.append(
                        DatabasePattern(
                            operation=prisma_match.group(2).upper(),
                            table_or_model=prisma_match.group(1),
                            file_path=file_path,
                            line_number=node.start_point.row + 1,
                            orm_framework="Prisma",
                        )
                    )

            # Recurse children
            for child in node.children:
                visit(child)

        visit(root)

        # 6. Extract process.env References via regex across entire file
        for line_idx, line in enumerate(code_str.splitlines(), start=1):
            env_matches = re.finditer(r"process\.env(?:\.([a-zA-Z0-9_]+)|\[['\"]([a-zA-Z0-9_]+)['\"]\])", line)
            for m in env_matches:
                var_name = m.group(1) or m.group(2)
                has_fallback = "||" in line or "??" in line
                env_vars.append(
                    EnvVarReference(
                        name=var_name,
                        file_path=file_path,
                        line_number=line_idx,
                        has_fallback=has_fallback,
                    )
                )

        return {
            "symbols": symbols,
            "imports_exports": imports_exports,
            "calls": calls,
            "routes": routes,
            "client_calls": client_calls,
            "env_vars": env_vars,
            "events": events,
            "db_patterns": db_patterns,
            "error": None,
        }

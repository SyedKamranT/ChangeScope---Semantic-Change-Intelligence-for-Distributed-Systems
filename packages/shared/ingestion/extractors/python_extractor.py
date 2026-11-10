"""Pure Static AST Extraction Engine for Python Codebases.

Extracts classes, functions, calls, imports, exports, API routes (FastAPI, Flask, Django),
HTTP client calls (httpx, requests, aiohttp), env vars, event producers/consumers,
and database patterns without executing any repository code.
"""

import ast
import re
from typing import Any

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


class PythonExtractor:
    """Safe, deterministic static analyzer for Python source files."""

    @classmethod
    def extract_source(cls, code_str: str, file_path: str) -> dict[str, Any]:
        """Parses Python source code and extracts all structural and semantic constructs."""
        symbols: list[CodeSymbol] = []
        imports_exports: list[ImportExport] = []
        calls: list[CallRelationship] = []
        routes: list[RouteDefinition] = []
        client_calls: list[HttpClientCall] = []
        env_vars: list[EnvVarReference] = []
        events: list[EventPattern] = []
        db_patterns: list[DatabasePattern] = []

        try:
            tree = ast.parse(code_str, filename=file_path)
        except SyntaxError as err:
            return {
                "symbols": symbols,
                "imports_exports": imports_exports,
                "calls": calls,
                "routes": routes,
                "client_calls": client_calls,
                "env_vars": env_vars,
                "events": events,
                "db_patterns": db_patterns,
                "error": f"SyntaxError at line {err.lineno}: {err.msg}",
            }

        # Track caller stack during traversal
        caller_stack: list[str] = ["<module>"]

        for node in ast.walk(tree):
            # 1. Classes & ORM Models
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                decorators = [cls._get_decorator_name(d) for d in node.decorator_list]
                symbols.append(
                    CodeSymbol(
                        name=node.name,
                        symbol_type="class",
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        docstring=doc,
                        decorators=decorators,
                    )
                )

                # Check for SQLAlchemy / ORM __tablename__
                table_name = None
                columns: list[str] = []
                for sub in node.body:
                    if isinstance(sub, ast.Assign):
                        for target in sub.targets:
                            if isinstance(target, ast.Name) and target.id == "__tablename__":
                                if isinstance(sub.value, ast.Constant) and isinstance(sub.value.value, str):
                                    table_name = sub.value.value
                            elif isinstance(target, ast.Name):
                                columns.append(target.id)
                    elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
                        if sub.target.id == "__tablename__" and sub.value and isinstance(sub.value, ast.Constant):
                            table_name = str(sub.value.value)
                        else:
                            columns.append(sub.target.id)

                if table_name:
                    db_patterns.append(
                        DatabasePattern(
                            operation="MODEL_DEF",
                            table_or_model=table_name,
                            file_path=file_path,
                            line_number=node.lineno,
                            orm_framework="SQLAlchemy",
                            columns=columns,
                        )
                    )

            # 2. Functions & API Routes
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_type = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                doc = ast.get_docstring(node)
                decorators = [cls._get_decorator_name(d) for d in node.decorator_list]

                # Check for API Route decorators (FastAPI, Flask)
                route = cls._extract_route_from_func(node, file_path)
                if route:
                    routes.append(route)

                # Check for Celery task decorators
                for dec in decorators:
                    if "task" in dec.lower():
                        events.append(
                            EventPattern(
                                pattern_type="consumer",
                                event_name_or_topic=node.name,
                                file_path=file_path,
                                line_number=node.lineno,
                                framework="Celery",
                            )
                        )

                symbols.append(
                    CodeSymbol(
                        name=node.name,
                        symbol_type=func_type,
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        docstring=doc,
                        decorators=decorators,
                    )
                )

            # 3. Imports & Exports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports_exports.append(
                        ImportExport(
                            file_path=file_path,
                            kind="import",
                            module=alias.name,
                            symbols=[alias.asname or alias.name],
                            start_line=node.lineno,
                            is_external=not alias.name.startswith("."),
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                symbols_imported = [alias.name for alias in node.names]
                imports_exports.append(
                    ImportExport(
                        file_path=file_path,
                        kind="import",
                        module=module_name,
                        symbols=symbols_imported,
                        start_line=node.lineno,
                        is_external=not (module_name.startswith(".") or node.level > 0),
                    )
                )

            # 4. Exports (__all__)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        exported_symbols = []
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    exported_symbols.append(elt.value)
                        imports_exports.append(
                            ImportExport(
                                file_path=file_path,
                                kind="export",
                                module=file_path,
                                symbols=exported_symbols,
                                start_line=node.lineno,
                                is_external=False,
                            )
                        )

            # 5. Function Calls & HTTP Clients & Event Triggers
            elif isinstance(node, ast.Call):
                call_name = cls._get_call_name(node.func)
                if call_name:
                    calls.append(
                        CallRelationship(
                            caller_name=caller_stack[-1],
                            callee_name=call_name,
                            file_path=file_path,
                            line_number=node.lineno,
                            is_internal=not any(call_name.startswith(p) for p in ["httpx", "requests", "os", "sys"]),
                            evidence=f"Call to {call_name} at line {node.lineno}",
                        )
                    )

                    # HTTP Client Calls: requests / httpx / aiohttp
                    http_client = cls._extract_http_client_call(node, call_name, file_path)
                    if http_client:
                        client_calls.append(http_client)

                    # Event Producers: Celery delay/apply_async, Kafka send
                    event_prod = cls._extract_event_producer(node, call_name, file_path)
                    if event_prod:
                        events.append(event_prod)

                    # Database Access: session.execute, session.query
                    db_op = cls._extract_db_call(node, call_name, file_path)
                    if db_op:
                        db_patterns.append(db_op)

            # 6. Environment Variable References
            env_ref = cls._extract_env_var(node, file_path)
            if env_ref:
                env_vars.append(env_ref)

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

    @classmethod
    def _get_decorator_name(cls, dec_node: ast.AST) -> str:
        if isinstance(dec_node, ast.Name):
            return dec_node.id
        elif isinstance(dec_node, ast.Attribute):
            return f"{cls._get_call_name(dec_node.value)}.{dec_node.attr}"
        elif isinstance(dec_node, ast.Call):
            return cls._get_decorator_name(dec_node.func)
        return "decorator"

    @classmethod
    def _get_call_name(cls, func_node: ast.AST) -> str | None:
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            value_name = cls._get_call_name(func_node.value)
            return f"{value_name}.{func_node.attr}" if value_name else func_node.attr
        return None

    @classmethod
    def _extract_route_from_func(
        cls, func_node: ast.FunctionDef | ast.AsyncFunctionDef, file_path: str
    ) -> RouteDefinition | None:
        """Extracts FastAPI or Flask route definitions from function decorators."""
        for dec in func_node.decorator_list:
            if isinstance(dec, ast.Call):
                dec_func_name = cls._get_call_name(dec.func) or ""
                # Match e.g. app.get("/items"), router.post("/checkout"), app.route("/path", methods=["POST"])
                match = re.search(
                    r"(?:app|router|bp)\.(get|post|put|delete|patch|options|route)$", dec_func_name, re.IGNORECASE
                )
                if match:
                    method_or_route = match.group(1).upper()
                    path = "/"
                    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                        path = dec.args[0].value

                    method = method_or_route
                    if method == "ROUTE":
                        # Check methods kwarg
                        method = "GET"
                        for kw in dec.keywords:
                            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                                if kw.value.elts and isinstance(kw.value.elts[0], ast.Constant):
                                    method = str(kw.value.elts[0].value).upper()

                    # Extract parameter names
                    params = [{"name": a.arg} for a in func_node.args.args if a.arg != "self"]
                    return RouteDefinition(
                        method=method,
                        path_template=path,
                        handler_name=func_node.name,
                        file_path=file_path,
                        start_line=func_node.lineno,
                        end_line=func_node.end_lineno or func_node.lineno,
                        framework="FastAPI",
                        parameters=params,
                    )
        return None

    @classmethod
    def _extract_http_client_call(cls, node: ast.Call, call_name: str, file_path: str) -> HttpClientCall | None:
        """Detects calls to requests, httpx, or aiohttp."""
        # e.g., requests.get("https://..."), httpx.post("http://...")
        match = re.match(
            r"(requests|httpx|client|session)\.(get|post|put|delete|patch|request)$", call_name, re.IGNORECASE
        )
        if match:
            lib = match.group(1).lower()
            method = match.group(2).upper()
            target_url = "dynamic_url"
            is_dynamic = True

            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                target_url = node.args[0].value
                is_dynamic = False
            elif node.args and isinstance(node.args[0], ast.JoinedStr):
                # Reconstruct f-string literal fragments with placeholders for expressions
                parts: list[str] = []
                for val in node.args[0].values:
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        parts.append(val.value)
                    else:
                        parts.append("{...}")
                target_url = "".join(parts)
                is_dynamic = True

            return HttpClientCall(
                method=method,
                url_or_path=target_url,
                client_library=lib,
                file_path=file_path,
                line_number=node.lineno,
                is_dynamic=is_dynamic,
            )
        return None

    @classmethod
    def _extract_event_producer(cls, node: ast.Call, call_name: str, file_path: str) -> EventPattern | None:
        """Detects Celery delay/apply_async and Kafka produce calls."""
        if call_name.endswith(".delay") or call_name.endswith(".apply_async"):
            task_name = call_name.rsplit(".", 1)[0]
            return EventPattern(
                pattern_type="producer",
                event_name_or_topic=task_name,
                file_path=file_path,
                line_number=node.lineno,
                framework="Celery",
            )
        elif "producer.send" in call_name:
            topic = "unknown_topic"
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                topic = node.args[0].value
            return EventPattern(
                pattern_type="producer",
                event_name_or_topic=topic,
                file_path=file_path,
                line_number=node.lineno,
                framework="Kafka",
            )
        return None

    @classmethod
    def _extract_db_call(cls, node: ast.Call, call_name: str, file_path: str) -> DatabasePattern | None:
        """Detects database query operations: session.execute, session.query."""
        if call_name in {"session.execute", "session.query", "conn.execute", "cursor.execute"}:
            sql_preview = "DYNAMIC_QUERY"
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                sql_preview = node.args[0].value[:60].strip()
            elif node.args and isinstance(node.args[0], ast.Call):
                sql_preview = cls._get_call_name(node.args[0].func) or "CALL"
            return DatabasePattern(
                operation="RAW_QUERY",
                table_or_model=sql_preview,
                file_path=file_path,
                line_number=node.lineno,
                orm_framework="SQLAlchemy",
            )
        return None

    @classmethod
    def _extract_env_var(cls, node: ast.AST, file_path: str) -> EnvVarReference | None:
        """Detects os.environ['VAR'], os.environ.get('VAR'), os.getenv('VAR')."""
        if isinstance(node, ast.Subscript):
            # os.environ["VAR"]
            val_name = cls._get_call_name(node.value)
            if val_name == "os.environ" and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                return EnvVarReference(
                    name=node.slice.value,
                    file_path=file_path,
                    line_number=node.lineno,
                    has_fallback=False,
                )
        elif isinstance(node, ast.Call):
            call_name = cls._get_call_name(node.func)
            if call_name in {"os.getenv", "os.environ.get"}:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    var_name = node.args[0].value
                    default_val = None
                    has_fallback = len(node.args) > 1 or len(node.keywords) > 0
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        default_val = str(node.args[1].value)
                    return EnvVarReference(
                        name=var_name,
                        file_path=file_path,
                        line_number=node.lineno,
                        default_value=default_val,
                        has_fallback=has_fallback,
                    )
        return None

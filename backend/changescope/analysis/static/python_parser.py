"""Tree-sitter AST Parser for Python (FastAPI, Flask, SQLAlchemy, requests/httpx)."""

import re
from typing import Any

import tree_sitter_python as tspython
from changescope.analysis.static.models import ExtractedClientCall, ExtractedORMModel, ExtractedRoute
from tree_sitter import Language, Parser

# Initialize Python Language and Parser
PY_LANGUAGE = Language(tspython.language())


class PythonASTParser:
    """Extracts routes, HTTP client calls, and ORM models from Python source code."""

    def __init__(self):
        self.parser = Parser(PY_LANGUAGE)

    def parse_source(self, code_str: str, file_path: str = "app.py") -> dict[str, list[Any]]:
        """Parses a Python source string and returns extracted routes, calls, and ORM models."""
        code_bytes = code_str.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        root = tree.root_node

        routes = self._extract_routes(root, code_bytes, file_path)
        calls = self._extract_client_calls(root, code_bytes, file_path)
        models = self._extract_orm_models(root, code_bytes, file_path)

        return {
            "routes": routes,
            "client_calls": calls,
            "orm_models": models,
        }

    def _extract_routes(self, root, code_bytes: bytes, file_path: str) -> list[ExtractedRoute]:
        routes = []

        def visit(node):
            if node.type == "decorated_definition":
                # Look for decorators
                decorator_nodes = [c for c in node.children if c.type == "decorator"]
                func_def = next((c for c in node.children if c.type == "function_definition"), None)

                if func_def:
                    func_name_node = next((c for c in func_def.children if c.type == "identifier"), None)
                    func_name = func_name_node.text.decode("utf-8") if func_name_node else "anonymous"

                    for dec in decorator_nodes:
                        dec_text = dec.text.decode("utf-8")
                        # Match FastAPI / Flask style: @app.get("/path"), @router.post("/path")
                        match = re.search(
                            r"@\w+\.(get|post|put|delete|patch|options)\(\s*['\"]([^'\"]+)['\"]",
                            dec_text,
                            re.IGNORECASE,
                        )
                        if match:
                            method = match.group(1).upper()
                            path = match.group(2)
                            routes.append(
                                ExtractedRoute(
                                    method=method,
                                    path_template=path,
                                    handler_name=func_name,
                                    file_path=file_path,
                                    start_line=node.start_point.row + 1,
                                    end_line=node.end_point.row + 1,
                                    framework="FastAPI",
                                )
                            )

            for child in node.children:
                visit(child)

        visit(root)
        return routes

    def _extract_client_calls(self, root, code_bytes: bytes, file_path: str) -> list[ExtractedClientCall]:
        calls = []

        def visit(node):
            if node.type == "call":
                func_node = node.child_by_field_name("function")
                if func_node:
                    func_text = func_node.text.decode("utf-8")
                    args_node = node.child_by_field_name("arguments")
                    args_text = args_node.text.decode("utf-8") if args_node else ""

                    # Match requests.get("..."), httpx.post("..."), client.get("...")
                    match = re.match(
                        r"(?:requests|httpx|client|session)\.(get|post|put|delete|patch)",
                        func_text,
                        re.IGNORECASE,
                    )
                    if match:
                        method = match.group(1).upper()
                        url_match = re.search(r"['\"]([^'\"]+)['\"]", args_text)
                        if url_match:
                            calls.append(
                                ExtractedClientCall(
                                    method=method,
                                    url_or_path=url_match.group(1),
                                    client_library="requests/httpx",
                                    file_path=file_path,
                                    start_line=node.start_point.row + 1,
                                    end_line=node.end_point.row + 1,
                                    is_dynamic=False,
                                )
                            )
                        else:
                            # Dynamic call: requests.get(url_var)
                            dyn_match = re.search(r"\(\s*([a-zA-Z_]\w*)", args_text)
                            var_name = dyn_match.group(1) if dyn_match else "dynamic_url"
                            calls.append(
                                ExtractedClientCall(
                                    method=method,
                                    url_or_path=f"${{{var_name}}}",
                                    client_library="requests/httpx",
                                    file_path=file_path,
                                    start_line=node.start_point.row + 1,
                                    end_line=node.end_point.row + 1,
                                    is_dynamic=True,
                                )
                            )

            for child in node.children:
                visit(child)

        visit(root)
        return calls

    def _extract_orm_models(self, root, code_bytes: bytes, file_path: str) -> list[ExtractedORMModel]:
        models = []

        def visit(node):
            if node.type == "class_definition":
                class_text = node.text.decode("utf-8")
                class_name_node = next((c for c in node.children if c.type == "identifier"), None)
                class_name = class_name_node.text.decode("utf-8") if class_name_node else "UnknownClass"

                # Look for __tablename__ = "users"
                table_match = re.search(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", class_text)
                if table_match:
                    table_name = table_match.group(1)
                    models.append(
                        ExtractedORMModel(
                            model_name=class_name,
                            table_name=table_name,
                            file_path=file_path,
                            start_line=node.start_point.row + 1,
                            end_line=node.end_point.row + 1,
                        )
                    )

            for child in node.children:
                visit(child)

        visit(root)
        return models

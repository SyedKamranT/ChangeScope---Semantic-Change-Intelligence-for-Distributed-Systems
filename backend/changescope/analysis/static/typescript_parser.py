"""Tree-sitter AST Parser for TypeScript and JavaScript (Express, NestJS, axios, fetch)."""

import re
from typing import Any

import tree_sitter_typescript as tstypescript
from changescope.analysis.static.models import ExtractedClientCall, ExtractedRoute
from tree_sitter import Language, Parser

# Initialize TypeScript Language and Parser
TS_LANGUAGE = Language(tstypescript.language_typescript())


class TypeScriptASTParser:
    """Extracts routes and HTTP client calls from TypeScript / JavaScript code."""

    def __init__(self):
        self.parser = Parser(TS_LANGUAGE)

    def parse_source(self, code_str: str, file_path: str = "app.ts") -> dict[str, list[Any]]:
        code_bytes = code_str.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        root = tree.root_node

        routes = self._extract_routes(root, code_bytes, file_path)
        calls = self._extract_client_calls(root, code_bytes, file_path)

        return {
            "routes": routes,
            "client_calls": calls,
            "orm_models": [],
        }

    def _extract_routes(self, root, code_bytes: bytes, file_path: str) -> list[ExtractedRoute]:
        routes = []

        def visit(node):
            # Express: app.get('/orders', (req, res) => ...) or router.post('/checkout', ...)
            if node.type == "call_expression":
                text = node.text.decode("utf-8")
                match = re.search(
                    r"(?:app|router)\.(get|post|put|delete|patch)\(\s*['\"`]([^'\"`]+)['\"`]",
                    text,
                    re.IGNORECASE,
                )
                if match:
                    method = match.group(1).upper()
                    path = match.group(2)
                    routes.append(
                        ExtractedRoute(
                            method=method,
                            path_template=path,
                            handler_name="express_handler",
                            file_path=file_path,
                            start_line=node.start_point.row + 1,
                            end_line=node.end_point.row + 1,
                            framework="Express",
                        )
                    )

            # NestJS Controller Decorators: @Get('/users'), @Post()
            if node.type == "decorator":
                text = node.text.decode("utf-8")
                match = re.search(r"@(Get|Post|Put|Delete|Patch)\(\s*['\"`]([^'\"`]*)['\"`]?\s*\)", text, re.IGNORECASE)
                if match:
                    method = match.group(1).upper()
                    subpath = match.group(2) or "/"
                    routes.append(
                        ExtractedRoute(
                            method=method,
                            path_template=subpath,
                            handler_name="nestjs_handler",
                            file_path=file_path,
                            start_line=node.start_point.row + 1,
                            end_line=node.end_point.row + 1,
                            framework="NestJS",
                        )
                    )

            for child in node.children:
                visit(child)

        visit(root)
        return routes

    def _extract_client_calls(self, root, code_bytes: bytes, file_path: str) -> list[ExtractedClientCall]:
        calls = []

        def visit(node):
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node:
                    func_text = func_node.text.decode("utf-8")
                    args_node = node.child_by_field_name("arguments")
                    args_text = args_node.text.decode("utf-8") if args_node else ""

                    # axios.post('/api/pay', ...)
                    axios_match = re.match(r"axios\.(get|post|put|delete|patch)", func_text, re.IGNORECASE)
                    if axios_match:
                        url_match = re.search(r"['\"`]([^'\"`]+)['\"`]", args_text)
                        url_or_path = url_match.group(1) if url_match else "unknown"
                        calls.append(
                            ExtractedClientCall(
                                method=axios_match.group(1).upper(),
                                url_or_path=url_or_path,
                                client_library="axios",
                                file_path=file_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                            )
                        )
                    elif func_text == "fetch":
                        url_match = re.search(r"['\"`]([^'\"`]+)['\"`]", args_text)
                        url_or_path = url_match.group(1) if url_match else "unknown"
                        method_match = re.search(
                            r"method:\s*['\"`](GET|POST|PUT|DELETE|PATCH)['\"`]", args_text, re.IGNORECASE
                        )
                        method = method_match.group(1).upper() if method_match else "GET"
                        calls.append(
                            ExtractedClientCall(
                                method=method,
                                url_or_path=url_or_path,
                                client_library="fetch",
                                file_path=file_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                            )
                        )

            for child in node.children:
                visit(child)

        visit(root)
        return calls

"""Data structures for AST extraction results."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedRoute:
    """An API route definition extracted from code."""

    method: str
    path_template: str
    handler_name: str
    file_path: str
    start_line: int
    end_line: int
    framework: str  # 'FastAPI', 'Flask', 'Django', 'Express', 'NestJS'
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedClientCall:
    """An outbound HTTP or RPC call invocation extracted from code."""

    method: str
    url_or_path: str
    client_library: str  # 'requests', 'httpx', 'fetch', 'axios'
    file_path: str
    start_line: int
    end_line: int
    is_dynamic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedORMModel:
    """An ORM entity model mapped to a database table."""

    model_name: str
    table_name: str
    file_path: str
    start_line: int
    end_line: int
    columns: list[dict[str, Any]] = field(default_factory=list)

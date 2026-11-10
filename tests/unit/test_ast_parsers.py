"""Unit tests for Tree-sitter Python and TypeScript AST Parsers."""

from changescope.analysis.static.python_parser import PythonASTParser
from changescope.analysis.static.typescript_parser import TypeScriptASTParser


def test_python_fastapi_route_and_client_extraction():
    code = """
from fastapi import FastAPI
import httpx
from db import Base

app = FastAPI()

class Order(Base):
    __tablename__ = "orders"

@app.get("/api/v1/items")
def list_items():
    res = httpx.get("https://inventory.internal/stock")
    return {"status": "ok"}

@app.post("/api/v1/checkout")
def checkout():
    return {"order_id": 123}
"""
    parser = PythonASTParser()
    result = parser.parse_source(code, file_path="main.py")

    routes = result["routes"]
    assert len(routes) == 2
    assert routes[0].method == "GET"
    assert routes[0].path_template == "/api/v1/items"
    assert routes[0].handler_name == "list_items"
    assert routes[1].method == "POST"
    assert routes[1].path_template == "/api/v1/checkout"

    client_calls = result["client_calls"]
    assert len(client_calls) == 1
    assert client_calls[0].method == "GET"
    assert client_calls[0].url_or_path == "https://inventory.internal/stock"

    orm_models = result["orm_models"]
    assert len(orm_models) == 1
    assert orm_models[0].model_name == "Order"
    assert orm_models[0].table_name == "orders"


def test_typescript_express_and_axios_extraction():
    code = """
import express from 'express';
import axios from 'axios';

const app = express();

app.get('/api/v1/users', async (req, res) => {
    const response = await axios.post('http://billing.internal/charge', { amount: 100 });
    res.json(response.data);
});

app.post('/api/v1/register', (req, res) => {
    res.send('registered');
});
"""
    parser = TypeScriptASTParser()
    result = parser.parse_source(code, file_path="server.ts")

    routes = result["routes"]
    assert len(routes) == 2
    assert routes[0].method == "GET"
    assert routes[0].path_template == "/api/v1/users"
    assert routes[1].method == "POST"
    assert routes[1].path_template == "/api/v1/register"

    client_calls = result["client_calls"]
    assert len(client_calls) == 1
    assert client_calls[0].method == "POST"
    assert client_calls[0].url_or_path == "http://billing.internal/charge"
    assert client_calls[0].client_library == "axios"

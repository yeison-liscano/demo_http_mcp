"""End-to-end: a real MCP client (the `mcp` SDK) against this server over HTTP and stdio.

Each test runs against three transports:

- ``http``: the unauthenticated MCP server on uvicorn (ephemeral loopback port).
- ``http-auth0``: the Auth0-protected app (`auth_mcp` + `Auth0TokenValidator`, with only
  Auth0's JWT verification mocked), called with a bearer token.
- ``stdio``: the real ``run-stdio`` entry point (`app.main.run_stdio`) as a subprocess.

This is what catches protocol drift between http-mcp and the client ecosystem, which
hand-built JSON-RPC requests cannot. The Claude sub-agents are faked (`tests.fakes`) in the
served app and in the subprocess, so no test calls Claude or the web.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
import uvicorn
from auth_mcp.resource_server import ProtectedMCPAppConfig, create_protected_mcp_app
from auth_mcp.types import ProtectedResourceMetadata
from http_mcp.server import MCPServer
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.routing import Mount

from app.auth0 import Auth0TokenValidator
from app.tools import TOOLS, create_tools
from tests.fakes import FETCH_ANSWER, SEARCH_ANSWER, fake_web_agents
from tests.mcp_protocol import PROTOCOL_VERSION

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.types import ASGIApp, Receive, Scope, Send

BACKEND_DIR = Path(__file__).resolve().parent.parent
_STARTUP_TIMEOUT_S = 10.0
_STDIO_BOOT = (
    "from tests.fakes import fake_web_agents\n"
    "from app.main import run_stdio\n"
    "with fake_web_agents():\n"
    "    run_stdio()\n"
)
TRANSPORTS = ("http", "http-auth0", "stdio")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _with_fake_agents(app: ASGIApp) -> ASGIApp:
    """Enter the agent fakes for each request.

    uvicorn serves from another thread, and pydantic-ai's `Agent.override` is a context
    variable, so an override entered in the test would not reach the server.
    """

    async def wrapped(scope: Scope, receive: Receive, send: Send) -> None:
        with fake_web_agents():
            await app(scope, receive, send)

    return wrapped


@contextmanager
def _serve(app: ASGIApp, port: int) -> Iterator[None]:
    config = uvicorn.Config(
        _with_fake_agents(app),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + _STARTUP_TIMEOUT_S
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail("uvicorn did not start")
        time.sleep(0.02)
    yield
    server.should_exit = True
    thread.join(timeout=_STARTUP_TIMEOUT_S)


@pytest.fixture(scope="module")
def plain_url() -> Iterator[str]:
    mcp_server = MCPServer(tools=TOOLS, name="test", version="1.0.0")
    port = _free_port()
    with _serve(Starlette(routes=[Mount("/mcp", mcp_server.app)]), port):
        yield f"http://127.0.0.1:{port}/mcp/"


@pytest.fixture(scope="module")
def protected_url() -> Iterator[str]:
    port = _free_port()
    resource = f"http://127.0.0.1:{port}/mcp/"
    auth0_api = AsyncMock()
    auth0_api.verify_access_token.return_value = {
        "sub": "user|123",
        "scope": "tool:web_search tool:web_fetch",
        "aud": resource,
        "exp": 9999999999,
    }
    with patch("app.auth0.ApiClient", return_value=auth0_api):
        validator = Auth0TokenValidator(domain="test.auth0.com", audience=resource)
    app = create_protected_mcp_app(
        ProtectedMCPAppConfig(
            mcp_server=MCPServer(
                tools=create_tools(auth_enabled=True),
                name="test",
                version="1.0.0",
            ),
            token_validator=validator,
            resource_endpoint=ProtectedResourceMetadata(
                resource=AnyHttpUrl(resource),
                authorization_servers=("https://test.auth0.com/",),
            ),
        ),
    )
    with _serve(app, port):
        yield resource


@pytest.fixture(params=TRANSPORTS)
def client(request: pytest.FixtureRequest, plain_url: str, protected_url: str) -> Client:
    match request.param:
        case "http":
            return Client(plain_url)
        case "http-auth0":
            bearer = httpx2.AsyncClient(headers={"Authorization": "Bearer header.payload.sig"})
            return Client(streamable_http_client(protected_url, http_client=bearer))
        case _:
            return Client(
                StdioServerParameters(
                    command=sys.executable,
                    args=["-c", _STDIO_BOOT],
                    cwd=str(BACKEND_DIR),
                ),
            )


def _structured(result: Any) -> dict[str, Any]:  # noqa: ANN401
    assert result.is_error is False, result.content
    assert isinstance(result.structured_content, dict)
    return result.structured_content


async def test_negotiates_current_protocol(client: Client) -> None:
    async with client:
        assert client.protocol_version == PROTOCOL_VERSION
        assert client.server_info is not None
        assert client.server_info.name == "test"


async def test_lists_web_tools(client: Client) -> None:
    async with client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"web_search", "web_fetch"}
    for tool in tools.values():
        assert tool.output_schema is not None
        assert "prompt_injection_detections" in tool.output_schema["properties"]


async def test_calls_web_tools(client: Client) -> None:
    async with client:
        search = await client.call_tool("web_search", {"query": "what is MCP?"})
        fetch = await client.call_tool(
            "web_fetch",
            {"url": "https://example.com/", "question": "What is this page for?"},
        )
    assert _structured(search) == {**SEARCH_ANSWER, "prompt_injection_detections": []}
    assert _structured(fetch) == {**FETCH_ANSWER, "prompt_injection_detections": []}


async def test_invalid_arguments_raise_invalid_params(client: Client) -> None:
    async with client:
        with pytest.raises(MCPError, match="url"):
            await client.call_tool("web_fetch", {"url": "file:///etc/passwd"})


async def test_http_without_token_is_refused(protected_url: str) -> None:
    with pytest.RaisesGroup(MCPError, flatten_subgroups=True):
        async with Client(protected_url) as client:
            await client.list_tools()

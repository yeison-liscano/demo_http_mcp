"""End-to-end: a real MCP client (the `mcp` SDK) against this server over HTTP and stdio.

Each test runs against three transports:

- ``http``: the unauthenticated MCP server on uvicorn (ephemeral loopback port).
- ``http-auth0``: the Auth0-protected app (`auth_mcp` + `Auth0TokenValidator`, with only
  Auth0's JWT verification mocked), called with a bearer token.
- ``stdio``: the real ``run-stdio`` entry point (`app.main.run_stdio`) as a subprocess.

This is what catches protocol drift between http-mcp and the client ecosystem, which
hand-built JSON-RPC requests cannot. NVD is faked in-process and in the subprocess.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import httpx2
import nvdlib
import pytest
import uvicorn
from auth_mcp.resource_server import ProtectedMCPAppConfig, create_protected_mcp_app
from auth_mcp.types import ProtectedResourceMetadata
from http_mcp.server import MCPServer
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp.types import GetPromptResult, TextContent
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.routing import Mount

from app.auth0 import Auth0TokenValidator
from app.prompts import PROMPTS
from app.tools import TOOLS, create_tools
from tests.conftest import make_fake_cpe, make_fake_cve
from tests.mcp_protocol import PROTOCOL_VERSION

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.types import ASGIApp

BACKEND_DIR = Path(__file__).resolve().parent.parent
_STARTUP_TIMEOUT_S = 10.0
_STDIO_BOOT = (
    "import nvdlib; from tests.conftest import make_fake_cpe, make_fake_cve; "
    "nvdlib.searchCVE = lambda **_: [make_fake_cve()]; "
    "nvdlib.searchCPE = lambda **_: [make_fake_cpe()]; "
    "from app.main import run_stdio; run_stdio()"
)
TRANSPORTS = ("http", "http-auth0", "stdio")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve(app: ASGIApp, port: int) -> Iterator[None]:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
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
    mcp_server = MCPServer(tools=TOOLS, prompts=PROMPTS, name="test", version="1.0.0")
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
        "scope": "tool:search_cpe tool:search_cve",
        "aud": resource,
        "exp": 9999999999,
    }
    with patch("app.auth0.ApiClient", return_value=auth0_api):
        validator = Auth0TokenValidator(domain="test.auth0.com", audience=resource)
    app = create_protected_mcp_app(
        ProtectedMCPAppConfig(
            mcp_server=MCPServer(
                tools=create_tools(auth_enabled=True),
                prompts=PROMPTS,
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


@pytest.fixture(autouse=True)
def _fake_nvd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nvdlib, "searchCVE", lambda **_: [make_fake_cve()])
    monkeypatch.setattr(nvdlib, "searchCPE", lambda **_: [make_fake_cpe()])


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


def _text(prompt: GetPromptResult) -> str:
    content = prompt.messages[0].content
    assert isinstance(content, TextContent), content
    return content.text


async def test_negotiates_current_protocol(client: Client) -> None:
    async with client:
        assert client.protocol_version == PROTOCOL_VERSION
        assert client.server_info is not None
        assert client.server_info.name == "test"


async def test_lists_tools_and_prompts(client: Client) -> None:
    async with client:
        tools = {t.name for t in (await client.list_tools()).tools}
        prompts = {p.name for p in (await client.list_prompts()).prompts}
    assert tools == {"search_cpe", "search_cve"}
    assert prompts == {"async_nvd_search", "sync_nvd_search"}


async def test_calls_tools(client: Client) -> None:
    async with client:
        cpe = await client.call_tool("search_cpe", {"product": "curl", "version": "8.4.0"})
        cve = await client.call_tool("search_cve", {"cve_id": "CVE-2023-44487"})
    assert _structured(cpe)["cpes"][0]["cpeName"].startswith("cpe:2.3:a:haxx:curl")
    assert _structured(cve)["cves"][0]["id"] == "CVE-2023-44487"


async def test_invalid_arguments_raise_invalid_params(client: Client) -> None:
    async with client:
        with pytest.raises(MCPError, match="Version must be a valid semver"):
            await client.call_tool("search_cpe", {"product": "curl", "version": "8.4"})


async def test_gets_prompts(client: Client) -> None:
    args = {"dependency_name": "curl", "dependency_version": "8.4.0"}
    async with client:
        simple = await client.get_prompt("sync_nvd_search", args)
        enriched = await client.get_prompt("async_nvd_search", args)

    assert _text(simple) == "Search for vulnerabilities in curl 8.4.0"
    text = _text(enriched)
    # The preamble mentions "<cves>" too, so take the block after the last opening tag.
    cves = json.loads(text.rsplit("<cves>", 1)[1].split("</cves>", 1)[0])
    assert cves[0]["cves"][0]["id"] == "CVE-2023-44487"


async def test_http_without_token_is_refused(protected_url: str) -> None:
    with pytest.RaisesGroup(MCPError, flatten_subgroups=True):
        async with Client(protected_url) as client:
            await client.list_tools()

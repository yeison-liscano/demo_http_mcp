"""Integration tests verifying auth_mcp protects the MCP server."""

from __future__ import annotations

from auth_mcp.resource_server import (
    ProtectedMCPAppConfig,
    TokenInfo,
    TokenValidator,
    create_protected_mcp_app,
)
from auth_mcp.types import ProtectedResourceMetadata
from http_mcp.server import MCPServer
from pydantic import AnyHttpUrl
from starlette.testclient import TestClient

from app.prompts import PROMPTS
from app.tools import create_tools


class FakeTokenValidator(TokenValidator):
    """Returns a fixed TokenInfo for any token, or None for 'bad-token'."""

    def __init__(self, scopes: tuple[str, ...] = ()) -> None:
        self._scopes = scopes

    async def validate_token(
        self,
        token: str,
        resource: str | None = None,  # noqa: ARG002
    ) -> TokenInfo | None:
        if token == "bad-token":  # noqa: S105
            return None
        return TokenInfo(
            subject="user|123",
            scopes=self._scopes,
            client_id="test-client",
        )


def _jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    body: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


def _init_request() -> dict:
    return _jsonrpc(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.0.1"},
        },
        req_id=0,
    )


def _build_protected_app(
    scopes: tuple[str, ...] = ("tool:search_cpe", "tool:search_cve"),
    *,
    require_authentication: bool = False,
) -> TestClient:
    tools = create_tools(auth_enabled=True)
    mcp_server = MCPServer(tools=tools, prompts=PROMPTS, name="test", version="1.0.0")

    config = ProtectedMCPAppConfig(
        mcp_server=mcp_server,
        token_validator=FakeTokenValidator(scopes=scopes),
        resource_endpoint=ProtectedResourceMetadata(
            resource=AnyHttpUrl("https://api.test/"),
            authorization_servers=(AnyHttpUrl("https://test.auth0.com/"),),
            scopes_supported=("tool:search_cpe", "tool:search_cve"),
        ),
        mcp_path="/mcp",
        require_authentication=require_authentication,
    )
    app = create_protected_mcp_app(config)
    return TestClient(app, raise_server_exceptions=False)


class TestProtectedMCPMetadata:
    def test_metadata_endpoint_accessible_without_token(self) -> None:
        with _build_protected_app() as client:
            resp = client.get("/.well-known/oauth-protected-resource/mcp")
            assert resp.status_code == 200
            data = resp.json()
            assert "https://test.auth0.com/" in data["authorization_servers"]


class TestProtectedMCPToolAccess:
    def test_unauthenticated_lists_no_scoped_tools(self) -> None:
        with _build_protected_app() as client:
            client.post("/mcp", json=_init_request())
            resp = client.post("/mcp", json=_jsonrpc("tools/list"))
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["result"]["tools"]) == 0

    def test_authenticated_with_scopes_lists_tools(self) -> None:
        with _build_protected_app() as client:
            headers = {"Authorization": "Bearer valid-token"}
            client.post("/mcp", json=_init_request(), headers=headers)
            resp = client.post("/mcp", json=_jsonrpc("tools/list"), headers=headers)
            assert resp.status_code == 200
            tool_names = [t["name"] for t in resp.json()["result"]["tools"]]
            assert "search_cpe" in tool_names
            assert "search_cve" in tool_names

    def test_authenticated_without_scopes_lists_no_tools(self) -> None:
        with _build_protected_app(scopes=()) as client:
            headers = {"Authorization": "Bearer valid-token"}
            client.post("/mcp", json=_init_request(), headers=headers)
            resp = client.post("/mcp", json=_jsonrpc("tools/list"), headers=headers)
            assert resp.status_code == 200
            assert len(resp.json()["result"]["tools"]) == 0

    def test_invalid_token_returns_401(self) -> None:
        with _build_protected_app(require_authentication=True) as client:
            resp = client.post(
                "/mcp",
                json=_init_request(),
                headers={"Authorization": "Bearer bad-token"},
            )
            assert resp.status_code == 401
            assert "WWW-Authenticate" in resp.headers

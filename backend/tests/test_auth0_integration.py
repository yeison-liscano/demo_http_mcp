"""Integration tests verifying auth_mcp protects the MCP server."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from auth_mcp.resource_server import (
    ProtectedMCPAppConfig,
    TokenInfo,
    TokenValidator,
    create_protected_mcp_app,
)
from auth_mcp.types import AuthorizationTransportPolicy, ProtectedResourceMetadata
from http_mcp.server import MCPServer
from pydantic import AnyHttpUrl, ValidationError
from starlette.testclient import TestClient

from app.auth0 import Auth0TokenValidator
from app.tools import create_tools
from tests.fakes import SEARCH_ANSWER
from tests.mcp_protocol import mcp_post, tool_call

RESOURCE = "https://api.test/mcp/"
ISSUER = "https://test.auth0.com/"
ALL_SCOPES = ("tool:web_search", "tool:web_fetch")
AUTH = {"Authorization": "Bearer valid-token"}


class FakeTokenValidator(TokenValidator):
    """Returns a fixed TokenInfo for any token, or None for 'bad-token'."""

    def __init__(self, scopes: tuple[str, ...] = (), audience: str | None = None) -> None:
        self._scopes = scopes
        self._audience = audience

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
            audience=self._audience,
        )


def _build_protected_app(
    scopes: tuple[str, ...] = ALL_SCOPES,
    *,
    require_authentication: bool = False,
    validator: TokenValidator | None = None,
) -> TestClient:
    tools = create_tools(auth_enabled=True)
    mcp_server = MCPServer(tools=tools, name="test", version="1.0.0")

    config = ProtectedMCPAppConfig(
        mcp_server=mcp_server,
        token_validator=validator or FakeTokenValidator(scopes=scopes),
        resource_endpoint=ProtectedResourceMetadata(
            resource=AnyHttpUrl(RESOURCE),
            authorization_servers=(ISSUER,),
            scopes_supported=ALL_SCOPES,
        ),
        mcp_path="/mcp",
        require_authentication=require_authentication,
    )
    app = create_protected_mcp_app(config)
    return TestClient(app, raise_server_exceptions=False)


class TestProtectedMCPMetadata:
    def test_metadata_endpoint_accessible_without_token(self) -> None:
        with _build_protected_app() as client:
            resp = client.get("/.well-known/oauth-protected-resource/mcp/")
            assert resp.status_code == HTTPStatus.OK
            data = resp.json()
            assert data["authorization_servers"] == [ISSUER]

    def test_http_authorization_server_is_rejected(self) -> None:
        """http-mcp >= 0.19 refuses non-HTTPS issuers by default, even on localhost."""
        with pytest.raises(ValidationError, match="HTTPS"):
            ProtectedResourceMetadata(
                resource=AnyHttpUrl("http://localhost:8000/mcp/"),
                authorization_servers=("http://localhost:8000",),
            )

    def test_loopback_http_issuer_requires_explicit_opt_in(self) -> None:
        """0.19.0rc2: a validation-context opt-in allows HTTP issuers on loopback only."""
        local_issuer = "http://localhost:9000"
        metadata = ProtectedResourceMetadata.model_validate(
            {"resource": "http://localhost:8000/mcp/", "authorization_servers": [local_issuer]},
            context=AuthorizationTransportPolicy.ALLOW_LOOPBACK_HTTP,
        )
        app = create_protected_mcp_app(
            ProtectedMCPAppConfig(
                mcp_server=MCPServer(tools=(), prompts=(), name="test", version="1.0.0"),
                token_validator=FakeTokenValidator(scopes=()),
                resource_endpoint=metadata,
                mcp_path="/mcp",
            ),
        )
        with TestClient(app) as client:
            resp = client.get("/.well-known/oauth-protected-resource/mcp/")
        assert resp.status_code == HTTPStatus.OK
        # Served verbatim: the opt-in is validation context, never metadata.
        assert resp.json()["authorization_servers"] == [local_issuer]

        with pytest.raises(ValidationError, match="HTTPS"):
            ProtectedResourceMetadata.model_validate(
                {"resource": RESOURCE, "authorization_servers": ["http://auth.example"]},
                context=AuthorizationTransportPolicy.ALLOW_LOOPBACK_HTTP,
            )


class TestProtectedMCPToolAccess:
    def test_unauthenticated_lists_no_scoped_tools(self) -> None:
        with _build_protected_app() as client:
            resp = mcp_post(client, "/mcp/", "tools/list")
            assert resp.status_code == HTTPStatus.OK
            assert resp.json()["result"]["tools"] == []

    def test_authenticated_with_scopes_lists_tools(self) -> None:
        with _build_protected_app() as client:
            resp = mcp_post(client, "/mcp/", "tools/list", headers=AUTH)
            assert resp.status_code == HTTPStatus.OK
            tool_names = {t["name"] for t in resp.json()["result"]["tools"]}
            assert tool_names == {"web_search", "web_fetch"}

    @pytest.mark.usefixtures("fake_agents")
    def test_call_with_scope_runs_the_tool(self) -> None:
        with _build_protected_app(scopes=("tool:web_search",)) as client:
            resp = tool_call(client, "/mcp/", "web_search", {"query": "mcp"}, headers=AUTH)
            assert resp.status_code == HTTPStatus.OK
            assert resp.json()["result"]["structuredContent"]["answer"] == SEARCH_ANSWER["answer"]

    def test_authenticated_without_scopes_lists_no_tools(self) -> None:
        with _build_protected_app(scopes=()) as client:
            resp = mcp_post(client, "/mcp/", "tools/list", headers=AUTH)
            assert resp.status_code == HTTPStatus.OK
            assert resp.json()["result"]["tools"] == []

    def test_call_without_scope_asks_for_step_up(self) -> None:
        # The sub-agent never runs: the request is refused before the tool is invoked.
        with _build_protected_app(scopes=("tool:web_search",)) as client:
            resp = tool_call(
                client,
                "/mcp/",
                "web_fetch",
                {"url": "https://example.com/"},
                headers=AUTH,
            )
            assert resp.status_code == HTTPStatus.FORBIDDEN
            challenge = resp.headers["WWW-Authenticate"]
            assert 'error="insufficient_scope"' in challenge
            assert 'scope="tool:web_fetch"' in challenge

    def test_invalid_token_returns_401(self) -> None:
        with _build_protected_app(require_authentication=True) as client:
            resp = mcp_post(
                client,
                "/mcp/",
                "server/discover",
                headers={"Authorization": "Bearer bad-token"},
            )
            assert resp.status_code == HTTPStatus.UNAUTHORIZED
            assert 'error="invalid_token"' in resp.headers["WWW-Authenticate"]

    def test_missing_token_returns_401_without_error_code(self) -> None:
        with _build_protected_app(require_authentication=True) as client:
            resp = mcp_post(client, "/mcp/", "server/discover")
            assert resp.status_code == HTTPStatus.UNAUTHORIZED
            challenge = resp.headers["WWW-Authenticate"]
            assert "resource_metadata=" in challenge
            assert "error=" not in challenge


class TestAudienceBinding:
    """auth_mcp >= 0.19 rejects tokens whose audience names another resource."""

    def test_token_for_other_resource_is_rejected(self) -> None:
        validator = FakeTokenValidator(scopes=ALL_SCOPES, audience="https://other.test/")
        with _build_protected_app(require_authentication=True, validator=validator) as client:
            resp = mcp_post(client, "/mcp/", "tools/list", headers=AUTH)
            assert resp.status_code == HTTPStatus.UNAUTHORIZED

    @pytest.mark.parametrize("aud", [RESOURCE, [RESOURCE, f"{ISSUER}userinfo"]])
    def test_auth0_token_for_this_resource_is_accepted(self, aud: object) -> None:
        mock_client = AsyncMock()
        mock_client.verify_access_token.return_value = {
            "sub": "user|123",
            "scope": " ".join(ALL_SCOPES),
            "aud": aud,
            "exp": 9999999999,
        }
        with patch("app.auth0.ApiClient", return_value=mock_client):
            validator = Auth0TokenValidator(domain="test.auth0.com", audience=RESOURCE)
        with _build_protected_app(require_authentication=True, validator=validator) as client:
            resp = mcp_post(client, "/mcp/", "tools/list", headers=AUTH)
            assert resp.status_code == HTTPStatus.OK
            assert len(resp.json()["result"]["tools"]) == len(ALL_SCOPES)

    def test_auth0_audience_that_is_not_the_resource_is_rejected(self) -> None:
        mock_client = AsyncMock()
        mock_client.verify_access_token.return_value = {
            "sub": "user|123",
            "scope": " ".join(ALL_SCOPES),
            "aud": "https://legacy-api-identifier/",
        }
        with patch("app.auth0.ApiClient", return_value=mock_client):
            validator = Auth0TokenValidator(
                domain="test.auth0.com",
                audience="https://legacy-api-identifier/",
            )
        with _build_protected_app(require_authentication=True, validator=validator) as client:
            resp = mcp_post(client, "/mcp/", "tools/list", headers=AUTH)
            assert resp.status_code == HTTPStatus.UNAUTHORIZED

"""MCP tool integration tests (no auth — tests tool logic directly)."""

from http import HTTPStatus

from http_mcp.server import MCPServer
from pymocks import Mock, with_mock
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from app.prompts import PROMPTS
from app.tools import TOOLS
from tests.conftest import SearchCPECapture, SearchCVECapture
from tests.mcp_protocol import PROTOCOL_VERSION, mcp_post, tool_call

HTTP_OK = HTTPStatus.OK.value
INVALID_PARAMS = -32602
HEADER_MISMATCH = -32020

# Standalone MCP server without auth for testing tool logic
_mcp_server = MCPServer(tools=TOOLS, prompts=PROMPTS, name="test", version="1.0.0")
_app = Starlette(routes=[Mount("/", _mcp_server.app)])


class TestMCPDiscovery:
    def test_server_discover_reports_capabilities(self) -> None:
        with TestClient(_app) as client:
            resp = mcp_post(client, "/", "server/discover")
            assert resp.status_code == HTTP_OK
            result = resp.json()["result"]
            assert result["supportedVersions"] == [PROTOCOL_VERSION]
            assert "tools" in result["capabilities"]
            assert "prompts" in result["capabilities"]

    def test_lists_tools_and_prompts(self) -> None:
        with TestClient(_app) as client:
            tools = mcp_post(client, "/", "tools/list").json()["result"]["tools"]
            prompts = mcp_post(client, "/", "prompts/list").json()["result"]["prompts"]
        assert {t["name"] for t in tools} == {"search_cpe", "search_cve"}
        assert {p["name"] for p in prompts} == {"async_nvd_search", "sync_nvd_search"}

    def test_legacy_initialize_handshake_is_rejected(self) -> None:
        """A pre-2026-07-28 client (initialize without mirrored headers) cannot connect."""
        with TestClient(_app) as client:
            resp = client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0.0.1"},
                    },
                },
            )
            assert resp.status_code == HTTPStatus.BAD_REQUEST
            assert resp.json()["error"]["code"] == HEADER_MISMATCH

    def test_non_loopback_origin_is_refused(self) -> None:
        with TestClient(_app) as client:
            resp = mcp_post(client, "/", "tools/list", headers={"Origin": "https://evil.example"})
            assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_loopback_browser_origin_is_accepted(self) -> None:
        with TestClient(_app) as client:
            resp = mcp_post(client, "/", "tools/list", headers={"Origin": "http://localhost:5173"})
            assert resp.status_code == HTTP_OK


class TestMCPSearchCVE:
    def test_search_cve_by_id(
        self,
        fake_search_cve: SearchCVECapture,  # noqa: ARG002
        mock_search_cve: Mock,
    ) -> None:
        with with_mock(mock_search_cve), TestClient(_app) as client:
            resp = tool_call(client, "/", "search_cve", {"cve_id": "CVE-2023-44487"})
            assert resp.status_code == HTTP_OK
            data = resp.json()
            assert "result" in data
            assert data["result"]["isError"] is False
            content = data["result"]["structuredContent"]
            assert len(content["cves"]) == 1
            assert content["cves"][0]["id"] == "CVE-2023-44487"

    def test_search_cve_no_filters_returns_error(self) -> None:
        with TestClient(_app) as client:
            resp = tool_call(client, "/", "search_cve", {})
            assert resp.status_code == HTTP_OK
            data = resp.json()
            assert data["error"]["code"] == INVALID_PARAMS
            assert "At least one search filter" in data["error"]["message"]


class TestMCPSearchCPE:
    def test_search_cpe(
        self,
        fake_search_cpe: SearchCPECapture,  # noqa: ARG002
        mock_search_cpe: Mock,
    ) -> None:
        with with_mock(mock_search_cpe), TestClient(_app) as client:
            resp = tool_call(client, "/", "search_cpe", {"product": "curl", "version": "8.4.0"})
            assert resp.status_code == HTTP_OK
            data = resp.json()
            assert "result" in data
            assert data["result"]["isError"] is False
            content = data["result"]["structuredContent"]
            assert len(content["cpes"]) == 1
            assert "curl" in content["cpes"][0]["cpeName"]

    def test_tool_name_header_must_match_body(self) -> None:
        with TestClient(_app) as client:
            resp = tool_call(
                client,
                "/",
                "search_cpe",
                {"product": "curl", "version": "8.4.0"},
                headers={"Mcp-Name": "search_cve"},
            )
            assert resp.status_code == HTTPStatus.BAD_REQUEST
            assert resp.json()["error"]["code"] == HEADER_MISMATCH

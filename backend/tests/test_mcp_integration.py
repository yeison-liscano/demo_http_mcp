"""MCP protocol integration tests for the web tools (no auth; sub-agents faked)."""

from http import HTTPStatus

import pytest
from http_mcp.server import MCPServer
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from app.tools import TOOLS
from tests.fakes import FETCH_ANSWER, SEARCH_ANSWER
from tests.mcp_protocol import PROTOCOL_VERSION, mcp_post, tool_call

HTTP_OK = HTTPStatus.OK.value
INVALID_PARAMS = -32602
METHOD_NOT_FOUND = -32601
HEADER_MISMATCH = -32020

# Standalone MCP server without auth for testing tool logic
_mcp_server = MCPServer(tools=TOOLS, name="test", version="1.0.0")
_app = Starlette(routes=[Mount("/", _mcp_server.app)])


class TestMCPDiscovery:
    def test_server_discover_reports_capabilities(self) -> None:
        with TestClient(_app) as client:
            resp = mcp_post(client, "/", "server/discover")
            assert resp.status_code == HTTP_OK
            result = resp.json()["result"]
            assert result["supportedVersions"] == [PROTOCOL_VERSION]
            assert set(result["capabilities"]) == {"tools"}

    def test_lists_web_tools(self) -> None:
        with TestClient(_app) as client:
            tools = mcp_post(client, "/", "tools/list").json()["result"]["tools"]
        assert {t["name"] for t in tools} == {"web_search", "web_fetch"}
        for tool in tools:
            assert tool["annotations"]["readOnlyHint"] is True
            assert tool["annotations"]["openWorldHint"] is True
            assert "prompt_injection_detections" in tool["outputSchema"]["properties"]

    def test_prompts_are_not_served(self) -> None:
        with TestClient(_app) as client:
            resp = mcp_post(client, "/", "prompts/list")
            assert resp.json()["error"]["code"] == METHOD_NOT_FOUND

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


@pytest.mark.usefixtures("fake_agents")
class TestWebTools:
    def test_web_search(self) -> None:
        with TestClient(_app) as client:
            resp = tool_call(client, "/", "web_search", {"query": "what is MCP?"})
        assert resp.status_code == HTTP_OK
        result = resp.json()["result"]
        assert result["isError"] is False
        assert result["structuredContent"] == {
            **SEARCH_ANSWER,
            "prompt_injection_detections": [],
        }

    def test_web_fetch(self) -> None:
        with TestClient(_app) as client:
            resp = tool_call(client, "/", "web_fetch", {"url": "https://example.com/"})
        assert resp.status_code == HTTP_OK
        result = resp.json()["result"]
        assert result["isError"] is False
        assert result["structuredContent"]["answer"] == FETCH_ANSWER["answer"]

    def test_tool_name_header_must_match_body(self) -> None:
        with TestClient(_app) as client:
            resp = tool_call(
                client,
                "/",
                "web_search",
                {"query": "mcp"},
                headers={"Mcp-Name": "web_fetch"},
            )
            assert resp.status_code == HTTPStatus.BAD_REQUEST
            assert resp.json()["error"]["code"] == HEADER_MISMATCH


class TestInvalidArguments:
    """Rejected before any sub-agent runs, so no fake is needed."""

    @pytest.mark.parametrize(
        ("tool", "arguments"),
        [
            ("web_search", {}),
            ("web_search", {"query": ""}),
            ("web_search", {"query": "x" * 501}),
            ("web_fetch", {}),
            ("web_fetch", {"url": "file:///etc/passwd"}),
            ("web_fetch", {"url": "not a url"}),
            ("web_fetch", {"url": "https://example.com/", "question": "x" * 501}),
        ],
    )
    def test_invalid_arguments_return_invalid_params(
        self,
        tool: str,
        arguments: dict[str, object],
    ) -> None:
        with TestClient(_app) as client:
            resp = tool_call(client, "/", tool, arguments)
        assert resp.status_code == HTTP_OK
        assert resp.json()["error"]["code"] == INVALID_PARAMS

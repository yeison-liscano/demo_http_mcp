import os
from http import HTTPStatus

os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")

from pymocks import Mock, with_mock
from starlette.testclient import TestClient

from app.app import app
from tests.conftest import SearchCPECapture, SearchCVECapture

HTTP_OK = HTTPStatus.OK.value


def _jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    """Build a JSON-RPC 2.0 request."""
    body: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


def _init_request() -> dict:
    """MCP initialize request."""
    return _jsonrpc(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.0.1"},
        },
        req_id=0,
    )


def _tool_call(name: str, arguments: dict, req_id: int = 1) -> dict:
    """MCP tool call request."""
    return _jsonrpc("tools/call", {"name": name, "arguments": arguments}, req_id)


class TestMCPSearchCVE:
    def test_search_cve_by_id(
        self,
        fake_search_cve: SearchCVECapture,  # noqa: ARG002
        mock_search_cve: Mock,
    ) -> None:
        with with_mock(mock_search_cve), TestClient(app) as client:
            # Initialize the MCP session
            init_resp = client.post("/mcp/", json=_init_request())
            assert init_resp.status_code == HTTP_OK

            # Call the search_cve tool
            resp = client.post(
                "/mcp/",
                json=_tool_call("search_cve", {"cve_id": "CVE-2023-44487"}),
            )
            assert resp.status_code == HTTP_OK
            data = resp.json()
            assert "result" in data
            assert data["result"]["isError"] is False
            content = data["result"]["structuredContent"]
            assert len(content["cves"]) == 1
            assert content["cves"][0]["id"] == "CVE-2023-44487"

    def test_search_cve_no_filters_returns_error(self) -> None:
        with TestClient(app) as client:
            init_resp = client.post("/mcp/", json=_init_request())
            assert init_resp.status_code == HTTP_OK

            resp = client.post(
                "/mcp/",
                json=_tool_call("search_cve", {}),
            )
            assert resp.status_code == HTTP_OK
            data = resp.json()
            # Validation error — should be an error response
            assert "error" in data


class TestMCPSearchCPE:
    def test_search_cpe(
        self,
        fake_search_cpe: SearchCPECapture,  # noqa: ARG002
        mock_search_cpe: Mock,
    ) -> None:
        with with_mock(mock_search_cpe), TestClient(app) as client:
            init_resp = client.post("/mcp/", json=_init_request())
            assert init_resp.status_code == HTTP_OK

            resp = client.post(
                "/mcp/",
                json=_tool_call(
                    "search_cpe",
                    {"product": "curl", "version": "8.4.0"},
                ),
            )
            assert resp.status_code == HTTP_OK
            data = resp.json()
            assert "result" in data
            assert data["result"]["isError"] is False
            content = data["result"]["structuredContent"]
            assert len(content["cpes"]) == 1
            assert "curl" in content["cpes"][0]["cpeName"]

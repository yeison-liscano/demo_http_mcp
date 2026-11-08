"""Helpers for building MCP 2026-07-28 requests (the only revision http-mcp >= 0.17 serves).

The revision has no `initialize` handshake: every request restates the protocol version
and client capabilities in `params._meta`, and mirrors routing values into headers that
the server checks against the body.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx2
    from starlette.testclient import TestClient

PROTOCOL_VERSION = "2026-07-28"
_NAMED_METHODS = frozenset({"tools/call", "prompts/get"})


def mcp_request(
    method: str,
    params: dict[str, Any] | None = None,
    req_id: int = 1,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Return the JSON-RPC body and the mirrored MCP headers for one request."""
    params = dict(params or {})
    params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "0.0.1"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    headers = {"MCP-Protocol-Version": PROTOCOL_VERSION, "Mcp-Method": method}
    if method in _NAMED_METHODS:
        headers["Mcp-Name"] = params["name"]
    body = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    return body, headers


def mcp_post(
    client: TestClient,
    path: str,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    req_id: int = 1,
    headers: dict[str, str] | None = None,
) -> httpx2.Response:
    """POST one MCP request, merging any extra headers (e.g. Authorization, Origin)."""
    body, mcp_headers = mcp_request(method, params, req_id)
    return client.post(path, json=body, headers={**mcp_headers, **(headers or {})})


def tool_call(
    client: TestClient,
    path: str,
    name: str,
    arguments: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> httpx2.Response:
    return mcp_post(
        client,
        path,
        "tools/call",
        {"name": name, "arguments": arguments},
        headers=headers,
    )

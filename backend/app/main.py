import asyncio

import uvicorn
from http_mcp.server import MCPServer

from app.tools import TOOLS


def run_http() -> None:
    """Serve the Auth0-protected MCP app on http://localhost:8000/mcp/."""
    # Import string, not the object: importing app.app builds the Auth0 validator,
    # which needs AUTH0_* settings that stdio mode does not.
    uvicorn.run("app.app:app", host="localhost", port=8000)


def run_stdio() -> None:
    """Serve the MCP server over stdio (no authentication, tools unscoped)."""
    stdio_server = MCPServer(tools=TOOLS, name="test", version="1.0.0")
    asyncio.run(stdio_server.serve_stdio())

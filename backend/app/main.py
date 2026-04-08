import asyncio
import os

import uvicorn
from http_mcp.server import MCPServer

from app.app import fast_app
from app.prompts import PROMPTS
from app.tools import TOOLS


def run_http() -> None:
    uvicorn.run(fast_app, host="localhost", port=8000)


def run_stdio() -> None:
    stdio_server = MCPServer(tools=TOOLS, prompts=PROMPTS, name="test", version="1.0.0")
    request_headers = {
        "Authorization": os.getenv("NVD_API_KEY", ""),
    }
    asyncio.run(stdio_server.serve_stdio(request_headers), debug=True)

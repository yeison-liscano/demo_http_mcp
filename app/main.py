import asyncio
import os

import uvicorn

from app.app import app, mcp_server


def run_http() -> None:
    uvicorn.run(app, host="localhost", port=8000)


def run_stdio() -> None:
    request_headers = {
        "Authorization": os.getenv("NVD_API_KEY", ""),
    }
    asyncio.run(mcp_server.serve_stdio(request_headers), debug=True)

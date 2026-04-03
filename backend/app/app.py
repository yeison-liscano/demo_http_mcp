from __future__ import annotations as _annotations

import json
import os
from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import fastapi
import httpx
import logfire
import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from http_mcp.server import MCPServer
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from typing_extensions import TypedDict

from app.agen_memory import AgentMemory as Database
from app.prompts import PROMPTS
from app.tools import TOOLS

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()

agent = Agent("gemini-2.5-pro")
THIS_DIR = Path(__file__).parent
BACKEND_DIR = THIS_DIR.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: fastapi.FastAPI) -> AsyncIterator[dict[str, Database]]:
    async with Database.connect() as db:
        yield {"db": db}


app = FastAPI(
    lifespan=lifespan,
    title="Vulnerability Agent",
    description="A vulnerability agent that can help you check for vulnerabilities a dependency",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logfire.instrument_fastapi(app)


mcp_server = MCPServer(tools=TOOLS, prompts=PROMPTS, name="test", version="1.0.0")

app.mount(
    "/mcp",
    mcp_server.app,
)


async def get_db(request: Request) -> Database:
    return request.state.db


@app.get("/chat/")
async def get_chat(database: Annotated[Database, Depends(get_db)]) -> Response:
    msgs = await database.get_messages()
    return Response(
        b"\n".join(json.dumps(to_chat_message(m)).encode("utf-8") for m in msgs),
        media_type="text/plain",
    )


class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    role: Literal["user", "model"]
    timestamp: str
    content: str


def to_chat_message(m: ModelMessage) -> ChatMessage:
    first_part = m.parts[0]
    if isinstance(m, ModelRequest):
        if isinstance(first_part, UserPromptPart):
            return {
                "role": "user",
                "timestamp": first_part.timestamp.isoformat(),
                "content": str(first_part.content),
            }
    elif isinstance(m, ModelResponse) and isinstance(first_part, TextPart):
        return {
            "role": "model",
            "timestamp": m.timestamp.isoformat(),
            "content": first_part.content,
        }
    msg = f"Unexpected message type for chat app: {m}"
    raise UnexpectedModelBehavior(msg)


@app.post("/chat/")
async def post_chat(
    prompt: Annotated[str, fastapi.Form()],
    database: Annotated[Database, Depends(get_db)],
) -> StreamingResponse:
    async def stream_messages() -> AsyncIterator[bytes]:
        """Streams new line delimited JSON `Message`s to the client."""
        # stream the user prompt so that can be displayed straight away
        yield (
            json.dumps(
                {
                    "role": "user",
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                    "content": prompt,
                },
            ).encode("utf-8")
            + b"\n"
        )

        http_client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {os.getenv('NVD_API_KEY')}"},
            timeout=httpx.Timeout(60.0),
        )
        server = MCPServerStreamableHTTP(
            url="http://localhost:8000/mcp/",
            http_client=http_client,
            timeout=60,
        )
        # get the chat history so far to pass as context to the agent
        messages = await database.get_messages()
        # run the agent with the user prompt and the chat history
        async with agent.run_stream(prompt, message_history=messages, toolsets=[server]) as result:
            async for text in result.stream(debounce_by=0.01):
                # text here is a `str` and the frontend wants
                # JSON encoded ModelResponse, so we create one
                m = ModelResponse(parts=[TextPart(text)], timestamp=result.timestamp())
                yield json.dumps(to_chat_message(m)).encode("utf-8") + b"\n"

        # add new messages (e.g. the user prompt and the agent response in this case)
        await database.add_messages(result.new_messages_json())

    return StreamingResponse(stream_messages(), media_type="text/plain")


def _mount_frontend() -> None:
    """Mount the React frontend build if it exists (production mode)."""
    if FRONTEND_DIR.is_dir():
        # Serve index.html for the root and any non-API routes (SPA fallback)
        @app.get("/")
        async def index() -> Response:
            index_html = FRONTEND_DIR / "index.html"
            return Response(index_html.read_text(), media_type="text/html")

        # Serve static assets (JS, CSS, images, etc.)
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

        # SPA catch-all: serve index.html for any unmatched routes
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> Response:
            # Try to serve the file if it exists, otherwise return index.html
            file_path = FRONTEND_DIR / full_path
            if file_path.is_file():
                return Response(file_path.read_bytes(), media_type="application/octet-stream")
            index_html = FRONTEND_DIR / "index.html"
            return Response(index_html.read_text(), media_type="text/html")


_mount_frontend()


def main() -> None:
    uvicorn.run("app.app:app", reload=True, reload_dirs=[str(THIS_DIR)])

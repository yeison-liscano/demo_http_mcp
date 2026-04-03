from __future__ import annotations as _annotations

import json
import os
from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import fastapi
import logfire
import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from http_mcp.server import MCPServer
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from typing_extensions import TypedDict

from app.agen_memory import AgentMemory as Database
from app.agent import stream_messages
from app.prompts import PROMPTS
from app.tools import TOOLS

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()

agent = Agent("ollama:gemma4")
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
        b"\n".join(
            json.dumps(cm).encode("utf-8")
            for m in msgs
            if (cm := to_chat_message(m)) is not None
        ),
        media_type="text/plain",
    )


class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    type: Literal["text"]
    role: Literal["user", "model"]
    timestamp: str
    content: str


def to_chat_message(m: ModelMessage) -> ChatMessage | None:
    if isinstance(m, ModelRequest):
        for req_part in m.parts:
            if isinstance(req_part, UserPromptPart):
                return {
                    "type": "text",
                    "role": "user",
                    "timestamp": req_part.timestamp.isoformat(),
                    "content": str(req_part.content),
                }
    elif isinstance(m, ModelResponse):
        for resp_part in m.parts:
            if isinstance(resp_part, TextPart):
                return {
                    "type": "text",
                    "role": "model",
                    "timestamp": m.timestamp.isoformat(),
                    "content": resp_part.content,
                }
    return None


@app.post("/chat/")
async def post_chat(
    prompt: Annotated[str, fastapi.Form()],
    database: Annotated[Database, Depends(get_db)],
) -> StreamingResponse:
    async def _stream_messages() -> AsyncIterator[bytes]:
        """Streams new line delimited JSON `Message`s to the client."""
        # stream the user prompt so that can be displayed straight away
        yield (
            json.dumps(
                {
                    "type": "text",
                    "role": "user",
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                    "content": prompt,
                },
            ).encode("utf-8")
            + b"\n"
        )
        async for chat_message in stream_messages(agent, prompt, database):
            yield (chat_message.model_dump_json() + "\n").encode("utf-8")

    return StreamingResponse(_stream_messages(), media_type="text/plain")


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

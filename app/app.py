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
from fastapi import Depends, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
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


@asynccontextmanager
async def lifespan(_app: fastapi.FastAPI) -> AsyncIterator[dict[str, Database]]:
    async with Database.connect() as db:
        yield {"db": db}


app = fastapi.FastAPI(lifespan=lifespan)
logfire.instrument_fastapi(app)

mcp_server = MCPServer(tools=TOOLS, prompts=PROMPTS, name="test", version="1.0.0")

app.mount(
    "/mcp",
    mcp_server.app,
)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse((THIS_DIR / "chat_app.html"), media_type="text/html")


@app.get("/chat_app.ts")
async def main_ts() -> FileResponse:
    """Get the raw typescript code, it's compiled in the browser, forgive me."""
    return FileResponse((THIS_DIR / "chat_app.ts"), media_type="text/plain")


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


def main() -> None:
    uvicorn.run("app.app:app", reload=True, reload_dirs=[str(THIS_DIR)])

from __future__ import annotations as _annotations

import json
from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import fastapi
import logfire
import uvicorn
from auth_mcp.resource_server import ProtectedMCPAppConfig, create_protected_mcp_app
from auth_mcp.types import AuthorizationServerMetadata, ProtectedResourceMetadata
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from http_mcp.server import MCPServer
from pydantic import AnyHttpUrl
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from app.agen_memory import AgentMemory as Database
from app.agent import stream_messages
from app.auth0 import Auth0TokenValidator
from app.auth0.client_store import Auth0ClientStore
from app.config import Config
from app.prompts import PROMPTS
from app.tools import create_tools

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()

config = Config()
agent = Agent("ollama:gemma4")
THIS_DIR = Path(__file__).parent
BACKEND_DIR = THIS_DIR.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: fastapi.FastAPI) -> AsyncIterator[dict[str, Database]]:
    async with Database.connect() as db:
        yield {"db": db}


fast_app = FastAPI(
    title="Vulnerability Agent",
    description="A vulnerability agent that can help you check for vulnerabilities a dependency",
)


fast_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

logfire.instrument_fastapi(fast_app)

tools = create_tools(auth_enabled=config.auth0_enabled)
mcp_server = MCPServer(tools=tools, prompts=PROMPTS, name="test", version="1.0.0")

auth0_domain = config.auth0_domain
auth0_audience = config.auth0_audience
tool_scopes = ("tool:search_cpe", "tool:search_cve")

client_store = Auth0ClientStore(
    domain=auth0_domain,
    mcp_app_client_id=config.auth0_mcp_app_client_id,
    mgmt_client_id=config.auth0_mgmt_client_id,
    mgmt_client_secret=config.auth0_mgmt_client_secret,
)

protected_config = ProtectedMCPAppConfig(
    mcp_server=mcp_server,
    token_validator=Auth0TokenValidator(domain=auth0_domain, audience=auth0_audience),
    resource_endpoint=ProtectedResourceMetadata(
        resource=AnyHttpUrl("http://localhost:8000/mcp/"),
        authorization_servers=(AnyHttpUrl("http://localhost:8000"),),
        scopes_supported=tool_scopes,
    ),
    authorization_server_metadata=AuthorizationServerMetadata(
        issuer=AnyHttpUrl(f"https://{auth0_domain}/"),
        authorization_endpoint=AnyHttpUrl(f"https://{auth0_domain}/authorize"),
        token_endpoint=AnyHttpUrl(f"https://{auth0_domain}/oauth/token"),
        registration_endpoint=AnyHttpUrl("http://localhost:8000/register"),
    ),
    client_store=client_store,
    mcp_path="/mcp",
    require_authentication=True,
)
app = create_protected_mcp_app(protected_config, lifespan=lifespan)



async def get_db(request: Request) -> Database:
    return request.state.db


# SECURITY: These chat endpoints are intentionally unauthenticated.
# If exposed beyond localhost, add authentication to prevent unauthorized
# access to conversation history and LLM compute.
@fast_app.get("/chat/")
async def get_chat(database: Annotated[Database, Depends(get_db)]) -> Response:
    msgs = await database.get_messages()
    lines: list[bytes] = []
    for m in msgs:
        lines.extend(json.dumps(event).encode("utf-8") for event in to_chat_events(m))
    return Response(b"\n".join(lines), media_type="text/plain")


def to_chat_events(m: ModelMessage) -> list[dict[str, Any]]:  # noqa: C901
    """Convert a stored ModelMessage into frontend StreamEvent dicts."""
    events: list[dict[str, Any]] = []
    if isinstance(m, ModelRequest):
        for req_part in m.parts:
            if isinstance(req_part, UserPromptPart):
                events.append(
                    {
                        "type": "text",
                        "role": "user",
                        "timestamp": req_part.timestamp.isoformat(),
                        "content": str(req_part.content),
                    },
                )
            elif isinstance(req_part, ToolReturnPart):
                events.append(
                    {
                        "type": "tool_result",
                        "tool_call_id": req_part.tool_call_id,
                        "tool_name": req_part.tool_name,
                        "args": {},
                        "result": req_part.content,
                        "timestamp": req_part.timestamp.isoformat() if req_part.timestamp else "",
                    },
                )
    elif isinstance(m, ModelResponse):
        for resp_part in m.parts:
            if isinstance(resp_part, TextPart):
                events.append(
                    {
                        "type": "text",
                        "role": "model",
                        "timestamp": m.timestamp.isoformat(),
                        "content": resp_part.content,
                    },
                )
            elif isinstance(resp_part, ThinkingPart):
                events.append(
                    {
                        "type": "thinking",
                        "content": resp_part.content,
                        "timestamp": m.timestamp.isoformat(),
                    },
                )
            elif isinstance(resp_part, ToolCallPart):
                args: dict[str, Any] = {}
                if isinstance(resp_part.args, str):
                    try:
                        args = json.loads(resp_part.args)
                    except json.JSONDecodeError:
                        args = {"raw": resp_part.args}
                elif isinstance(resp_part.args, dict):
                    args = resp_part.args
                events.append(
                    {
                        "type": "tool_call",
                        "tool_call_id": resp_part.tool_call_id,
                        "tool_name": resp_part.tool_name,
                        "args": args,
                        "timestamp": m.timestamp.isoformat(),
                    },
                )
    return events


@fast_app.post("/chat/")
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
        @fast_app.get("/")
        async def index() -> Response:
            index_html = FRONTEND_DIR / "index.html"
            return Response(index_html.read_text(), media_type="text/html")

        # Serve static assets (JS, CSS, images, etc.)
        fast_app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

        # SPA catch-all: serve index.html for any unmatched routes
        @fast_app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> Response:
            file_path = (FRONTEND_DIR / full_path).resolve()
            if not file_path.is_relative_to(FRONTEND_DIR.resolve()):
                return Response(status_code=404)
            if file_path.is_file():
                return Response(file_path.read_bytes(), media_type="application/octet-stream")
            index_html = FRONTEND_DIR / "index.html"
            return Response(index_html.read_text(), media_type="text/html")


_mount_frontend()

app.mount("/api", fast_app)

def main() -> None:
    uvicorn.run("app.app:app", reload=True, reload_dirs=[str(THIS_DIR)])

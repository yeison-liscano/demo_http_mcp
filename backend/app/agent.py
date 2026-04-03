import json
import logging
import os
from collections.abc import AsyncIterable, AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    HandleResponseEvent,
    ModelResponseStreamEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPartDelta,
    ToolReturnPart,
)
from pydantic_ai.run import AgentRun

from app.agen_memory import AgentMemory

LOGGER = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """Format of messages sent to the browser."""

    role: Literal["user", "model"]
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    more_body: bool = True


class ToolExecutionRequest(BaseModel):
    confirmation_id: str
    tool_name: str
    args: dict


class ToolExecutionResult(BaseModel):
    tool_call_id: str
    tool_name: str
    args: dict
    result: Any


def _process_model_response_stream_event(
    model_response_stream_event: ModelResponseStreamEvent,
) -> ChatMessage | None:
    if isinstance(model_response_stream_event, PartStartEvent) and isinstance(
        model_response_stream_event.part,
        TextPart,
    ):
        return ChatMessage(
            content=model_response_stream_event.part.content,
            more_body=True,
            role="model",
        )
    if isinstance(model_response_stream_event, PartDeltaEvent) and isinstance(
        model_response_stream_event.delta,
        TextPartDelta | ThinkingPartDelta,
    ):
        return ChatMessage(
            content=model_response_stream_event.delta.content_delta or "",
            role="model",
            more_body=True,
        )

    return None


def _process_handle_response_event(
    handle_response_event: HandleResponseEvent,
) -> ToolReturnPart | ToolExecutionRequest | None:
    if isinstance(handle_response_event, FunctionToolResultEvent) and isinstance(
        handle_response_event.result,
        ToolReturnPart,
    ):
        return handle_response_event.result
    if isinstance(handle_response_event, FunctionToolCallEvent):
        part = handle_response_event.part
        args: dict | None = None
        try:
            args = json.loads(part.args) if isinstance(part.args, str) else part.args
        except json.JSONDecodeError:
            args = {"args": part.args}
        if args is None:
            args = {}
        return ToolExecutionRequest(
            confirmation_id=part.tool_call_id,
            tool_name=part.tool_name,
            args=args,
        )
    return None


def _build_tool_execution_result(
    tool_part: ToolReturnPart,
    called_tools: dict[str, ToolExecutionRequest],
) -> ToolExecutionResult:
    args = (
        called_tools[tool_part.tool_call_id].args
        if tool_part.tool_call_id in called_tools
        else {}
    )
    return ToolExecutionResult(
        tool_call_id=tool_part.tool_call_id,
        tool_name=tool_part.tool_name,
        args=args,
        result=tool_part.content,
    )


async def _process_tool_events(
    handle_stream: AsyncIterable[HandleResponseEvent],
) -> None:
    async for event in handle_stream:
        tool_part = _process_handle_response_event(event)
        if tool_part is None:
            continue
        print(tool_part)


async def _process_model_events(
    request_stream: AsyncIterable[ModelResponseStreamEvent],
) -> AsyncIterator[ChatMessage]:
    async for request_event in request_stream:
        processed_event = _process_model_response_stream_event(request_event)
        if processed_event is None:
            continue
        yield processed_event


async def _iterate_agent_nodes(
    run: AgentRun[None, str],
    database: AgentMemory,
) -> AsyncIterator[ChatMessage]:
    async for node in run:
        if Agent.is_call_tools_node(node):
            async with node.stream(run.ctx) as handle_stream:
                await _process_tool_events(handle_stream)
            continue
        if Agent.is_model_request_node(node):
            async with node.stream(run.ctx) as request_stream:
                async for response in _process_model_events(request_stream):
                    yield response
            continue
        if Agent.is_end_node(node):
            yield ChatMessage(role="model", content="\n\n")
            if run.result:
                await database.add_messages(run.result.new_messages_json())


async def stream_messages(
    agent: Agent,
    prompt: str,
    database: AgentMemory,
) -> AsyncIterator[ChatMessage]:
    messages = await database.get_messages()
    http_client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {os.getenv('NVD_API_KEY')}"},
        timeout=httpx.Timeout(60.0),
    )
    server = MCPServerStreamableHTTP(
        url="http://localhost:8000/mcp/",
        http_client=http_client,
        timeout=60,
    )
    async with (
        agent.iter(
            prompt,
            message_history=messages,
            toolsets=[server],
        ) as run,
    ):
        try:
            async for response in _iterate_agent_nodes(run, database):
                yield response
        except ModelHTTPError:
            LOGGER.exception("Error streaming messages")
            yield ChatMessage(
                role="model",
                content="Error Streaming",
                more_body=False,
            )
            return

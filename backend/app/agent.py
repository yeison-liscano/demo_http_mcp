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
    ThinkingPart,
    ThinkingPartDelta,
    ToolReturnPart,
)
from pydantic_ai.run import AgentRun

from app.agen_memory import AgentMemory

LOGGER = logging.getLogger(__name__)


class TextEvent(BaseModel):
    """Text chunk streamed to the browser."""

    type: Literal["text"] = "text"
    role: Literal["user", "model"]
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    more_body: bool = True


class ToolCallEvent(BaseModel):
    """Emitted when the model invokes a tool."""

    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    args: dict
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ToolResultEvent(BaseModel):
    """Emitted when a tool returns its result."""

    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    tool_name: str
    args: dict
    result: Any
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ThinkingEvent(BaseModel):
    """Emitted for model thinking/reasoning chunks."""

    type: Literal["thinking"] = "thinking"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


StreamEvent = TextEvent | ToolCallEvent | ToolResultEvent | ThinkingEvent


def _process_model_response_stream_event(
    model_response_stream_event: ModelResponseStreamEvent,
) -> TextEvent | ThinkingEvent | None:
    if isinstance(model_response_stream_event, PartStartEvent):
        if isinstance(model_response_stream_event.part, TextPart):
            return TextEvent(
                content=model_response_stream_event.part.content,
                more_body=True,
                role="model",
            )
        if isinstance(model_response_stream_event.part, ThinkingPart):
            return ThinkingEvent(content=model_response_stream_event.part.content)
    if isinstance(model_response_stream_event, PartDeltaEvent):
        if isinstance(model_response_stream_event.delta, TextPartDelta):
            return TextEvent(
                content=model_response_stream_event.delta.content_delta or "",
                role="model",
                more_body=True,
            )
        if isinstance(model_response_stream_event.delta, ThinkingPartDelta):
            return ThinkingEvent(
                content=model_response_stream_event.delta.content_delta or "",
            )

    return None


def _process_handle_response_event(
    handle_response_event: HandleResponseEvent,
    called_tools: dict[str, ToolCallEvent],
) -> ToolCallEvent | ToolResultEvent | None:
    if isinstance(handle_response_event, FunctionToolResultEvent) and isinstance(
        handle_response_event.result,
        ToolReturnPart,
    ):
        tool_part = handle_response_event.result
        call = called_tools.get(tool_part.tool_call_id)
        return ToolResultEvent(
            tool_call_id=tool_part.tool_call_id,
            tool_name=tool_part.tool_name,
            args=call.args if call else {},
            result=tool_part.content,
        )
    if isinstance(handle_response_event, FunctionToolCallEvent):
        part = handle_response_event.part
        args: dict | None = None
        try:
            args = json.loads(part.args) if isinstance(part.args, str) else part.args
        except json.JSONDecodeError:
            args = {"args": part.args}
        if args is None:
            args = {}
        event = ToolCallEvent(
            tool_call_id=part.tool_call_id,
            tool_name=part.tool_name,
            args=args,
        )
        called_tools[event.tool_call_id] = event
        return event
    return None


async def _process_tool_events(
    handle_stream: AsyncIterable[HandleResponseEvent],
    called_tools: dict[str, ToolCallEvent],
) -> AsyncIterator[ToolCallEvent | ToolResultEvent]:
    async for event in handle_stream:
        tool_event = _process_handle_response_event(event, called_tools)
        if tool_event is None:
            continue
        yield tool_event


async def _process_model_events(
    request_stream: AsyncIterable[ModelResponseStreamEvent],
) -> AsyncIterator[TextEvent | ThinkingEvent]:
    async for request_event in request_stream:
        processed_event = _process_model_response_stream_event(request_event)
        if processed_event is None:
            continue
        yield processed_event


async def _iterate_agent_nodes(
    run: AgentRun[None, str],
    database: AgentMemory,
) -> AsyncIterator[StreamEvent]:
    called_tools: dict[str, ToolCallEvent] = {}
    async for node in run:
        if Agent.is_call_tools_node(node):
            async with node.stream(run.ctx) as handle_stream:
                async for tool_event in _process_tool_events(handle_stream, called_tools):
                    yield tool_event
            continue
        if Agent.is_model_request_node(node):
            async with node.stream(run.ctx) as request_stream:
                async for response in _process_model_events(request_stream):
                    yield response
            continue
        if Agent.is_end_node(node):
            yield TextEvent(role="model", content="\n\n")
            if run.result:
                await database.add_messages(run.result.new_messages_json())


async def stream_messages(
    agent: Agent,
    prompt: str,
    database: AgentMemory,
) -> AsyncIterator[StreamEvent]:
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
            yield TextEvent(
                role="model",
                content="Error Streaming",
                more_body=False,
            )
            return

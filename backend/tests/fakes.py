"""Deterministic stand-ins for the Claude sub-agents: no network, no Anthropic credentials.

Shared by the in-process tests and the stdio subprocess (`test_mcp_client_compat`).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from pydantic_ai.models.test import TestModel

from app.agents import web_fetch_agent, web_search_agent

if TYPE_CHECKING:
    from collections.abc import Iterator

SEARCH_ANSWER = {
    "answer": "MCP is an open protocol that connects AI applications to tools and data.",
    "sources": [{"title": "Model Context Protocol", "url": "https://modelcontextprotocol.io/"}],
}
FETCH_ANSWER = {
    "answer": "Example Domain is reserved for use in documentation examples.",
    "sources": [{"title": "Example Domain", "url": "https://example.com/"}],
}


@contextmanager
def fake_web_agents() -> Iterator[None]:
    """Answer every web tool call with a canned output instead of calling Claude."""
    with (
        web_search_agent.override(
            model=TestModel(call_tools=[], custom_output_args=SEARCH_ANSWER),
        ),
        web_fetch_agent.override(
            model=TestModel(call_tools=[], custom_output_args=FETCH_ANSWER),
        ),
    ):
        yield

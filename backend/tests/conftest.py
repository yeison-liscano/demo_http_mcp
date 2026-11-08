from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

import pytest
from ddgs.ddgs import DDGS  # the class pydantic-ai's DuckDuckGo tool uses (not `ddgs.DDGS`)

from tests.fakes import fake_web_agents

if TYPE_CHECKING:
    from collections.abc import Iterator


def _no_network(*_: object, **__: object) -> NoReturn:
    msg = "tests must not reach the web: patch the search or download"
    raise AssertionError(msg)


@pytest.fixture(autouse=True)
def _block_web_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that would run a real DuckDuckGo search or page download."""
    monkeypatch.setattr(DDGS, "text", _no_network)
    monkeypatch.setattr("pydantic_ai.common_tools.web_fetch.safe_download", _no_network)


@pytest.fixture
def fake_agents() -> Iterator[None]:
    with fake_web_agents():
        yield

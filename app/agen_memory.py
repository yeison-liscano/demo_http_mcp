from __future__ import annotations as _annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator, Callable  # noqa: TC003
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, LiteralString, ParamSpec, TypeVar

import logfire
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
)

THIS_DIR = Path(__file__).parent


P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class AgentMemory:
    con: sqlite3.Connection
    _loop: asyncio.AbstractEventLoop
    _executor: ThreadPoolExecutor

    @classmethod
    @asynccontextmanager
    async def connect(
        cls, file: Path = THIS_DIR / ".chat_app_messages.sqlite",
    ) -> AsyncIterator[AgentMemory]:
        with logfire.span("connect to DB"):
            loop = asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=1)
            con = await loop.run_in_executor(executor, cls._connect, file)
            slf = cls(con, loop, executor)
        try:
            yield slf
        finally:
            await slf._asyncify(con.close)

    @staticmethod
    def _connect(file: Path) -> sqlite3.Connection:
        con = sqlite3.connect(str(file))
        con = logfire.instrument_sqlite3(con)
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS messages (id INT PRIMARY KEY, message_list TEXT);")
        con.commit()
        return con

    async def add_messages(self, messages: bytes) -> None:
        await self._asyncify(
            self._execute,
            "INSERT INTO messages (message_list) VALUES (?);",
            messages,
            commit=True,
        )
        await self._asyncify(self.con.commit)

    async def get_messages(self) -> list[ModelMessage]:
        c = await self._asyncify(self._execute, "SELECT message_list FROM messages order by id")
        rows = await self._asyncify(c.fetchall)
        messages: list[ModelMessage] = []
        for row in rows:
            messages.extend(ModelMessagesTypeAdapter.validate_json(row[0]))
        return messages

    def _execute(self, sql: LiteralString, *args: Any, commit: bool = False) -> sqlite3.Cursor:  # noqa: ANN401
        cur = self.con.cursor()
        cur.execute(sql, args)
        if commit:
            self.con.commit()
        return cur

    async def _asyncify(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        return await self._loop.run_in_executor(
            self._executor,
            partial(func, **kwargs),
            *args,
        )

## test-http-mcp

Demo Model Context Protocol (MCP) server implemented in Python using the
`http-mcp` package. It can run over HTTP (Starlette/Uvicorn) or over stdio,
exposing example Tools and Prompts to any MCP-capable client.

### Requirements

- Python 3.13
- `uv` (recommended) or `pip`

### Install

Using `uv` (recommended):

```bash
uv run python -V            # will create a venv and sync deps from pyproject
```

Using `pip` (alternative):

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install .
```

### Run (HTTP mode)

Starts a Starlette app and mounts the MCP server under `/mcp` on port 8000.

```bash
uv run run-app
# → http://localhost:8000/mcp
```

Example `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "test-http-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "Authorization": "Bearer $TEST_TOKEN"
      }
    }
  }
}
```

Usage with `Gemini`:

```json
{
  "mcpServers": {
    "test": {
      "httpUrl": "http://localhost:8000/mcp/",
      "timeout": 5000,
      "headers": {
        "Authorization": "Bearer TEST_TOKEN"
      }
    }
  }
}
```

### Run (stdio mode)

### Use with Cursor or other MCP clients

Example `.cursor/mcp.json` entry to connect via stdio:

```json
{
  "mcpServers": {
    "test_studio": {
      "command": "uv",
      "args": ["run", "run-stdio"],
      "env": { "AUTHORIZATION_TOKEN": "Bearer TEST_TOKEN" }
    }
  }
}
```

### What this server exposes

- Tools (see `app/tools.py`):
  - `get_weather(location: str, unit: str = "celsius") -> { weather: str }`
  - `get_time() -> { time: str }`
  - `tool_that_access_request(username: str) -> { message: str }` (reads
    `Authorization` from the incoming request headers)
  - `get_called_tools() -> { called_tools: string[] }`
- Prompts (see `app/prompts.py`):
  - `get_advice(topic: str, include_actionable_steps: bool = false)` → returns a
    single user message template

### Project scripts

Two console entry points are defined in `pyproject.toml`:

- `run-app` → `app.main:run_http`
- `run-stdio` → `app.main:run_stdio`

### Development

Common tasks (using `uv`):

```bash
uv run ruff check .           # lint
uv run mypy .                 # type check
uv run pytest                 # tests
uv run mdformat .             # format markdown
```

### Implementation notes

- The Starlette app is defined in `app/main.py` and mounts
  `http_mcp.server.MCPServer` at `/mcp`.
- Tool inputs/outputs are validated with Pydantic v2 models; async tool
  functions receive a typed `ToolArguments` with `inputs`, `context`, and (in
  HTTP mode) `request`.
- A simple `Context` keeps track of called tool names during a session.

### License

MIT — see `LICENSE`.

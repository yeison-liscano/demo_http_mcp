## test-http-mcp

Demo Model Context Protocol (MCP) server implemented in Python using the
`http-mcp` package. It can run over HTTP (Starlette/Uvicorn) or over stdio,
exposing example Tools and Prompts to any MCP-capable client. The project
includes a React frontend that provides a chat interface for querying
vulnerabilities via the NVD (National Vulnerability Database).

<a href="https://glama.ai/mcp/servers/@yeison-liscano/demo_http_mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@yeison-liscano/demo_http_mcp/badge" alt="Demo HTTP Server MCP server" />
</a>

### Project structure

```
test-http-mcp/
├── backend/                 # Python backend (FastAPI + MCP server)
│   ├── app/                 # Application source code
│   │   ├── app.py           # FastAPI app, routes, MCP mount
│   │   ├── main.py          # Entry points (HTTP / stdio)
│   │   ├── agen_memory.py   # SQLite message persistence
│   │   ├── config.py        # Settings via pydantic-settings
│   │   ├── tools/           # MCP tools (CPE/CVE search via NVD)
│   │   └── prompts/         # MCP prompt templates
│   ├── pyproject.toml       # Python deps & scripts
│   ├── uv.lock              # Locked dependencies
│   ├── ruff.toml            # Linter config
│   ├── mypy.ini             # Type-checker config
│   └── .envrc               # direnv auto-activation
├── frontend/                # React + TypeScript frontend (Vite)
│   ├── src/
│   │   ├── components/      # ChatApp, ChatInput, MessageList, MessageBubble
│   │   ├── api.ts           # API client (fetch history, stream messages)
│   │   ├── types.ts         # Shared TypeScript types
│   │   ├── App.tsx          # Root component
│   │   └── App.css          # Styles
│   ├── vite.config.ts       # Vite config with dev proxy
│   └── package.json         # Node dependencies
├── AGENTS.md
├── LICENSE
└── README.md
```

### Requirements

- Python 3.13
- Node.js 18+ and npm
- `uv` (recommended) or `pip`

### Install

Backend (using `uv`):

```bash
cd backend
uv run python -V            # creates a venv and syncs deps from pyproject
```

Backend (using `pip`):

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install .
```

Frontend:

```bash
cd frontend
npm install
```

### Run

#### Development (frontend + backend separately)

Start the backend:

```bash
cd backend
uv run run-app
# → API on http://localhost:8000
# → MCP endpoint on http://localhost:8000/mcp/
```

Start the frontend dev server (in a separate terminal):

```bash
cd frontend
npm run dev
# → UI on http://localhost:5173 (proxies /api/* → backend)
```

#### Production (backend serves the built frontend)

Build the frontend and start the backend:

```bash
cd frontend && npm run build && cd ..
cd backend && uv run run-app
# → Everything on http://localhost:8000
```

### Run (stdio mode)

### Use with Cursor or other MCP clients

Example `.cursor/mcp.json` for HTTP mode:

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

Example `.cursor/mcp.json` entry to connect via stdio:

```json
{
  "mcpServers": {
    "test_studio": {
      "command": "uv",
      "args": ["run", "--project", "backend", "run-stdio"],
      "env": { "AUTHORIZATION_TOKEN": "Bearer TEST_TOKEN" }
    }
  }
}
```

### What this server exposes

- Tools (see `backend/app/tools/`):
  - `search_cpe(product, version, vendor)` — search Common Platform Enumerations via NVD
  - `search_cve(cpe_name)` — search Common Vulnerabilities and Exposures for a given CPE
- Prompts (see `backend/app/prompts/`):
  - `sync_nvd_search(dependency, version)` — simple vulnerability search prompt
  - `async_nvd_search(dependency, version)` — advanced prompt with pre-fetched CVE data

### Project scripts

Two console entry points are defined in `backend/pyproject.toml`:

- `run-app` → `app.main:run_http`
- `run-stdio` → `app.main:run_stdio`
- `run-app-local` → `app.app:main` (with auto-reload)

### Development

Common tasks (run from the `backend/` directory):

```bash
uv run ruff check .           # lint
uv run mypy .                 # type check
uv run pytest                 # tests
uv run mdformat .             # format markdown
```

Frontend tasks (run from the `frontend/` directory):

```bash
npm run dev                   # start dev server
npm run build                 # production build
npm run lint                  # lint with ESLint
npx tsc --noEmit              # type check
```

### Implementation notes

- The FastAPI app is defined in `backend/app/app.py` and mounts
  `http_mcp.server.MCPServer` at `/mcp`.
- The chat interface uses `pydantic-ai` with a Gemini agent that can call
  MCP tools to search for vulnerabilities.
- Chat history is persisted in a local SQLite database via `agen_memory.py`.
- The React frontend streams responses as newline-delimited JSON and renders
  markdown with the `marked` library.
- In production, the backend serves the built frontend from `frontend/dist/`
  with SPA fallback routing.
- In development, Vite proxies `/api/*` requests to the backend on port 8000.

### License

MIT — see `LICENSE`.

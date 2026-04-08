## test-http-mcp

Demo Model Context Protocol (MCP) server implemented in Python using the
`http-mcp` package. It can run over HTTP (Starlette/Uvicorn) or over stdio,
exposing example Tools and Prompts to any MCP-capable client. The project
includes a React frontend that provides a chat interface for querying
vulnerabilities via the NVD (National Vulnerability Database).

[![Chat UI](https://img.youtube.com/vi/BzrVV2y8g1Q/0.jpg)](https://youtube.com/shorts/BzrVV2y8g1Q)

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
│   │   ├── auth0/           # Auth0 integration
│   │   │   ├── __init__.py  # JWT token validator
│   │   │   └── client_store.py # Dynamic client registration (RFC 7591)
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

### Authentication (Auth0)

The MCP endpoint (`/mcp/`) is protected with Auth0 OAuth2 authentication.
Tools require scopes (`tool:search_cpe`, `tool:search_cve`) to be present in
the access token.

#### Required environment variables

| Variable | Description |
|----------|-------------|
| `AUTH0_DOMAIN` | Auth0 tenant domain (e.g. `your-tenant.auth0.com`) |
| `AUTH0_AUDIENCE` | API identifier for token validation |
| `AUTH0_MCP_APP_CLIENT_ID` | Auth0 application client ID for the MCP app |
| `AUTH0_MGMT_CLIENT_ID` | Management API client ID (for dynamic registration) |
| `AUTH0_MGMT_CLIENT_SECRET` | Management API client secret |
| `AUTH0_ENABLED` | Set to `false` to disable scope enforcement (default: `true`) |

Place these in `backend/.env` (git-ignored).

#### App mount structure

| Path | App | Auth |
|------|-----|------|
| `/mcp/` | Protected MCP server | Auth0 Bearer token required |
| `/register` | Dynamic client registration (RFC 7591) | Unauthenticated |
| `/.well-known/` | OAuth/resource metadata | Unauthenticated |
| `/api/chat/` | Chat interface endpoints | Unauthenticated (see note) |
| `/api/` | Frontend static files | Unauthenticated |

> **Note:** The chat endpoints are intentionally unauthenticated for local
> development. Add authentication before exposing beyond localhost.

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

With Auth0 enabled, clients must obtain an OAuth2 access token. The server
supports [RFC 7591 Dynamic Client Registration](https://datatracker.ietf.org/doc/html/rfc7591)
at `/register`, so MCP clients that implement the auth spec will register
automatically.

Example `.cursor/mcp.json` for HTTP mode:

```json
{
  "mcpServers": {
    "test-http-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp/"
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
      "timeout": 5000
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

- The root ASGI app is an Auth0-protected MCP app created by `auth_mcp`,
  which mounts the FastAPI sub-app at `/api`.
- The MCP endpoint at `/mcp/` requires a valid Auth0 Bearer token with
  the appropriate tool scopes.
- Dynamic client registration at `/register` proxies to a pre-created
  Auth0 application, updating its allowed callback URLs. Redirect URIs
  are validated (HTTPS required; HTTP allowed only for localhost).
- The chat interface uses `pydantic-ai` with an Ollama agent that can call
  MCP tools to search for vulnerabilities.
- Chat history is persisted in a local SQLite database via `agen_memory.py`.
- The React frontend streams responses as newline-delimited JSON and renders
  markdown with the `marked` library.
- In production, the backend serves the built frontend from `frontend/dist/`
  with SPA fallback routing (path traversal protected).
- In development, Vite proxies `/api/*` requests to the backend on port 8000.

### License

MIT — see `LICENSE`.

## test-http-mcp

Demo Model Context Protocol (MCP) server implemented in Python using the
`http-mcp` package. It can run over HTTP (Starlette/Uvicorn, protected with
Auth0) or over stdio, exposing tools and prompts that query the NVD (National
Vulnerability Database) to any MCP-capable client.

<a href="https://glama.ai/mcp/servers/@yeison-liscano/demo_http_mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@yeison-liscano/demo_http_mcp/badge" alt="Demo HTTP Server MCP server" />
</a>

### Project structure

```
test-http-mcp/
├── backend/                 # Python MCP server
│   ├── app/                 # Application source code
│   │   ├── app.py           # Auth0-protected HTTP app (auth_mcp)
│   │   ├── main.py          # Entry points (HTTP / stdio)
│   │   ├── config.py        # Settings via pydantic-settings
│   │   ├── auth0/           # Auth0 integration
│   │   │   ├── __init__.py  # JWT token validator
│   │   │   └── client_store.py # Dynamic client registration (RFC 7591, not mounted)
│   │   ├── tools/           # MCP tools (CPE/CVE search via NVD)
│   │   └── prompts/         # MCP prompt templates
│   ├── tests/               # pytest suite, incl. end-to-end MCP client tests
│   ├── pyproject.toml       # Python deps & scripts
│   ├── uv.lock              # Locked dependencies
│   ├── ruff.toml            # Linter config
│   ├── mypy.ini             # Type-checker config
│   └── .envrc               # direnv auto-activation
├── flake.nix                # Nix dev shell
├── AGENTS.md
├── LICENSE
└── README.md
```

### Protocol

The server speaks only MCP protocol revision `2026-07-28` (http-mcp >= 0.17).
There is no `initialize` handshake, so clients must use an MCP SDK that supports
that revision, for example the Python `mcp` SDK >= 2.x or FastMCP 4.

### Authentication (Auth0, HTTP only)

The HTTP endpoint (`/mcp/`) is protected with Auth0 OAuth2 authentication.
Tools require scopes (`tool:search_cpe`, `tool:search_cve`) to be present in
the access token. stdio mode has no authentication and no tool scopes.

#### Required environment variables

| Variable | Description |
|----------|-------------|
| `AUTH0_DOMAIN` | Auth0 tenant domain (e.g. `your-tenant.auth0.com`) |
| `AUTH0_AUDIENCE` | Auth0 API identifier. **Must be the MCP resource URI** (`http://localhost:8000/mcp/`): tokens whose audience names another resource are rejected (RFC 8707) |
| `AUTH0_MCP_APP_CLIENT_ID` | Auth0 application client ID for the MCP app (used by `Auth0ClientStore`, currently not mounted) |
| `AUTH0_MGMT_CLIENT_ID` | Management API client ID (used by `Auth0ClientStore`, currently not mounted) |
| `AUTH0_MGMT_CLIENT_SECRET` | Management API client secret (used by `Auth0ClientStore`, currently not mounted) |
| `AUTH0_ENABLED` | Set to `false` to disable scope enforcement (default: `true`) |

Place these in `backend/.env` (git-ignored).

#### HTTP routes

| Path | Purpose | Auth |
|------|---------|------|
| `/mcp/` | MCP server (Streamable HTTP) | Auth0 Bearer token required |
| `/.well-known/oauth-protected-resource/mcp/` | Protected resource metadata (RFC 9728), names Auth0 as the authorization server | Unauthenticated |

Clients discover Auth0's endpoints from the tenant itself, so client
registration depends on the tenant: enable Dynamic Client Registration in
Auth0, or configure the client with a pre-registered client ID.

### Requirements

- Python 3.13
- `uv` (recommended) or `pip`
- Node.js (optional): only for `npx`-based MCP clients and servers

Alternatively, [Nix](https://nixos.org) supplies all of the above — see
[Nix dev shell](#nix-dev-shell).

### Nix dev shell

`flake.nix` pins the whole toolchain (Python 3.13, `uv`, Node.js 24, `git`),
so nothing needs to be installed system-wide:

```bash
nix develop
```

With [direnv](https://direnv.net) the shell loads automatically on `cd`, and
also syncs `backend/.venv`:

```bash
direnv allow
```

Library dependencies stay owned by `backend/uv.lock`, so pinned tool versions
(ruff, mypy, pytest) come from `uv`, not from Nix. Inside the shell `uv` is
pinned to the Nix interpreter (`UV_PYTHON`, `UV_PYTHON_DOWNLOADS=never`) so it
never downloads a second Python.

To bump the pinned nixpkgs revision:

```bash
nix flake update
```

### Install

Using `uv`:

```bash
cd backend
uv sync
```

Using `pip`:

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install .
```

### Run

HTTP (needs the Auth0 variables above):

```bash
cd backend
uv run run-app          # → MCP endpoint on http://localhost:8000/mcp/
uv run run-app-local    # same, with auto-reload
```

stdio (no Auth0 configuration needed):

```bash
cd backend
uv run run-stdio
```

### Test with an MCP client

With the Python `mcp` SDK (installed in the dev group):

```python
import asyncio

import httpx2
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    # stdio: the client launches the server as a subprocess
    stdio = StdioServerParameters(command="uv", args=["run", "--project", "backend", "run-stdio"])
    async with Client(stdio) as client:
        print(await client.list_tools())

    # HTTP: pass an Auth0 access token for this API (audience = the MCP resource URI)
    http_client = httpx2.AsyncClient(headers={"Authorization": "Bearer <access-token>"})
    async with Client(streamable_http_client("http://localhost:8000/mcp/", http_client=http_client)) as client:
        print(await client.call_tool("search_cve", {"cve_id": "CVE-2023-44487"}))


asyncio.run(main())
```

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
      "args": ["run", "--project", "backend", "run-stdio"]
    }
  }
}
```

### What this server exposes

- Tools (see `backend/app/tools/`):
  - `search_cpe(product, version, vendor)` — search Common Platform Enumerations via NVD
  - `search_cve(cve_id, cpe_name, keyword_search, cwe_id, cvss_v3_severity, has_kev, no_rejected, pub_start_date, pub_end_date)`
    — search Common Vulnerabilities and Exposures; at least one filter is required
- Prompts (see `backend/app/prompts/`):
  - `sync_nvd_search(dependency_name, dependency_version)` — simple vulnerability search prompt
  - `async_nvd_search(dependency_name, dependency_version)` — prompt with pre-fetched CVE data

### Project scripts

Three console entry points are defined in `backend/pyproject.toml`:

- `run-app` → `app.main:run_http` (HTTP on `localhost:8000`)
- `run-app-local` → `app.app:main` (HTTP with auto-reload)
- `run-stdio` → `app.main:run_stdio`

### Development

Common tasks (run from the `backend/` directory):

```bash
uv run ruff check .           # lint
uv run mypy .                 # type check
uv run pytest                 # tests
uv run mdformat .             # format markdown
```

`tests/test_mcp_client_compat.py` drives the server with the real `mcp` SDK
client over HTTP (plain and Auth0-protected) and over stdio (`run-stdio`), so it
catches protocol drift between `http-mcp` and MCP clients.

### Implementation notes

- The HTTP app is an Auth0-protected MCP app created by `auth_mcp`; the MCP
  endpoint at `/mcp/` requires a valid Auth0 Bearer token with the
  appropriate tool scopes.
- `Auth0ClientStore` (dynamic client registration proxied to a pre-created
  Auth0 application) is kept but not mounted: http-mcp >= 0.19 only accepts
  HTTPS authorization servers and endpoints, and MCP clients on SDK 2.x require
  the metadata `issuer` to match the advertised server, which a localhost proxy
  for Auth0 cannot satisfy.
- Only loopback browser origins are accepted on `/mcp/` (http-mcp's DNS
  rebinding defence); clients that send no `Origin` header are unaffected.

### License

MIT — see `LICENSE`.

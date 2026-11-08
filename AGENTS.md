# Project Instructions

## Architecture Overview

This is an MCP (Model Context Protocol) server built on `http-mcp`, served over
HTTP (with Auth0 OAuth2 authentication) or stdio. It speaks only MCP protocol
revision `2026-07-28`. It also serves as the compatibility testbed for `http-mcp`
releases.

### App structure

- **HTTP app** (`app` in `backend/app/app.py`) — Auth0-protected MCP app created
  by `auth_mcp`. Handles `/mcp/` and `/.well-known/oauth-protected-resource/mcp/`.
- **stdio server** (`run_stdio` in `backend/app/main.py`) — same tools and prompts,
  no authentication or scopes.

### Key modules

| Module                                    | Purpose                                                        |
| ----------------------------------------- | -------------------------------------------------------------- |
| `backend/app/app.py`                      | HTTP app: MCP server + Auth0 wiring                            |
| `backend/app/main.py`                     | Entry points: `run-app` (HTTP), `run-stdio`                    |
| `backend/app/auth0/__init__.py`           | Auth0 JWT token validator                                      |
| `backend/app/auth0/client_store.py`       | Dynamic client registration (RFC 7591), not mounted            |
| `backend/app/config.py`                   | pydantic-settings config (Auth0)                               |
| `backend/app/tools/`                      | MCP tools — CPE/CVE search via NVD                             |
| `backend/app/prompts/`                    | MCP prompts                                                    |
| `backend/tests/test_mcp_client_compat.py` | End-to-end tests with the real `mcp` SDK client (HTTP + stdio) |

## Development Guidelines

### Backend

- Python 3.13, managed with `uv`
- Run from `backend/`: `uv run run-app` (HTTP), `uv run run-app-local` (HTTP, reload),
  `uv run run-stdio` (stdio)
- Lint: `uv run ruff check .` — Type check: `uv run mypy .` — Test: `uv run pytest`
- Follow existing patterns: pydantic models for I/O, `Config` for env vars

### Security rules

- **Never log secrets.** Use redacted summaries (e.g. `expires_in`) not full token responses.
- **Validate file paths.** Any user-controlled path must be `.resolve()`d and
  checked with `.is_relative_to()` before serving.
- **CORS: explicit origins only.** Never use `allow_origins=["*"]` with credentials.
- **Validate redirect URIs.** Only HTTPS allowed; HTTP only for localhost.
- **Auth0 env vars go in `backend/.env`** (git-ignored). Never commit secrets.

## Execute Security Scanners

### Execute SCA Scanner When:

- New dependencies are added or updated
- Lock files are modified (`uv.lock`, `package-lock.json`)
- Before deploying to production or pushing to the repository

### Execute SAST Scanner When:

- Source code changes are made to application files
- Security-sensitive code is modified (auth, token handling, file serving)
- Before committing significant code changes

### Execute Both Scanners When:

- Complete security audit is needed
- Major project updates involving both code and dependencies
- Pre-deployment security check

## Prerequisites

- Docker installed on the system
- No Dockerfile creation needed - only download the Docker images
- Write access to the project directory for configuration files and results

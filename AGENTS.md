# Project Instructions

## Architecture Overview

This is an MCP (Model Context Protocol) server with Auth0 OAuth2 authentication,
a chat agent, and a React frontend.

### App structure

- **Root app** (`app` in `backend/app/app.py`) — Auth0-protected MCP app created
  by `auth_mcp`. Handles `/mcp/`, `/register`, `/.well-known/` endpoints.
- **FastAPI sub-app** (`fast_app`, mounted at `/api`) — chat endpoints, frontend
  serving. Chat endpoints are intentionally unauthenticated for local dev.
- **Frontend** (`frontend/`) — React + TypeScript + Vite SPA.

### Key modules

| Module | Purpose |
|--------|---------|
| `backend/app/app.py` | App setup, routes, MCP + Auth0 wiring |
| `backend/app/auth0/__init__.py` | Auth0 JWT token validator |
| `backend/app/auth0/client_store.py` | Dynamic client registration (RFC 7591) |
| `backend/app/config.py` | pydantic-settings config (Auth0, Logfire) |
| `backend/app/tools/` | MCP tools — CPE/CVE search via NVD |
| `backend/app/agent.py` | pydantic-ai agent streaming logic |
| `backend/app/agen_memory.py` | SQLite message persistence |
| `frontend/src/api.ts` | API client (fetch history, stream messages) |

## Development Guidelines

### Backend

- Python 3.13, managed with `uv`
- Run from `backend/`: `uv run run-app` (production) or `uv run run-app-local` (reload)
- Lint: `uv run ruff check .` — Type check: `uv run mypy .` — Test: `uv run pytest`
- Follow existing patterns: pydantic models for I/O, `Config` for env vars

### Frontend

- React + TypeScript + Vite
- Run from `frontend/`: `npm run dev` (proxies `/api/*` to backend on 8000)
- Lint: `npm run lint` — Type check: `npx tsc --noEmit`

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

## Fluid Attacks Scanner

### Purpose

Scan the project for vulnerabilities using the Fluid Attacks MCP tools.

### Step-by-Step Instructions

#### 1. Use Fluid Attack MCP tools to configure and run the scanner

#### 2. Add the output file to .gitignore

#### 3. Remediate vulnerabilities

- Review the output file
- If there are vulnerabilities, remediate them

## Best Practices for Agents

### Configuration File Management

- Always verify the correct paths for include/exclude before running
- Adjust configuration based on project structure
- Use `.gitignore` as a reference for exclude patterns
- Store configuration files in the project root and add them to .gitignore
- Add the output file (Fluid-Attacks-Results.csv) to .gitignore

## When to Run What

| Scenario                      | Scanner | Priority |
| ----------------------------- | ------- | -------- |
| New dependency added          | SCA     | High     |
| Code changes in auth/security | SAST    | Critical |
| Weekly security audit         | Both    | Medium   |
| Pre-deployment check          | Both    | Critical |
| Dependency version update     | SCA     | High     |
| New feature development       | SAST    | Medium   |
| Third-party library added     | SCA     | High     |
| API endpoint changes          | SAST    | High     |

## Integration with Development Workflow

- On Code Changes: Run SAST if source files modified
- On Dependency Changes: Run SCA if dependency files modified
- On User Request: Run appropriate scanner(s)
- Help with remediation: Always create/update security reports
- Re-scan: After fixes to verify remediation

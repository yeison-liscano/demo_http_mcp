from http_mcp.types import Tool, ToolAnnotations

from app.tools.web import WebFetchInput, WebSearchInput, WebToolOutput, web_fetch, web_search

# Read-only, but they reach the open web and a model, so results vary between calls.
_WEB = ToolAnnotations(read_only_hint=True, idempotent_hint=False, open_world_hint=True)


def create_tools(*, auth_enabled: bool = False) -> tuple[Tool, ...]:
    """Create tool definitions, optionally with Auth0 scope enforcement."""
    search_scopes = ("tool:web_search",) if auth_enabled else ()
    fetch_scopes = ("tool:web_fetch",) if auth_enabled else ()
    return (
        Tool(
            inputs=WebSearchInput,
            output=WebToolOutput,
            func=web_search,
            scopes=search_scopes,
            annotations=_WEB,
        ),
        Tool(
            inputs=WebFetchInput,
            output=WebToolOutput,
            func=web_fetch,
            scopes=fetch_scopes,
            annotations=_WEB,
        ),
    )


# Default without scopes, for stdio and the unauthenticated tests.
TOOLS = create_tools(auth_enabled=False)

__all__ = ["TOOLS", "create_tools"]

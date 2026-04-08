from http_mcp.types import Tool

from app.tools.models import (
    SearchCPEInput,
    SearchCPEOutput,
    SearchCVEInput,
    SearchCVEOutput,
)
from app.tools.nvd_dal import search_cpe, search_cve


def create_tools(*, auth_enabled: bool = False) -> tuple[Tool, ...]:
    """Create tool definitions, optionally with Auth0 scope enforcement."""
    cpe_scopes = ("tool:search_cpe",) if auth_enabled else ()
    cve_scopes = ("tool:search_cve",) if auth_enabled else ()
    return (
        Tool(
            inputs=SearchCPEInput,
            output=SearchCPEOutput,
            func=search_cpe,
            scopes=cpe_scopes,
        ),
        Tool(
            inputs=SearchCVEInput,
            output=SearchCVEOutput,
            func=search_cve,
            scopes=cve_scopes,
        ),
    )


# Backward-compatible default (no auth)
TOOLS = create_tools(auth_enabled=False)

__all__ = ["TOOLS", "create_tools"]

from http_mcp.types import Tool

from app.tools.models import (
    SearchCPEInput,
    SearchCPEOutput,
    SearchCVEInput,
    SearchCVEOutput,
)
from app.tools.nvd_dal import search_cpe, search_cve

TOOLS = (
    Tool(
        inputs=SearchCPEInput,
        output=SearchCPEOutput,
        func=search_cpe,
    ),
    Tool(
        inputs=SearchCVEInput,
        output=SearchCVEOutput,
        func=search_cve,
    ),
)

__all__ = ["TOOLS"]

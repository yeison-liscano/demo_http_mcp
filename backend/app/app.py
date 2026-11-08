"""Auth0-protected MCP server over Streamable HTTP."""

from pathlib import Path

import uvicorn
from auth_mcp.resource_server import ProtectedMCPAppConfig, create_protected_mcp_app
from auth_mcp.types import ProtectedResourceMetadata
from http_mcp.server import MCPServer
from pydantic import AnyHttpUrl

from app.auth0 import Auth0TokenValidator
from app.config import Config
from app.prompts import PROMPTS
from app.tools import create_tools

THIS_DIR = Path(__file__).parent
TOOL_SCOPES = ("tool:search_cpe", "tool:search_cve")

config = Config()
mcp_server = MCPServer(
    tools=create_tools(auth_enabled=config.auth0_enabled),
    prompts=PROMPTS,
    name="test",
    version="1.0.0",
)

# http-mcp >= 0.19 only accepts HTTPS issuers in `authorization_servers` and HTTPS
# endpoints in authorization server metadata, and MCP clients on SDK 2.x require the
# metadata `issuer` to equal the advertised server (RFC 8414 section 3.3). Auth0 is
# therefore advertised directly; client registration is up to the Auth0 tenant.
app = create_protected_mcp_app(
    ProtectedMCPAppConfig(
        mcp_server=mcp_server,
        token_validator=Auth0TokenValidator(
            domain=config.auth0_domain,
            audience=config.auth0_audience,
        ),
        resource_endpoint=ProtectedResourceMetadata(
            resource=AnyHttpUrl("http://localhost:8000/mcp/"),
            authorization_servers=(f"https://{config.auth0_domain}/",),
            scopes_supported=TOOL_SCOPES,
        ),
        mcp_path="/mcp",
        require_authentication=True,
    ),
)


def main() -> None:
    """Serve the HTTP app with auto-reload (development)."""
    uvicorn.run(
        "app.app:app",
        host="localhost",
        port=8000,
        reload=True,
        reload_dirs=[str(THIS_DIR)],
    )

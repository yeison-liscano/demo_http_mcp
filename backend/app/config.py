from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, whatever directory the server is started from: an MCP client
# launching run-stdio decides the working directory, not us.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_enabled: bool = True
    auth0_mcp_app_client_id: str = ""
    auth0_mgmt_client_id: str = ""
    auth0_mgmt_client_secret: str = ""

    # Claude sub-agents behind the web tools. Without an API key, the Anthropic SDK resolves
    # credentials itself (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, an `ant auth login` profile).
    anthropic_api_key: SecretStr | None = None
    agent_model: str = "claude-opus-5-5"
    agent_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"

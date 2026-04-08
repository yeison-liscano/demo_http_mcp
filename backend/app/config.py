from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    logfire_api_key: str = ""
    logfire_project_id: str = ""
    logfire_api_url: str = ""

    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_enabled: bool = True
    auth0_mcp_app_client_id: str = ""
    auth0_mgmt_client_id: str = ""
    auth0_mgmt_client_secret: str = ""

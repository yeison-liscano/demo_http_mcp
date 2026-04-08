"""Auth0 token validator for auth_mcp integration."""

from __future__ import annotations

import logging

from auth0_api_python import ApiClient, ApiClientOptions
from auth_mcp.resource_server import TokenInfo, TokenValidator

LOGGER = logging.getLogger(__name__)


class Auth0TokenValidator(TokenValidator):
    """Validates Auth0-issued JWTs using the auth0-api-python SDK."""

    def __init__(self, domain: str, audience: str) -> None:
        if not domain or not audience:
            msg = "Auth0 domain and audience must be non-empty"
            LOGGER.debug(msg)
            raise ValueError(msg)
        self._api_client = ApiClient(ApiClientOptions(domain=domain, audience=audience))

    async def validate_token(
        self,
        token: str,
        resource: str | None = None,  # noqa: ARG002
    ) -> TokenInfo | None:
        """Validate a Bearer token via Auth0 and return TokenInfo or None."""
        try:
            decoded = await self._api_client.verify_access_token(access_token=token)
        except Exception:
            LOGGER.debug("Auth0 token verification failed")
            LOGGER.exception("Token verification error")
            return None

        scope_str = decoded.get("scope", "")
        LOGGER.debug("Token valid for subject '%s' with scopes: %s", decoded.get("sub"), scope_str)
        return TokenInfo(
            subject=decoded.get("sub", decoded.get("client_id", "")),
            scopes=tuple(scope_str.split()) if scope_str else (),
            expires_at=decoded.get("exp"),
            client_id=decoded.get("client_id"),
            audience=decoded.get("aud"),
        )


__all__ = ["Auth0TokenValidator"]

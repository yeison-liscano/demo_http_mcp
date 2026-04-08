"""Auth0-backed client store for RFC 7591 Dynamic Client Registration."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import httpx
from auth_mcp.authorization_server.client_store import ClientStore
from auth_mcp.types.registration import ClientRegistrationRequest, ClientRegistrationResponse

LOGGER = logging.getLogger(__name__)

_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def _is_valid_redirect_uri(uri: str) -> bool:
    """Allow HTTPS redirect URIs, or HTTP only for localhost."""
    parsed = urlparse(uri)
    if not parsed.hostname:
        return False
    if parsed.hostname in _LOCALHOST_HOSTS:
        return parsed.scheme in {"http", "https"}
    return parsed.scheme == "https"


class Auth0ClientStore(ClientStore):
    """Proxies dynamic client registration to a pre-created Auth0 application.

    On each registration request, updates the Auth0 app's allowed callback
    URLs to include the client's redirect_uris, then returns the app's
    client_id so the OAuth flow can proceed against Auth0.
    """

    def __init__(
        self,
        domain: str,
        mcp_app_client_id: str,
        mgmt_client_id: str,
        mgmt_client_secret: str,
    ) -> None:
        self._domain = domain
        self._mcp_app_client_id = mcp_app_client_id
        self._mgmt_client_id = mgmt_client_id
        self._mgmt_client_secret = mgmt_client_secret
        self._mgmt_token: str | None = None
        self._mgmt_token_expires_at: float = 0

    async def _get_mgmt_token(self) -> str:
        """Get a Management API access token, refreshing if expired."""
        if self._mgmt_token and time.time() < self._mgmt_token_expires_at:
            return self._mgmt_token

        async with httpx.AsyncClient() as client:
            LOGGER.debug("Fetching Management API token...")
            resp = await client.post(
                f"https://{self._domain}/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": self._mgmt_client_id,
                    "client_secret": self._mgmt_client_secret,
                    "audience": f"https://{self._domain}/api/v2/",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            LOGGER.debug("Management API token acquired, expires_in=%s", data.get("expires_in"))

        self._mgmt_token = data["access_token"]
        self._mgmt_token_expires_at = time.time() + data.get("expires_in", 3600) - 60
        return self._mgmt_token

    async def _update_callback_urls(self, redirect_uris: tuple[str, ...]) -> None:
        """Add redirect_uris to the Auth0 app's allowed callback URLs."""
        valid_uris = [uri for uri in redirect_uris if _is_valid_redirect_uri(uri)]
        rejected = set(redirect_uris) - set(valid_uris)
        if rejected:
            LOGGER.warning("Rejected invalid redirect URIs: %s", rejected)
        if not valid_uris:
            LOGGER.warning("No valid redirect URIs to register")
            return

        token = await self._get_mgmt_token()
        headers = {"Authorization": f"Bearer {token}"}
        base = f"https://{self._domain}/api/v2/clients/{self._mcp_app_client_id}"

        async with httpx.AsyncClient() as client:
            LOGGER.debug("Fetching Auth0 app details...")
            resp = await client.get(base, headers=headers)
            resp.raise_for_status()
            existing_callbacks: set[str] = set(resp.json().get("callbacks") or [])

            new_callbacks = existing_callbacks | set(valid_uris)
            LOGGER.debug("Existing: %s, new: %s", existing_callbacks, new_callbacks)
            if new_callbacks != existing_callbacks:
                resp = await client.patch(
                    base,
                    headers=headers,
                    json={"callbacks": sorted(new_callbacks)},
                )
                resp.raise_for_status()
                LOGGER.info("Updated Auth0 app callback URLs: %s", sorted(new_callbacks))

    async def register_client(
        self,
        request: ClientRegistrationRequest,
    ) -> ClientRegistrationResponse:
        """Register a client by updating Auth0 callbacks and returning the app's client_id."""
        LOGGER.debug("client registration request: redirect_uris=%s", request.redirect_uris)
        await self._update_callback_urls(request.redirect_uris)

        return ClientRegistrationResponse(
            client_id=self._mcp_app_client_id,
            client_id_issued_at=int(time.time()),
            redirect_uris=request.redirect_uris,
            grant_types=request.grant_types,
            response_types=request.response_types,
            token_endpoint_auth_method=request.token_endpoint_auth_method,
        )

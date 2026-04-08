"""Tests for the Auth0TokenValidator adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from auth_mcp.resource_server import TokenInfo

from app.auth0 import Auth0TokenValidator


class TestAuth0TokenValidatorInit:
    def test_requires_domain_and_audience(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Auth0TokenValidator(domain="", audience="test")
        with pytest.raises(ValueError, match="non-empty"):
            Auth0TokenValidator(domain="test", audience="")


class TestAuth0TokenValidatorValidate:
    @pytest.mark.anyio
    async def test_valid_token_returns_token_info(self) -> None:
        mock_client = AsyncMock()
        mock_client.verify_access_token.return_value = {
            "sub": "user|123",
            "scope": "tool:search_cpe tool:search_cve",
            "client_id": "abc",
            "exp": 9999999999,
            "aud": "https://api.test/",
        }
        with patch("app.auth0.ApiClient", return_value=mock_client):
            validator = Auth0TokenValidator(domain="test.auth0.com", audience="https://api.test/")
            result = await validator.validate_token("valid-token")

        assert isinstance(result, TokenInfo)
        assert result.subject == "user|123"
        assert "tool:search_cpe" in result.scopes
        assert "tool:search_cve" in result.scopes
        assert result.client_id == "abc"
        assert result.expires_at == 9999999999

    @pytest.mark.anyio
    async def test_invalid_token_returns_none(self) -> None:
        mock_client = AsyncMock()
        mock_client.verify_access_token.side_effect = Exception("bad token")
        with patch("app.auth0.ApiClient", return_value=mock_client):
            validator = Auth0TokenValidator(domain="test.auth0.com", audience="https://api.test/")
            result = await validator.validate_token("bad-token")

        assert result is None

    @pytest.mark.anyio
    async def test_token_without_sub_uses_client_id(self) -> None:
        mock_client = AsyncMock()
        mock_client.verify_access_token.return_value = {
            "client_id": "m2m-client",
            "scope": "tool:search_cpe",
        }
        with patch("app.auth0.ApiClient", return_value=mock_client):
            validator = Auth0TokenValidator(domain="test.auth0.com", audience="https://api.test/")
            result = await validator.validate_token("m2m-token")

        assert result is not None
        assert result.subject == "m2m-client"

    @pytest.mark.anyio
    async def test_token_without_scope_returns_empty_scopes(self) -> None:
        mock_client = AsyncMock()
        mock_client.verify_access_token.return_value = {"sub": "user|456"}
        with patch("app.auth0.ApiClient", return_value=mock_client):
            validator = Auth0TokenValidator(domain="test.auth0.com", audience="https://api.test/")
            result = await validator.validate_token("no-scope-token")

        assert result is not None
        assert result.scopes == ()

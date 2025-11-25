"""Tests for authentication handlers."""

import pytest
import httpx
import base64

from rest_client.auth import (
    APIKeyAuth,
    BearerTokenAuth,
    BasicAuth,
    CustomAuth,
    create_auth,
)


class TestAPIKeyAuth:
    """Test suite for API Key authentication."""

    def test_api_key_in_header(self):
        """Test API key authentication in header."""
        auth = APIKeyAuth(api_key="test-key", location="header", key_name="X-API-Key")
        request = httpx.Request("GET", "https://api.example.com/test")

        authenticated_request = auth.apply(request)

        assert "X-API-Key" in authenticated_request.headers
        assert authenticated_request.headers["X-API-Key"] == "test-key"

    def test_api_key_in_query(self):
        """Test API key authentication in query parameter."""
        auth = APIKeyAuth(api_key="test-key", location="query", key_name="api_key")
        request = httpx.Request("GET", "https://api.example.com/test")

        authenticated_request = auth.apply(request)

        assert "api_key=test-key" in str(authenticated_request.url)

    def test_api_key_invalid_location(self):
        """Test that invalid location raises ValueError."""
        with pytest.raises(ValueError):
            APIKeyAuth(api_key="test-key", location="invalid")


class TestBearerTokenAuth:
    """Test suite for Bearer token authentication."""

    def test_bearer_token_auth(self):
        """Test bearer token authentication."""
        auth = BearerTokenAuth(token="test-token")
        request = httpx.Request("GET", "https://api.example.com/test")

        authenticated_request = auth.apply(request)

        assert "Authorization" in authenticated_request.headers
        assert authenticated_request.headers["Authorization"] == "Bearer test-token"


class TestBasicAuth:
    """Test suite for Basic authentication."""

    def test_basic_auth(self):
        """Test basic authentication."""
        auth = BasicAuth(username="user", password="pass")
        request = httpx.Request("GET", "https://api.example.com/test")

        authenticated_request = auth.apply(request)

        assert "Authorization" in authenticated_request.headers

        # Decode and verify
        auth_header = authenticated_request.headers["Authorization"]
        assert auth_header.startswith("Basic ")

        encoded = auth_header.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "user:pass"


class TestCustomAuth:
    """Test suite for Custom authentication."""

    def test_custom_auth(self):
        """Test custom authentication handler."""
        def custom_auth_func(request):
            request.headers["X-Custom-Auth"] = "custom-value"
            return request

        auth = CustomAuth(auth_func=custom_auth_func)
        request = httpx.Request("GET", "https://api.example.com/test")

        authenticated_request = auth.apply(request)

        assert "X-Custom-Auth" in authenticated_request.headers
        assert authenticated_request.headers["X-Custom-Auth"] == "custom-value"


class TestCreateAuth:
    """Test suite for create_auth factory function."""

    def test_create_auth_with_api_key(self):
        """Test creating auth with API key."""
        auth = create_auth(api_key="test-key")
        assert isinstance(auth, APIKeyAuth)

    def test_create_auth_with_bearer_token(self):
        """Test creating auth with bearer token."""
        auth = create_auth(bearer_token="test-token")
        assert isinstance(auth, BearerTokenAuth)

    def test_create_auth_with_basic(self):
        """Test creating auth with username and password."""
        auth = create_auth(username="user", password="pass")
        assert isinstance(auth, BasicAuth)

    def test_create_auth_with_username_only(self):
        """Test that providing only username raises ValueError."""
        with pytest.raises(ValueError):
            create_auth(username="user")

    def test_create_auth_with_password_only(self):
        """Test that providing only password raises ValueError."""
        with pytest.raises(ValueError):
            create_auth(password="pass")

    def test_create_auth_with_none(self):
        """Test that no auth returns None."""
        auth = create_auth()
        assert auth is None

    def test_create_auth_priority(self):
        """Test that bearer token takes priority over API key."""
        auth = create_auth(api_key="key", bearer_token="token")
        assert isinstance(auth, BearerTokenAuth)

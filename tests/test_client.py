"""Tests for the synchronous REST client."""

import pytest
import httpx
import respx

from rest_client import Client, HTTPError, AuthenticationError, RateLimitError
from rest_client.retry import RetryConfig


class TestClient:
    """Test suite for the synchronous Client."""

    def test_client_initialization(self):
        """Test basic client initialization."""
        client = Client(base_url="https://api.example.com")
        assert client.config.base_url == "https://api.example.com"
        assert client.config.verify_ssl is True

    def test_client_initialization_with_trailing_slash(self):
        """Test that trailing slashes are removed from base_url."""
        client = Client(base_url="https://api.example.com/")
        assert client.config.base_url == "https://api.example.com"

    def test_client_with_api_key_auth(self):
        """Test client initialization with API key authentication."""
        client = Client(
            base_url="https://api.example.com",
            api_key="test-key"
        )
        assert client.auth is not None

    def test_client_with_bearer_token_auth(self):
        """Test client initialization with bearer token authentication."""
        client = Client(
            base_url="https://api.example.com",
            bearer_token="test-token"
        )
        assert client.auth is not None

    def test_client_with_basic_auth(self):
        """Test client initialization with basic authentication."""
        client = Client(
            base_url="https://api.example.com",
            username="user",
            password="pass"
        )
        assert client.auth is not None

    def test_client_context_manager(self):
        """Test client as context manager."""
        with Client(base_url="https://api.example.com") as client:
            assert client._client is None  # Not created until first use

    @respx.mock
    def test_get_request(self):
        """Test GET request."""
        route = respx.get("https://api.example.com/users/123").mock(
            return_value=httpx.Response(200, json={"id": 123, "name": "Test"})
        )

        client = Client(base_url="https://api.example.com")
        response = client.get("/users/123")

        assert response.status_code == 200
        assert response.json() == {"id": 123, "name": "Test"}
        assert route.called

    @respx.mock
    def test_post_request(self):
        """Test POST request."""
        route = respx.post("https://api.example.com/users").mock(
            return_value=httpx.Response(201, json={"id": 456, "name": "New User"})
        )

        client = Client(base_url="https://api.example.com")
        response = client.post("/users", json={"name": "New User"})

        assert response.status_code == 201
        assert route.called

    @respx.mock
    def test_http_error_raises_exception(self):
        """Test that HTTP errors raise appropriate exceptions."""
        respx.get("https://api.example.com/users/999").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        client = Client(base_url="https://api.example.com")

        with pytest.raises(HTTPError) as exc_info:
            client.get("/users/999")

        assert exc_info.value.status_code == 404

    @respx.mock
    def test_authentication_error(self):
        """Test that 401 raises AuthenticationError."""
        respx.get("https://api.example.com/protected").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )

        client = Client(base_url="https://api.example.com")

        with pytest.raises(AuthenticationError):
            client.get("/protected")

    @respx.mock
    def test_rate_limit_error(self):
        """Test that 429 raises RateLimitError."""
        respx.get("https://api.example.com/api/endpoint").mock(
            return_value=httpx.Response(
                429,
                headers={"Retry-After": "60"},
                text="Too Many Requests"
            )
        )

        client = Client(base_url="https://api.example.com")

        with pytest.raises(RateLimitError) as exc_info:
            client.get("/api/endpoint")

        assert exc_info.value.retry_after == 60

    @respx.mock
    def test_raise_for_status_disabled(self):
        """Test that errors don't raise when raise_for_status_enabled=False."""
        respx.get("https://api.example.com/users/999").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        client = Client(
            base_url="https://api.example.com",
            raise_for_status_enabled=False
        )
        response = client.get("/users/999")

        assert response.status_code == 404  # No exception raised

    def test_request_methods_exist(self):
        """Test that all HTTP methods are available."""
        client = Client(base_url="https://api.example.com")
        assert hasattr(client, 'get')
        assert hasattr(client, 'post')
        assert hasattr(client, 'put')
        assert hasattr(client, 'patch')
        assert hasattr(client, 'delete')
        assert hasattr(client, 'head')
        assert hasattr(client, 'options')

    @respx.mock
    def test_custom_headers(self):
        """Test that custom headers are included in requests."""
        route = respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200)
        )

        client = Client(
            base_url="https://api.example.com",
            headers={"X-Custom": "value"}
        )
        client.get("/test")

        # Verify the request was called with headers
        assert route.called
        request = route.calls.last.request
        assert "X-Custom" in request.headers
        assert request.headers["X-Custom"] == "value"

    @respx.mock
    def test_query_parameters(self):
        """Test that query parameters are properly encoded."""
        route = respx.get("https://api.example.com/search").mock(
            return_value=httpx.Response(200)
        )

        client = Client(base_url="https://api.example.com")
        client.get("/search", params={"q": "test query", "limit": 10})

        # Verify the request was called with params
        assert route.called
        request = route.calls.last.request
        assert "q=test+query" in str(request.url) or "q=test%20query" in str(request.url)
        assert "limit=10" in str(request.url)

    @respx.mock
    def test_retry_on_500_error(self):
        """Test that 500 errors trigger retry logic."""
        # First two calls fail, third succeeds
        route = respx.get("https://api.example.com/flaky-endpoint").mock(
            side_effect=[
                httpx.Response(500, text="Internal Server Error"),
                httpx.Response(500, text="Internal Server Error"),
                httpx.Response(200),
            ]
        )

        retry_config = RetryConfig(max_retries=3, backoff_factor=0.01)
        client = Client(
            base_url="https://api.example.com",
            retry=retry_config
        )
        response = client.get("/flaky-endpoint")

        assert response.status_code == 200
        assert route.call_count == 3  # 1 initial + 2 retries

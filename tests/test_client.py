"""Tests for the synchronous REST client."""

import pytest
import httpx
from unittest.mock import Mock, patch, MagicMock

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

    @patch('httpx.Client.send')
    def test_get_request(self, mock_send):
        """Test GET request."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"id": 123, "name": "Test"}
        mock_send.return_value = mock_response

        client = Client(base_url="https://api.example.com")
        response = client.get("/users/123")

        assert response.status_code == 200
        assert response.json() == {"id": 123, "name": "Test"}
        mock_send.assert_called_once()

    @patch('httpx.Client.send')
    def test_post_request(self, mock_send):
        """Test POST request."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.is_success = True
        mock_response.json.return_value = {"id": 456, "name": "New User"}
        mock_send.return_value = mock_response

        client = Client(base_url="https://api.example.com")
        response = client.post("/users", json={"name": "New User"})

        assert response.status_code == 201
        mock_send.assert_called_once()

    @patch('httpx.Client.send')
    def test_http_error_raises_exception(self, mock_send):
        """Test that HTTP errors raise appropriate exceptions."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.is_success = False
        mock_response.reason_phrase = "Not Found"
        mock_send.return_value = mock_response

        client = Client(base_url="https://api.example.com")

        with pytest.raises(HTTPError) as exc_info:
            client.get("/users/999")

        assert exc_info.value.status_code == 404

    @patch('httpx.Client.send')
    def test_authentication_error(self, mock_send):
        """Test that 401 raises AuthenticationError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.is_success = False
        mock_response.reason_phrase = "Unauthorized"
        mock_response.json.side_effect = Exception()  # Simulate no JSON body
        mock_send.return_value = mock_response

        client = Client(base_url="https://api.example.com")

        with pytest.raises(AuthenticationError):
            client.get("/protected")

    @patch('httpx.Client.send')
    def test_rate_limit_error(self, mock_send):
        """Test that 429 raises RateLimitError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.is_success = False
        mock_response.reason_phrase = "Too Many Requests"
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.side_effect = Exception()  # Simulate no JSON body
        mock_send.return_value = mock_response

        client = Client(base_url="https://api.example.com")

        with pytest.raises(RateLimitError) as exc_info:
            client.get("/api/endpoint")

        assert exc_info.value.retry_after == 60

    @patch('httpx.Client.send')
    def test_raise_for_status_disabled(self, mock_send):
        """Test that errors don't raise when raise_for_status_enabled=False."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.is_success = False
        mock_send.return_value = mock_response

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

    @patch('httpx.Client.send')
    def test_custom_headers(self, mock_send):
        """Test that custom headers are included in requests."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_send.return_value = mock_response

        client = Client(
            base_url="https://api.example.com",
            headers={"X-Custom": "value"}
        )
        client.get("/test")

        # Verify the request was called with headers
        called_request = mock_send.call_args[0][0]
        assert "X-Custom" in called_request.headers

    @patch('httpx.Client.send')
    def test_query_parameters(self, mock_send):
        """Test that query parameters are properly encoded."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_send.return_value = mock_response

        client = Client(base_url="https://api.example.com")
        client.get("/search", params={"q": "test query", "limit": 10})

        # Verify the request was called with params
        called_request = mock_send.call_args[0][0]
        assert "q=test+query" in str(called_request.url) or "q=test%20query" in str(called_request.url)

    @patch('httpx.Client.send')
    def test_retry_on_500_error(self, mock_send):
        """Test that 500 errors trigger retry logic."""
        # First two calls fail, third succeeds
        mock_response_fail = Mock(spec=httpx.Response)
        mock_response_fail.status_code = 500
        mock_response_fail.is_success = False
        mock_response_fail.reason_phrase = "Internal Server Error"
        mock_response_fail.json.side_effect = Exception()

        mock_response_success = Mock(spec=httpx.Response)
        mock_response_success.status_code = 200
        mock_response_success.is_success = True

        mock_send.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success
        ]

        retry_config = RetryConfig(max_retries=3, backoff_factor=0.01)
        client = Client(
            base_url="https://api.example.com",
            retry=retry_config
        )
        response = client.get("/flaky-endpoint")

        assert response.status_code == 200
        assert mock_send.call_count == 3  # 1 initial + 2 retries

"""Tests for the asynchronous REST client."""

import pytest
import httpx
from unittest.mock import Mock, AsyncMock, patch

from rest_client import AsyncClient, HTTPError, AuthenticationError


class TestAsyncClient:
    """Test suite for the asynchronous AsyncClient."""

    def test_async_client_initialization(self):
        """Test basic async client initialization."""
        client = AsyncClient(base_url="https://api.example.com")
        assert client.config.base_url == "https://api.example.com"
        assert client.config.verify_ssl is True

    def test_async_client_with_api_key(self):
        """Test async client with API key authentication."""
        client = AsyncClient(
            base_url="https://api.example.com",
            api_key="test-key"
        )
        assert client.auth is not None

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async client as context manager."""
        async with AsyncClient(base_url="https://api.example.com") as client:
            assert client._client is None  # Not created until first use

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.send')
    async def test_async_get_request(self, mock_send):
        """Test async GET request."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"id": 123, "name": "Test"}
        mock_send.return_value = mock_response

        client = AsyncClient(base_url="https://api.example.com")
        response = await client.get("/users/123")

        assert response.status_code == 200
        assert response.json() == {"id": 123, "name": "Test"}
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.send')
    async def test_async_post_request(self, mock_send):
        """Test async POST request."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.is_success = True
        mock_response.json.return_value = {"id": 456, "name": "New User"}
        mock_send.return_value = mock_response

        client = AsyncClient(base_url="https://api.example.com")
        response = await client.post("/users", json={"name": "New User"})

        assert response.status_code == 201
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.send')
    async def test_async_http_error(self, mock_send):
        """Test that HTTP errors raise exceptions in async client."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.is_success = False
        mock_response.reason_phrase = "Not Found"
        mock_send.return_value = mock_response

        client = AsyncClient(base_url="https://api.example.com")

        with pytest.raises(HTTPError):
            await client.get("/users/999")

    @pytest.mark.asyncio
    async def test_async_request_methods_exist(self):
        """Test that all async HTTP methods are available."""
        client = AsyncClient(base_url="https://api.example.com")
        assert hasattr(client, 'get')
        assert hasattr(client, 'post')
        assert hasattr(client, 'put')
        assert hasattr(client, 'patch')
        assert hasattr(client, 'delete')
        assert hasattr(client, 'head')
        assert hasattr(client, 'options')

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.send')
    async def test_async_close(self, mock_send):
        """Test that async client properly closes."""
        client = AsyncClient(base_url="https://api.example.com")

        # Force client creation
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_send.return_value = mock_response

        await client.get("/test")
        assert client._client is not None

        await client.close()
        # After close, _client should be None
        assert client._client is None

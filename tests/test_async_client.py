"""Tests for the asynchronous REST client."""

import pytest
import httpx
import respx

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
    @respx.mock
    async def test_async_get_request(self):
        """Test async GET request."""
        route = respx.get("https://api.example.com/users/123").mock(
            return_value=httpx.Response(200, json={"id": 123, "name": "Test"})
        )

        client = AsyncClient(base_url="https://api.example.com")
        response = await client.get("/users/123")

        assert response.status_code == 200
        assert response.json() == {"id": 123, "name": "Test"}
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_post_request(self):
        """Test async POST request."""
        route = respx.post("https://api.example.com/users").mock(
            return_value=httpx.Response(201, json={"id": 456, "name": "New User"})
        )

        client = AsyncClient(base_url="https://api.example.com")
        response = await client.post("/users", json={"name": "New User"})

        assert response.status_code == 201
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_http_error(self):
        """Test that HTTP errors raise exceptions in async client."""
        respx.get("https://api.example.com/users/999").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

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
    @respx.mock
    async def test_async_close(self):
        """Test that async client properly closes."""
        route = respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200)
        )

        client = AsyncClient(base_url="https://api.example.com")

        # Force client creation
        await client.get("/test")
        assert client._client is not None

        await client.close()
        # After close, _client should be None
        assert client._client is None

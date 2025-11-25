"""
Authentication handlers for the REST client library.

This module provides various authentication methods that can be used
with the REST client.
"""

from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import httpx
import base64


class Auth(ABC):
    """Base class for authentication handlers."""

    @abstractmethod
    def apply(self, request: httpx.Request) -> httpx.Request:
        """
        Apply authentication to a request.

        Args:
            request: The HTTP request to authenticate

        Returns:
            The authenticated request
        """
        pass


class APIKeyAuth(Auth):
    """API Key authentication (header-based or query parameter)."""

    def __init__(
        self,
        api_key: str,
        location: str = "header",
        key_name: str = "X-API-Key",
    ):
        """
        Initialize API Key authentication.

        Args:
            api_key: The API key value
            location: Where to place the key ("header" or "query")
            key_name: The name of the header or query parameter
        """
        self.api_key = api_key
        self.location = location.lower()
        self.key_name = key_name

        if self.location not in ("header", "query"):
            raise ValueError("location must be 'header' or 'query'")

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Apply API key authentication to the request."""
        if self.location == "header":
            request.headers[self.key_name] = self.api_key
        else:  # query
            # Add query parameter
            url = request.url
            params = dict(url.params)
            params[self.key_name] = self.api_key
            request.url = url.copy_with(params=params)
        return request


class BearerTokenAuth(Auth):
    """Bearer token authentication (OAuth2, JWT)."""

    def __init__(self, token: str):
        """
        Initialize Bearer token authentication.

        Args:
            token: The bearer token
        """
        self.token = token

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Apply bearer token authentication to the request."""
        request.headers["Authorization"] = f"Bearer {self.token}"
        return request


class BasicAuth(Auth):
    """Basic authentication (username/password)."""

    def __init__(self, username: str, password: str):
        """
        Initialize Basic authentication.

        Args:
            username: The username
            password: The password
        """
        self.username = username
        self.password = password

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Apply basic authentication to the request."""
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        request.headers["Authorization"] = f"Basic {encoded}"
        return request


class CustomAuth(Auth):
    """Custom authentication handler."""

    def __init__(self, auth_func):
        """
        Initialize custom authentication.

        Args:
            auth_func: A callable that takes a request and returns an authenticated request
        """
        self.auth_func = auth_func

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Apply custom authentication to the request."""
        return self.auth_func(request)


def create_auth(
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    auth: Optional[Auth] = None,
    **kwargs,
) -> Optional[Auth]:
    """
    Create an authentication handler from various inputs.

    Args:
        api_key: API key for APIKeyAuth
        bearer_token: Token for BearerTokenAuth
        username: Username for BasicAuth (requires password)
        password: Password for BasicAuth (requires username)
        auth: Custom Auth instance
        **kwargs: Additional arguments for specific auth types

    Returns:
        An Auth instance or None if no authentication is configured

    Raises:
        ValueError: If invalid authentication configuration is provided
    """
    if auth is not None:
        return auth

    if bearer_token:
        return BearerTokenAuth(bearer_token)

    if api_key:
        location = kwargs.get("api_key_location", "header")
        key_name = kwargs.get("api_key_name", "X-API-Key")
        return APIKeyAuth(api_key, location, key_name)

    if username and password:
        return BasicAuth(username, password)

    if username or password:
        raise ValueError("Both username and password must be provided for BasicAuth")

    return None

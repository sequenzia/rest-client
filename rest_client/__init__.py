"""
Python REST Client - A comprehensive REST API client library.

This library provides both synchronous and asynchronous HTTP clients
with built-in support for authentication, retry logic, streaming, and more.

Example (synchronous):
    >>> from rest_client import Client
    >>> client = Client(base_url="https://api.example.com", api_key="your-key")
    >>> response = client.get("/users/123")
    >>> user = response.json()

Example (asynchronous):
    >>> from rest_client import AsyncClient
    >>> async with AsyncClient(base_url="https://api.example.com") as client:
    ...     response = await client.get("/users/123")
    ...     user = response.json()
"""

from .client import Client
from .async_client import AsyncClient
from .exceptions import (
    ClientError,
    HTTPError,
    ConnectionError,
    TimeoutError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)
from .auth import (
    Auth,
    APIKeyAuth,
    BearerTokenAuth,
    BasicAuth,
    CustomAuth,
)
from .config import ClientConfig, TimeoutConfig
from .retry import RetryConfig

__version__ = "0.1.0"

__all__ = [
    # Clients
    "Client",
    "AsyncClient",
    # Exceptions
    "ClientError",
    "HTTPError",
    "ConnectionError",
    "TimeoutError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    # Authentication
    "Auth",
    "APIKeyAuth",
    "BearerTokenAuth",
    "BasicAuth",
    "CustomAuth",
    # Configuration
    "ClientConfig",
    "TimeoutConfig",
    "RetryConfig",
    # Version
    "__version__",
]

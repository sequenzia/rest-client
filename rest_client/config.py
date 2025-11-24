"""
Configuration classes for the REST client library.

This module provides configuration management for client instances.
"""

from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field
import httpx

from .retry import RetryConfig


@dataclass
class TimeoutConfig:
    """
    Configuration for request timeouts.

    Attributes:
        connect: Maximum time to establish connection (seconds)
        read: Maximum time to receive response data (seconds)
        write: Maximum time to send request data (seconds)
        pool: Maximum time to acquire a connection from the pool (seconds)
    """

    connect: Optional[float] = 5.0
    read: Optional[float] = 30.0
    write: Optional[float] = 30.0
    pool: Optional[float] = 5.0

    def to_httpx_timeout(self) -> httpx.Timeout:
        """Convert to httpx.Timeout object."""
        return httpx.Timeout(
            connect=self.connect,
            read=self.read,
            write=self.write,
            pool=self.pool,
        )


@dataclass
class ClientConfig:
    """
    Configuration for REST client instances.

    Attributes:
        base_url: Root URL for all API requests
        headers: Default headers applied to all requests
        timeout: Timeout configuration
        retry: Retry policy configuration
        verify_ssl: Whether to verify SSL certificates
        cert: Client certificate for SSL authentication
        max_redirects: Maximum number of redirects to follow
        pool_limits: Connection pool size limits
    """

    base_url: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry: Optional[RetryConfig] = field(default_factory=lambda: RetryConfig())
    verify_ssl: bool = True
    cert: Optional[Union[str, tuple]] = None
    max_redirects: int = 20
    pool_limits: Optional[Dict[str, int]] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.base_url:
            raise ValueError("base_url is required")

        # Ensure base_url doesn't end with a slash
        if self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")

        # Set default pool limits if not provided
        if self.pool_limits is None:
            self.pool_limits = {
                "max_keepalive_connections": 20,
                "max_connections": 100,
            }

    def get_httpx_limits(self) -> httpx.Limits:
        """Get httpx.Limits object from pool_limits."""
        return httpx.Limits(
            max_keepalive_connections=self.pool_limits.get(
                "max_keepalive_connections", 20
            ),
            max_connections=self.pool_limits.get("max_connections", 100),
        )

    def merge_headers(self, request_headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """
        Merge default headers with request-specific headers.

        Args:
            request_headers: Request-specific headers

        Returns:
            Merged headers dict
        """
        headers = self.headers.copy()
        if request_headers:
            headers.update(request_headers)
        return headers

    def merge_timeout(
        self, request_timeout: Optional[Union[float, TimeoutConfig]]
    ) -> httpx.Timeout:
        """
        Merge default timeout with request-specific timeout.

        Args:
            request_timeout: Request-specific timeout

        Returns:
            httpx.Timeout object
        """
        if request_timeout is None:
            return self.timeout.to_httpx_timeout()

        if isinstance(request_timeout, (int, float)):
            # If a single number is provided, use it for all timeout types
            return httpx.Timeout(request_timeout)

        if isinstance(request_timeout, TimeoutConfig):
            return request_timeout.to_httpx_timeout()

        return self.timeout.to_httpx_timeout()

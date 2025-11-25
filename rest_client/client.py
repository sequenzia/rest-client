"""
Synchronous REST client implementation.

This module provides a synchronous HTTP client for REST API interactions.
"""

from typing import Optional, Dict, Any, Union, Iterator
import httpx
import logging
from contextlib import contextmanager

from .config import ClientConfig, TimeoutConfig
from .auth import Auth, create_auth
from .retry import RetryConfig, RetryHandler
from .exceptions import (
    raise_for_status,
    ConnectionError as ClientConnectionError,
    TimeoutError as ClientTimeoutError,
)

logger = logging.getLogger(__name__)


class Client:
    """
    Synchronous REST API client.

    This client provides methods for making HTTP requests to REST APIs
    with support for authentication, retry logic, and streaming.

    Example:
        >>> client = Client(base_url="https://api.example.com", api_key="your-key")
        >>> response = client.get("/users/123")
        >>> user = response.json()

    Example with context manager:
        >>> with Client(base_url="https://api.example.com") as client:
        ...     response = client.get("/users")
    """

    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
        retry: Optional[RetryConfig] = None,
        verify_ssl: bool = True,
        cert: Optional[Union[str, tuple]] = None,
        max_redirects: int = 20,
        pool_limits: Optional[Dict[str, int]] = None,
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth: Optional[Auth] = None,
        raise_for_status_enabled: bool = True,
        **auth_kwargs,
    ):
        """
        Initialize the synchronous REST client.

        Args:
            base_url: Root URL for all API requests
            headers: Default headers applied to all requests
            timeout: Timeout configuration (seconds or TimeoutConfig)
            retry: Retry policy configuration
            verify_ssl: Whether to verify SSL certificates
            cert: Client certificate for SSL authentication
            max_redirects: Maximum number of redirects to follow
            pool_limits: Connection pool size limits
            api_key: API key for authentication
            bearer_token: Bearer token for authentication
            username: Username for basic authentication
            password: Password for basic authentication
            auth: Custom authentication handler
            raise_for_status_enabled: Whether to automatically raise exceptions for HTTP errors
            **auth_kwargs: Additional authentication arguments
        """
        # Create timeout config
        if timeout is None:
            timeout_config = TimeoutConfig()
        elif isinstance(timeout, (int, float)):
            timeout_config = TimeoutConfig(
                connect=timeout, read=timeout, write=timeout, pool=timeout
            )
        else:
            timeout_config = timeout

        # Create client configuration
        self.config = ClientConfig(
            base_url=base_url,
            headers=headers or {},
            timeout=timeout_config,
            retry=retry,
            verify_ssl=verify_ssl,
            cert=cert,
            max_redirects=max_redirects,
            pool_limits=pool_limits,
        )

        # Set up authentication
        self.auth = create_auth(
            api_key=api_key,
            bearer_token=bearer_token,
            username=username,
            password=password,
            auth=auth,
            **auth_kwargs,
        )

        # Configure automatic error raising
        self.raise_for_status_enabled = raise_for_status_enabled

        # Create retry handler
        self.retry_handler = (
            RetryHandler(self.config.retry) if self.config.retry else None
        )

        # Initialize httpx client (lazily created)
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Get or create the underlying httpx client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers=self.config.headers,
                timeout=self.config.timeout.to_httpx_timeout(),
                verify=self.config.verify_ssl,
                cert=self.config.cert,
                max_redirects=self.config.max_redirects,
                limits=self.config.get_httpx_limits(),
            )
        return self._client

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and clean up resources."""
        self.close()
        return False

    def close(self):
        """Close the client and clean up resources."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def _apply_auth(self, request: httpx.Request) -> httpx.Request:
        """Apply authentication to a request."""
        if self.auth:
            return self.auth.apply(request)
        return request

    def _build_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        content: Optional[bytes] = None,
    ) -> httpx.Request:
        """Build an HTTP request."""
        # Merge headers
        merged_headers = self.config.merge_headers(headers)

        # Build request
        request = self.client.build_request(
            method=method,
            url=url,
            params=params,
            headers=merged_headers,
            json=json,
            data=data,
            files=files,
            content=content,
        )

        # Apply authentication
        request = self._apply_auth(request)

        return request

    def _send_request(
        self,
        request: httpx.Request,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
        follow_redirects: bool = True,
    ) -> httpx.Response:
        """Send an HTTP request with retry logic."""
        # Merge timeout
        merged_timeout = self.config.merge_timeout(timeout)

        # Define request function
        def make_request() -> httpx.Response:
            try:
                logger.debug(f"{request.method} {request.url}")
                response = self.client.send(
                    request,
                    timeout=merged_timeout,
                    follow_redirects=follow_redirects,
                )
                logger.info(
                    f"{request.method} {request.url} -> {response.status_code}"
                )
                return response
            except httpx.ConnectError as e:
                logger.error(f"Connection error: {e}")
                raise ClientConnectionError(str(e)) from e
            except httpx.ReadTimeout as e:
                logger.error(f"Read timeout: {e}")
                raise ClientTimeoutError(str(e)) from e

        # Execute with retry logic if configured
        if self.retry_handler:
            response = self.retry_handler.execute(make_request)
        else:
            response = make_request()

        # Raise for status if enabled
        if self.raise_for_status_enabled:
            raise_for_status(response)

        return response

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        content: Optional[bytes] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
        follow_redirects: bool = True,
    ) -> httpx.Response:
        """
        Make an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            json: JSON request body
            data: Form data request body
            files: Files for multipart upload
            content: Raw request body
            timeout: Request timeout override
            follow_redirects: Whether to follow redirects

        Returns:
            HTTP response

        Raises:
            HTTPError: For HTTP error status codes (if raise_for_status_enabled)
            ConnectionError: For network connectivity issues
            TimeoutError: For request timeouts
        """
        request = self._build_request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            files=files,
            content=content,
        )
        return self._send_request(
            request, timeout=timeout, follow_redirects=follow_redirects
        )

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
    ) -> httpx.Response:
        """
        Make a GET request.

        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            timeout: Request timeout override

        Returns:
            HTTP response
        """
        return self.request("GET", url, params=params, headers=headers, timeout=timeout)

    def post(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        content: Optional[bytes] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
    ) -> httpx.Response:
        """
        Make a POST request.

        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            json: JSON request body
            data: Form data request body
            files: Files for multipart upload
            content: Raw request body
            timeout: Request timeout override

        Returns:
            HTTP response
        """
        return self.request(
            "POST",
            url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            files=files,
            content=content,
            timeout=timeout,
        )

    def put(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        content: Optional[bytes] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
    ) -> httpx.Response:
        """
        Make a PUT request.

        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            json: JSON request body
            data: Form data request body
            files: Files for multipart upload
            content: Raw request body
            timeout: Request timeout override

        Returns:
            HTTP response
        """
        return self.request(
            "PUT",
            url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            files=files,
            content=content,
            timeout=timeout,
        )

    def patch(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        content: Optional[bytes] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
    ) -> httpx.Response:
        """
        Make a PATCH request.

        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            json: JSON request body
            data: Form data request body
            files: Files for multipart upload
            content: Raw request body
            timeout: Request timeout override

        Returns:
            HTTP response
        """
        return self.request(
            "PATCH",
            url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            files=files,
            content=content,
            timeout=timeout,
        )

    def delete(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
    ) -> httpx.Response:
        """
        Make a DELETE request.

        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            timeout: Request timeout override

        Returns:
            HTTP response
        """
        return self.request(
            "DELETE", url, params=params, headers=headers, timeout=timeout
        )

    def head(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
    ) -> httpx.Response:
        """
        Make a HEAD request.

        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            timeout: Request timeout override

        Returns:
            HTTP response
        """
        return self.request("HEAD", url, params=params, headers=headers, timeout=timeout)

    def options(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
    ) -> httpx.Response:
        """
        Make an OPTIONS request.

        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            timeout: Request timeout override

        Returns:
            HTTP response
        """
        return self.request(
            "OPTIONS", url, params=params, headers=headers, timeout=timeout
        )

    @contextmanager
    def stream(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        content: Optional[bytes] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
    ) -> Iterator[httpx.Response]:
        """
        Stream an HTTP response.

        This method returns a context manager that yields a streaming response.
        The response content is not loaded into memory until you iterate over it.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL path (relative to base_url)
            params: Query parameters
            headers: Request headers
            json: JSON request body
            data: Form data request body
            files: Files for multipart upload
            content: Raw request body
            timeout: Request timeout override

        Yields:
            Streaming HTTP response

        Example:
            >>> with client.stream("GET", "/large-file") as response:
            ...     for chunk in response.iter_bytes(chunk_size=8192):
            ...         process_chunk(chunk)
        """
        request = self._build_request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            files=files,
            content=content,
        )

        merged_timeout = self.config.merge_timeout(timeout)

        with self.client.stream(
            request.method,
            request.url,
            headers=dict(request.headers),
            content=request.content,
            timeout=merged_timeout,
        ) as response:
            if self.raise_for_status_enabled:
                raise_for_status(response)
            yield response

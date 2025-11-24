"""
Exception hierarchy for the REST client library.

This module defines custom exceptions for different failure scenarios
to provide granular error handling capabilities.
"""

from typing import Optional, Dict, Any
import httpx


class ClientError(Exception):
    """Base exception for all client errors."""

    def __init__(self, message: str, response: Optional[httpx.Response] = None):
        """
        Initialize a ClientError.

        Args:
            message: Error message
            response: Optional HTTP response associated with the error
        """
        super().__init__(message)
        self.message = message
        self.response = response


class HTTPError(ClientError):
    """HTTP-level errors (4xx, 5xx responses)."""

    def __init__(
        self,
        message: str,
        response: httpx.Response,
        status_code: int,
    ):
        """
        Initialize an HTTPError.

        Args:
            message: Error message
            response: HTTP response that caused the error
            status_code: HTTP status code
        """
        super().__init__(message, response)
        self.status_code = status_code

    def __str__(self) -> str:
        return f"{self.status_code} {self.message}"


class ConnectionError(ClientError):
    """Network connectivity issues."""

    pass


class TimeoutError(ClientError):
    """Request timeout exceeded."""

    pass


class AuthenticationError(HTTPError):
    """Authentication failures (401, 403)."""

    def __init__(self, message: str, response: httpx.Response):
        """
        Initialize an AuthenticationError.

        Args:
            message: Error message
            response: HTTP response that caused the error
        """
        super().__init__(message, response, response.status_code)


class RateLimitError(HTTPError):
    """Rate limit exceeded (429)."""

    def __init__(
        self,
        message: str,
        response: httpx.Response,
        retry_after: Optional[int] = None,
    ):
        """
        Initialize a RateLimitError.

        Args:
            message: Error message
            response: HTTP response that caused the error
            retry_after: Optional seconds to wait before retrying
        """
        super().__init__(message, response, 429)
        self.retry_after = retry_after


class ValidationError(ClientError):
    """Request/response validation failures."""

    pass


def raise_for_status(response: httpx.Response) -> None:
    """
    Raise an appropriate exception for HTTP error status codes.

    Args:
        response: HTTP response to check

    Raises:
        AuthenticationError: For 401, 403 status codes
        RateLimitError: For 429 status code
        HTTPError: For other 4xx, 5xx status codes
    """
    if response.is_success:
        return

    message = f"{response.status_code} {response.reason_phrase}"

    # Try to extract error message from response body
    try:
        error_data = response.json()
        if isinstance(error_data, dict):
            message = error_data.get("message", error_data.get("error", message))
    except Exception:
        # If we can't parse JSON, use the default message
        pass

    if response.status_code in (401, 403):
        raise AuthenticationError(message, response)
    elif response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        retry_after_seconds = int(retry_after) if retry_after else None
        raise RateLimitError(message, response, retry_after_seconds)
    elif response.status_code >= 400:
        raise HTTPError(message, response, response.status_code)

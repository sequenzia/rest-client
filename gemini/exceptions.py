from typing import Optional, Any

class ClientError(Exception):
    """Base exception for all client errors."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error

class ConnectionError(ClientError):
    """Network connectivity issues."""
    pass

class TimeoutError(ClientError):
    """Request timeout exceeded."""
    pass

class HTTPError(ClientError):
    """Base for HTTP-level errors (4xx, 5xx)."""
    def __init__(
        self, 
        message: str, 
        status_code: int, 
        headers: Optional[dict] = None, 
        body: Any = None
    ):
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.headers = headers or {}
        self.body = body

class AuthenticationError(HTTPError):
    """Authentication failures (401, 403)."""
    pass

class RateLimitError(HTTPError):
    """Rate limit exceeded (429)."""
    pass

class ServerError(HTTPError):
    """Server-side errors (5xx)."""
    pass

class ValidationError(ClientError):
    """Request/response validation failures."""
    pass

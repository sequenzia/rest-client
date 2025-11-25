import asyncio
import time
import logging
import json
import random
from typing import (
    Any, Dict, Optional, Union, Generator, AsyncGenerator, 
    Tuple, Callable, Type, TypeVar
)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

# Import exceptions from the block above (assuming same file for snippet)
# from .exceptions import * # --- Configuration ---

@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    retry_codes: set[int] = field(default_factory=lambda: {408, 429, 500, 502, 503, 504})

@dataclass
class ClientConfig:
    base_url: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    auth: Optional[Tuple[str, str]] = None  # Basic Auth
    token: Optional[str] = None             # Bearer Token
    verify_ssl: bool = True
    retry: RetryConfig = field(default_factory=RetryConfig)

# --- Logging Setup ---
logger = logging.getLogger("rest_client")
logger.addHandler(logging.NullHandler())

# --- Utils ---

T = TypeVar("T")

def _calculate_backoff(attempt: int, config: RetryConfig, retry_after: Optional[float] = None) -> float:
    """Calculates sleep time with exponential backoff and jitter."""
    if retry_after is not None:
        return retry_after
    
    delay = min(config.max_delay, config.base_delay * (2 ** attempt))
    if config.jitter:
        delay = delay * random.uniform(0.5, 1.5)
    return delay

def _map_exception(e: Exception) -> Exception:
    """Maps httpx exceptions to custom ClientError hierarchy."""
    if isinstance(e, httpx.TimeoutException):
        return TimeoutError("Request timed out", original_error=e)
    if isinstance(e, httpx.NetworkError):
        return ConnectionError("Network error occurred", original_error=e)
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        content = e.response.text
        headers = dict(e.response.headers)
        
        if status in (401, 403):
            return AuthenticationError("Authentication failed", status, headers, content)
        if status == 429:
            return RateLimitError("Rate limit exceeded", status, headers, content)
        if 500 <= status < 600:
            return ServerError("Server error", status, headers, content)
        return HTTPError("HTTP error", status, headers, content)
    
    return ClientError(f"Unexpected error: {str(e)}", original_error=e)

# --- Base Client Logic ---

class _BaseClient(ABC):
    """Shared logic for Sync and Async clients."""
    
    def __init__(self, config: ClientConfig):
        self.config = config
        self._headers = config.headers.copy()
        self._headers.setdefault("User-Agent", "Python-REST-Client/1.0")
        self._headers.setdefault("Accept", "application/json")
        
        # Authentication Setup
        self._auth = config.auth
        if config.token:
            self._headers["Authorization"] = f"Bearer {config.token}"

    def _get_timeout(self, timeout_override: Optional[float]) -> float:
        return timeout_override if timeout_override is not None else self.config.timeout

    def _should_retry(self, status_code: int) -> bool:
        return status_code in self.config.retry.retry_codes

    def _get_retry_after(self, response: httpx.Response) -> Optional[float]:
        header = response.headers.get("Retry-After")
        if not header:
            return None
        try:
            return float(header)
        except ValueError:
            return None  # Handle HTTP-date format if necessary

# --- Synchronous Client ---

class Client(_BaseClient):
    def __init__(self, base_url: str, **kwargs):
        config = ClientConfig(base_url=base_url, **kwargs)
        super().__init__(config)
        self._client = httpx.Client(
            base_url=config.base_url,
            headers=self._headers,
            auth=self._auth,
            verify=config.verify_ssl,
            timeout=config.timeout
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self._client.close()

    def _request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> httpx.Response:
        attempt = 0
        timeout = self._get_timeout(kwargs.pop('timeout', None))
        
        while True:
            try:
                logger.debug(f"Attempt {attempt+1}: {method} {endpoint}")
                response = self._client.request(method, endpoint, timeout=timeout, **kwargs)
                response.raise_for_status()
                return response
            
            except httpx.HTTPStatusError as e:
                if attempt < self.config.retry.max_attempts and self._should_retry(e.response.status_code):
                    retry_after = self._get_retry_after(e.response)
                    sleep_time = _calculate_backoff(attempt, self.config.retry, retry_after)
                    logger.warning(f"Retrying {method} {endpoint} in {sleep_time:.2f}s (Code: {e.response.status_code})")
                    time.sleep(sleep_time)
                    attempt += 1
                    continue
                raise _map_exception(e)
            
            except (httpx.NetworkError, httpx.TimeoutException) as e:
                if attempt < self.config.retry.max_attempts:
                    sleep_time = _calculate_backoff(attempt, self.config.retry)
                    logger.warning(f"Retrying {method} {endpoint} due to network error in {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                    attempt += 1
                    continue
                raise _map_exception(e)
            except Exception as e:
                raise _map_exception(e)

    def get(self, endpoint: str, params: Optional[dict] = None, **kwargs) -> Any:
        response = self._request("GET", endpoint, params=params, **kwargs)
        return response.json()

    def post(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> Any:
        response = self._request("POST", endpoint, data=data, json=json, **kwargs)
        return response.json()

    def put(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> Any:
        response = self._request("PUT", endpoint, data=data, json=json, **kwargs)
        return response.json()

    def patch(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> Any:
        response = self._request("PATCH", endpoint, data=data, json=json, **kwargs)
        return response.json()

    def delete(self, endpoint: str, **kwargs) -> Any:
        self._request("DELETE", endpoint, **kwargs)
        return None

    def stream(self, method: str, endpoint: str, **kwargs) -> Generator[bytes, None, None]:
        """
        Stream response data. Note: This bypasses the automatic retry logic 
        wrapper for simplicity in this MVP, but can be wrapped similarly.
        """
        try:
            # We use streaming() context manager from httpx
            with self._client.stream(method, endpoint, **kwargs) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    yield chunk
        except Exception as e:
            raise _map_exception(e)


# --- Asynchronous Client ---

class AsyncClient(_BaseClient):
    def __init__(self, base_url: str, **kwargs):
        config = ClientConfig(base_url=base_url, **kwargs)
        super().__init__(config)
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=self._headers,
            auth=self._auth,
            verify=config.verify_ssl,
            timeout=config.timeout
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def close(self):
        await self._client.aclose()

    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> httpx.Response:
        attempt = 0
        timeout = self._get_timeout(kwargs.pop('timeout', None))
        
        while True:
            try:
                logger.debug(f"Async Attempt {attempt+1}: {method} {endpoint}")
                response = await self._client.request(method, endpoint, timeout=timeout, **kwargs)
                response.raise_for_status()
                return response
            
            except httpx.HTTPStatusError as e:
                if attempt < self.config.retry.max_attempts and self._should_retry(e.response.status_code):
                    retry_after = self._get_retry_after(e.response)
                    sleep_time = _calculate_backoff(attempt, self.config.retry, retry_after)
                    logger.warning(f"Retrying {method} {endpoint} in {sleep_time:.2f}s (Code: {e.response.status_code})")
                    await asyncio.sleep(sleep_time)
                    attempt += 1
                    continue
                raise _map_exception(e)
            
            except (httpx.NetworkError, httpx.TimeoutException) as e:
                if attempt < self.config.retry.max_attempts:
                    sleep_time = _calculate_backoff(attempt, self.config.retry)
                    logger.warning(f"Retrying {method} {endpoint} due to network error in {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                    attempt += 1
                    continue
                raise _map_exception(e)
            except Exception as e:
                raise _map_exception(e)

    async def get(self, endpoint: str, params: Optional[dict] = None, **kwargs) -> Any:
        response = await self._request("GET", endpoint, params=params, **kwargs)
        return response.json()

    async def post(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> Any:
        response = await self._request("POST", endpoint, data=data, json=json, **kwargs)
        return response.json()

    async def put(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> Any:
        response = await self._request("PUT", endpoint, data=data, json=json, **kwargs)
        return response.json()

    async def patch(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> Any:
        response = await self._request("PATCH", endpoint, data=data, json=json, **kwargs)
        return response.json()

    async def delete(self, endpoint: str, **kwargs) -> Any:
        await self._request("DELETE", endpoint, **kwargs)
        return None

    async def stream(self, method: str, endpoint: str, **kwargs) -> AsyncGenerator[bytes, None]:
        try:
            async with self._client.stream(method, endpoint, **kwargs) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
        except Exception as e:
            raise _map_exception(e)

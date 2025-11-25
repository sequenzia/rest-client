"""
Retry logic with exponential backoff for the REST client library.

This module provides retry mechanisms for handling transient failures using Tenacity.
"""

import asyncio
from typing import Callable, Set, Optional, Union
import httpx
import logging
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    before_sleep_log,
    RetryCallState,
)

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_status_codes: Optional[Set[int]] = None,
        backoff_factor: float = 0.5,
        max_backoff: float = 60.0,
        jitter: bool = True,
    ):
        """
        Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            retry_status_codes: HTTP status codes that should trigger a retry
            backoff_factor: Multiplier for exponential backoff
            max_backoff: Maximum backoff time in seconds
            jitter: Whether to add random jitter to backoff times
        """
        self.max_retries = max_retries
        self.retry_status_codes = retry_status_codes or {408, 429, 500, 502, 503, 504}
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.jitter = jitter

    def should_retry(
        self,
        attempt: int,
        response: Optional[httpx.Response] = None,
        exception: Optional[Exception] = None,
    ) -> bool:
        """
        Determine if a request should be retried.

        Args:
            attempt: Current attempt number (0-indexed)
            response: HTTP response (if available)
            exception: Exception that occurred (if any)

        Returns:
            True if the request should be retried, False otherwise
        """
        if attempt >= self.max_retries:
            return False

        # Retry on network errors
        if exception is not None:
            if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
                return True
            return False

        # Retry on specific status codes
        if response is not None:
            return response.status_code in self.retry_status_codes

        return False

    def get_backoff_time(self, attempt: int, retry_after: Optional[int] = None) -> float:
        """
        Calculate backoff time for a retry attempt.

        Args:
            attempt: Current attempt number (0-indexed)
            retry_after: Optional Retry-After header value in seconds

        Returns:
            Backoff time in seconds
        """
        # Honor Retry-After header if present
        if retry_after is not None:
            return min(float(retry_after), self.max_backoff)

        # Calculate exponential backoff: backoff_factor * (2 ** attempt)
        import random
        backoff = self.backoff_factor * (2 ** attempt)
        backoff = min(backoff, self.max_backoff)

        # Add jitter to prevent thundering herd
        if self.jitter:
            backoff = backoff * (0.5 + random.random())

        return backoff


class RetryHandler:
    """Handler for executing requests with retry logic using Tenacity."""

    def __init__(self, config: RetryConfig):
        """
        Initialize retry handler.

        Args:
            config: Retry configuration
        """
        self.config = config

    def _should_retry_response(self, response: httpx.Response) -> bool:
        """Check if a response should trigger a retry."""
        return response.status_code in self.config.retry_status_codes

    def _log_retry_attempt(self, retry_state: RetryCallState):
        """Log retry attempts."""
        if retry_state.outcome and retry_state.outcome.failed:
            exception = retry_state.outcome.exception()
            logger.warning(
                f"Request failed with {type(exception).__name__}: {exception}, "
                f"retrying (attempt {retry_state.attempt_number}/{self.config.max_retries + 1})..."
            )
        elif retry_state.outcome:
            result = retry_state.outcome.result()
            if isinstance(result, httpx.Response):
                logger.warning(
                    f"Request failed with status {result.status_code}, "
                    f"retrying (attempt {retry_state.attempt_number}/{self.config.max_retries + 1})..."
                )

    def execute(
        self,
        func: Callable[[], httpx.Response],
    ) -> httpx.Response:
        """
        Execute a synchronous request with retry logic.

        Args:
            func: Function that performs the request

        Returns:
            HTTP response

        Raises:
            Exception: The last exception if all retries are exhausted
        """
        # Create a retry decorator with Tenacity
        retry_decorator = retry(
            retry=(
                retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout))
                | retry_if_result(self._should_retry_response)
            ),
            stop=stop_after_attempt(self.config.max_retries + 1),
            wait=wait_exponential(
                multiplier=self.config.backoff_factor,
                max=self.config.max_backoff,
            ),
            before_sleep=self._log_retry_attempt,
            reraise=True,
        )

        # Apply decorator and execute
        retrying_func = retry_decorator(func)
        return retrying_func()

    async def execute_async(
        self,
        func: Callable[[], httpx.Response],
    ) -> httpx.Response:
        """
        Execute an asynchronous request with retry logic.

        Args:
            func: Async function that performs the request

        Returns:
            HTTP response

        Raises:
            Exception: The last exception if all retries are exhausted
        """
        # Create a retry decorator with Tenacity for async
        retry_decorator = retry(
            retry=(
                retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout))
                | retry_if_result(self._should_retry_response)
            ),
            stop=stop_after_attempt(self.config.max_retries + 1),
            wait=wait_exponential(
                multiplier=self.config.backoff_factor,
                max=self.config.max_backoff,
            ),
            before_sleep=self._log_retry_attempt,
            reraise=True,
        )

        # Apply decorator and execute
        retrying_func = retry_decorator(func)
        return await retrying_func()

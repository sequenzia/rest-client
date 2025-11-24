"""
Retry logic with exponential backoff for the REST client library.

This module provides retry mechanisms for handling transient failures.
"""

import time
import random
import asyncio
from typing import Callable, Set, Optional, Union
import httpx
import logging

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
        backoff = self.backoff_factor * (2 ** attempt)
        backoff = min(backoff, self.max_backoff)

        # Add jitter to prevent thundering herd
        if self.jitter:
            backoff = backoff * (0.5 + random.random())

        return backoff


class RetryHandler:
    """Handler for executing requests with retry logic."""

    def __init__(self, config: RetryConfig):
        """
        Initialize retry handler.

        Args:
            config: Retry configuration
        """
        self.config = config

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
        last_exception = None
        response = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = func()

                # Check if we should retry based on status code
                if not self.config.should_retry(attempt, response=response):
                    return response

                # Extract Retry-After header if present
                retry_after = None
                if response.status_code == 429:
                    retry_after_header = response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            retry_after = int(retry_after_header)
                        except ValueError:
                            pass

                # Log retry attempt
                logger.warning(
                    f"Request failed with status {response.status_code}, "
                    f"retrying (attempt {attempt + 1}/{self.config.max_retries})..."
                )

                # Calculate and apply backoff
                if attempt < self.config.max_retries:
                    backoff_time = self.config.get_backoff_time(attempt, retry_after)
                    logger.debug(f"Backing off for {backoff_time:.2f} seconds")
                    time.sleep(backoff_time)

            except Exception as e:
                last_exception = e

                # Check if we should retry based on exception
                if not self.config.should_retry(attempt, exception=e):
                    raise

                # Log retry attempt
                logger.warning(
                    f"Request failed with {type(e).__name__}: {e}, "
                    f"retrying (attempt {attempt + 1}/{self.config.max_retries})..."
                )

                # Calculate and apply backoff
                if attempt < self.config.max_retries:
                    backoff_time = self.config.get_backoff_time(attempt)
                    logger.debug(f"Backing off for {backoff_time:.2f} seconds")
                    time.sleep(backoff_time)

        # If we exhausted all retries with a response, return it
        if response is not None:
            return response

        # Otherwise, raise the last exception
        if last_exception is not None:
            raise last_exception

        # This should never happen, but just in case
        raise RuntimeError("Retry logic failed unexpectedly")

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
        last_exception = None
        response = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = await func()

                # Check if we should retry based on status code
                if not self.config.should_retry(attempt, response=response):
                    return response

                # Extract Retry-After header if present
                retry_after = None
                if response.status_code == 429:
                    retry_after_header = response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            retry_after = int(retry_after_header)
                        except ValueError:
                            pass

                # Log retry attempt
                logger.warning(
                    f"Request failed with status {response.status_code}, "
                    f"retrying (attempt {attempt + 1}/{self.config.max_retries})..."
                )

                # Calculate and apply backoff
                if attempt < self.config.max_retries:
                    backoff_time = self.config.get_backoff_time(attempt, retry_after)
                    logger.debug(f"Backing off for {backoff_time:.2f} seconds")
                    await asyncio.sleep(backoff_time)

            except Exception as e:
                last_exception = e

                # Check if we should retry based on exception
                if not self.config.should_retry(attempt, exception=e):
                    raise

                # Log retry attempt
                logger.warning(
                    f"Request failed with {type(e).__name__}: {e}, "
                    f"retrying (attempt {attempt + 1}/{self.config.max_retries})..."
                )

                # Calculate and apply backoff
                if attempt < self.config.max_retries:
                    backoff_time = self.config.get_backoff_time(attempt)
                    logger.debug(f"Backing off for {backoff_time:.2f} seconds")
                    await asyncio.sleep(backoff_time)

        # If we exhausted all retries with a response, return it
        if response is not None:
            return response

        # Otherwise, raise the last exception
        if last_exception is not None:
            raise last_exception

        # This should never happen, but just in case
        raise RuntimeError("Retry logic failed unexpectedly")

"""Tests for retry logic."""

import pytest
import httpx
from unittest.mock import Mock

from rest_client.retry import RetryConfig, RetryHandler


class TestRetryConfig:
    """Test suite for RetryConfig."""

    def test_default_retry_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert 500 in config.retry_status_codes
        assert config.backoff_factor == 0.5
        assert config.jitter is True

    def test_custom_retry_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_retries=5,
            retry_status_codes={502, 503},
            backoff_factor=1.0,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.retry_status_codes == {502, 503}
        assert config.backoff_factor == 1.0
        assert config.jitter is False

    def test_should_retry_on_status_code(self):
        """Test retry decision based on status code."""
        config = RetryConfig()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500

        assert config.should_retry(0, response=mock_response) is True

    def test_should_not_retry_on_success(self):
        """Test no retry on successful status code."""
        config = RetryConfig()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        assert config.should_retry(0, response=mock_response) is False

    def test_should_not_retry_after_max_attempts(self):
        """Test no retry after max attempts."""
        config = RetryConfig(max_retries=3)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500

        assert config.should_retry(3, response=mock_response) is False

    def test_should_retry_on_connection_error(self):
        """Test retry on connection errors."""
        config = RetryConfig()
        exception = httpx.ConnectError("Connection failed")

        assert config.should_retry(0, exception=exception) is True

    def test_should_retry_on_timeout(self):
        """Test retry on timeout errors."""
        config = RetryConfig()
        exception = httpx.ReadTimeout("Read timeout")

        assert config.should_retry(0, exception=exception) is True

    def test_should_not_retry_on_other_exceptions(self):
        """Test no retry on other exceptions."""
        config = RetryConfig()
        exception = ValueError("Invalid value")

        assert config.should_retry(0, exception=exception) is False

    def test_backoff_time_calculation(self):
        """Test backoff time calculation."""
        config = RetryConfig(backoff_factor=1.0, jitter=False)

        # Exponential backoff: factor * (2 ** attempt)
        assert config.get_backoff_time(0) == 1.0  # 1.0 * 2^0
        assert config.get_backoff_time(1) == 2.0  # 1.0 * 2^1
        assert config.get_backoff_time(2) == 4.0  # 1.0 * 2^2

    def test_backoff_time_with_max(self):
        """Test backoff time respects max_backoff."""
        config = RetryConfig(backoff_factor=1.0, max_backoff=3.0, jitter=False)

        assert config.get_backoff_time(5) == 3.0  # Capped at max_backoff

    def test_backoff_time_with_retry_after(self):
        """Test backoff time honors Retry-After header."""
        config = RetryConfig()

        backoff = config.get_backoff_time(0, retry_after=10)
        assert backoff == 10.0

    def test_backoff_time_with_jitter(self):
        """Test that jitter adds randomness to backoff time."""
        config = RetryConfig(backoff_factor=2.0, jitter=True)

        # With jitter, backoff should be within range
        backoff = config.get_backoff_time(1)  # Base: 2.0 * 2^1 = 4.0

        # With jitter: 4.0 * (0.5 + random()) = [2.0, 6.0]
        assert 2.0 <= backoff <= 6.0


class TestRetryHandler:
    """Test suite for RetryHandler."""

    def test_retry_handler_success_first_try(self):
        """Test that successful request on first try doesn't retry."""
        config = RetryConfig()
        handler = RetryHandler(config)

        call_count = 0

        def make_request():
            nonlocal call_count
            call_count += 1
            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200
            return mock_response

        response = handler.execute(make_request)

        assert response.status_code == 200
        assert call_count == 1

    def test_retry_handler_retries_on_500(self):
        """Test that 500 errors trigger retries."""
        config = RetryConfig(max_retries=2, backoff_factor=0.01)
        handler = RetryHandler(config)

        call_count = 0

        def make_request():
            nonlocal call_count
            call_count += 1
            mock_response = Mock(spec=httpx.Response)
            if call_count < 3:
                mock_response.status_code = 500
            else:
                mock_response.status_code = 200
            return mock_response

        response = handler.execute(make_request)

        assert response.status_code == 200
        assert call_count == 3  # 1 initial + 2 retries

    def test_retry_handler_exhausts_retries(self):
        """Test that retry handler returns last response after exhausting retries."""
        config = RetryConfig(max_retries=2, backoff_factor=0.01)
        handler = RetryHandler(config)

        def make_request():
            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 500
            return mock_response

        response = handler.execute(make_request)

        # Should return the last failing response
        assert response.status_code == 500

    def test_retry_handler_raises_on_non_retryable_exception(self):
        """Test that non-retryable exceptions are raised immediately."""
        config = RetryConfig()
        handler = RetryHandler(config)

        def make_request():
            raise ValueError("Invalid value")

        with pytest.raises(ValueError):
            handler.execute(make_request)

"""Tests for exception hierarchy."""

import pytest
import httpx
from unittest.mock import Mock

from rest_client.exceptions import (
    ClientError,
    HTTPError,
    ConnectionError,
    TimeoutError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    raise_for_status,
)


class TestExceptions:
    """Test suite for exception classes."""

    def test_client_error_base(self):
        """Test base ClientError exception."""
        error = ClientError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.response is None

    def test_http_error(self):
        """Test HTTPError exception."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500

        error = HTTPError("Server error", mock_response, 500)
        assert error.status_code == 500
        assert error.response == mock_response
        assert "500" in str(error)

    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 401

        error = AuthenticationError("Unauthorized", mock_response)
        assert error.status_code == 401

    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429

        error = RateLimitError("Too many requests", mock_response, retry_after=60)
        assert error.status_code == 429
        assert error.retry_after == 60

    def test_rate_limit_error_without_retry_after(self):
        """Test RateLimitError without retry_after."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429

        error = RateLimitError("Too many requests", mock_response)
        assert error.retry_after is None


class TestRaiseForStatus:
    """Test suite for raise_for_status function."""

    def test_success_status(self):
        """Test that successful responses don't raise."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 200

        # Should not raise
        raise_for_status(mock_response)

    def test_404_raises_http_error(self):
        """Test that 404 raises HTTPError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        mock_response.json.side_effect = Exception()  # No JSON body

        with pytest.raises(HTTPError) as exc_info:
            raise_for_status(mock_response)

        assert exc_info.value.status_code == 404

    def test_401_raises_authentication_error(self):
        """Test that 401 raises AuthenticationError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 401
        mock_response.reason_phrase = "Unauthorized"
        mock_response.json.side_effect = Exception()

        with pytest.raises(AuthenticationError):
            raise_for_status(mock_response)

    def test_403_raises_authentication_error(self):
        """Test that 403 raises AuthenticationError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 403
        mock_response.reason_phrase = "Forbidden"
        mock_response.json.side_effect = Exception()

        with pytest.raises(AuthenticationError):
            raise_for_status(mock_response)

    def test_429_raises_rate_limit_error(self):
        """Test that 429 raises RateLimitError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 429
        mock_response.reason_phrase = "Too Many Requests"
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.side_effect = Exception()

        with pytest.raises(RateLimitError) as exc_info:
            raise_for_status(mock_response)

        assert exc_info.value.retry_after == 30

    def test_500_raises_http_error(self):
        """Test that 500 raises HTTPError."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.reason_phrase = "Internal Server Error"
        mock_response.json.side_effect = Exception()

        with pytest.raises(HTTPError) as exc_info:
            raise_for_status(mock_response)

        assert exc_info.value.status_code == 500

    def test_error_message_from_json(self):
        """Test that error message is extracted from JSON response."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 400
        mock_response.reason_phrase = "Bad Request"
        mock_response.json.return_value = {"message": "Invalid input"}

        with pytest.raises(HTTPError) as exc_info:
            raise_for_status(mock_response)

        assert "Invalid input" in str(exc_info.value)

# Python REST Client

A comprehensive, production-ready Python library for interacting with REST APIs. Built on top of `httpx`, it provides both synchronous and asynchronous clients with support for authentication, retry logic, streaming, and more.

## Features

### Core Capabilities
- ✅ **Dual Interface**: Both synchronous and asynchronous clients
- ✅ **All HTTP Methods**: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
- ✅ **Authentication**: API Key, Bearer Token, Basic Auth, and custom handlers
- ✅ **Automatic Retries**: Exponential backoff with jitter for transient failures
- ✅ **Response Streaming**: Memory-efficient handling of large responses
- ✅ **Comprehensive Error Handling**: Granular exception hierarchy
- ✅ **Type Hints**: Full type annotations for excellent IDE support
- ✅ **Configurable Timeouts**: Connection, read, write, and pool timeouts
- ✅ **SSL/TLS Support**: Certificate verification and client certificates
- ✅ **Connection Pooling**: Efficient connection reuse
- ✅ **Context Managers**: Automatic resource cleanup

## Installation

```bash
pip install rest-client
```

For development dependencies:

```bash
pip install rest-client[dev]
```

For optional performance improvements:

```bash
pip install rest-client[fast]
```

## Quick Start

### Synchronous Client

```python
from rest_client import Client

# Create a client
client = Client(
    base_url="https://api.example.com",
    api_key="your-api-key"
)

# Make requests
response = client.get("/users/123")
user = response.json()

# POST request
new_user = client.post("/users", json={"name": "John Doe", "email": "john@example.com"})

# With context manager (recommended)
with Client(base_url="https://api.example.com", api_key="your-key") as client:
    users = client.get("/users").json()
    print(users)
```

### Asynchronous Client

```python
from rest_client import AsyncClient

async def main():
    async with AsyncClient(base_url="https://api.example.com", api_key="your-key") as client:
        response = await client.get("/users/123")
        user = response.json()

        # POST request
        new_user = await client.post("/users", json={"name": "Jane Doe"})
```

## Authentication

### API Key Authentication

```python
# In header (default)
client = Client(
    base_url="https://api.example.com",
    api_key="your-api-key"
)

# In query parameter
client = Client(
    base_url="https://api.example.com",
    api_key="your-api-key",
    api_key_location="query",
    api_key_name="apikey"
)
```

### Bearer Token Authentication

```python
client = Client(
    base_url="https://api.example.com",
    bearer_token="your-bearer-token"
)
```

### Basic Authentication

```python
client = Client(
    base_url="https://api.example.com",
    username="user",
    password="pass"
)
```

### Custom Authentication

```python
from rest_client import CustomAuth

def my_auth_handler(request):
    request.headers["X-Custom-Auth"] = "my-token"
    return request

client = Client(
    base_url="https://api.example.com",
    auth=CustomAuth(my_auth_handler)
)
```

## Making Requests

### GET Requests

```python
# Simple GET
response = client.get("/users")

# With query parameters
response = client.get("/search", params={"q": "python", "limit": 10})

# With custom headers
response = client.get("/users", headers={"X-Custom-Header": "value"})
```

### POST Requests

```python
# JSON body
response = client.post("/users", json={"name": "John", "email": "john@example.com"})

# Form data
response = client.post("/login", data={"username": "user", "password": "pass"})

# File upload
with open("file.txt", "rb") as f:
    response = client.post("/upload", files={"file": f})
```

### Other HTTP Methods

```python
# PUT
response = client.put("/users/123", json={"name": "Updated Name"})

# PATCH
response = client.patch("/users/123", json={"email": "new@example.com"})

# DELETE
response = client.delete("/users/123")

# HEAD
response = client.head("/users/123")

# OPTIONS
response = client.options("/users")
```

## Response Streaming

For large responses, use streaming to avoid loading everything into memory:

```python
# Synchronous streaming
with client.stream("GET", "/large-file") as response:
    for chunk in response.iter_bytes(chunk_size=8192):
        process_chunk(chunk)

# Asynchronous streaming
async with client.stream("GET", "/large-file") as response:
    async for chunk in response.aiter_bytes(chunk_size=8192):
        await process_chunk(chunk)
```

## Retry Configuration

Configure automatic retries for transient failures:

```python
from rest_client import Client, RetryConfig

retry_config = RetryConfig(
    max_retries=3,
    retry_status_codes={408, 429, 500, 502, 503, 504},
    backoff_factor=0.5,
    max_backoff=60.0,
    jitter=True
)

client = Client(
    base_url="https://api.example.com",
    retry=retry_config
)
```

To disable retries:

```python
client = Client(
    base_url="https://api.example.com",
    retry=None
)
```

## Timeout Configuration

Configure timeouts to prevent hanging requests:

```python
from rest_client import Client, TimeoutConfig

# Simple timeout (applies to all timeout types)
client = Client(base_url="https://api.example.com", timeout=30.0)

# Granular timeout configuration
timeout_config = TimeoutConfig(
    connect=5.0,   # Connection timeout
    read=30.0,     # Read timeout
    write=30.0,    # Write timeout
    pool=5.0       # Pool timeout
)

client = Client(base_url="https://api.example.com", timeout=timeout_config)

# Per-request timeout override
response = client.get("/slow-endpoint", timeout=60.0)
```

## Error Handling

The library provides a comprehensive exception hierarchy:

```python
from rest_client import (
    ClientError,           # Base exception
    HTTPError,             # HTTP errors (4xx, 5xx)
    AuthenticationError,   # 401, 403 errors
    RateLimitError,        # 429 errors
    ConnectionError,       # Network errors
    TimeoutError,          # Timeout errors
    ValidationError        # Validation errors
)

try:
    response = client.get("/users/123")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    print(f"Status code: {e.status_code}")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after} seconds")
except HTTPError as e:
    print(f"HTTP error {e.status_code}: {e.message}")
except ConnectionError as e:
    print(f"Connection failed: {e}")
except TimeoutError as e:
    print(f"Request timed out: {e}")
```

To handle errors manually without exceptions:

```python
client = Client(
    base_url="https://api.example.com",
    raise_for_status_enabled=False
)

response = client.get("/users/123")
if response.status_code == 200:
    user = response.json()
else:
    print(f"Error: {response.status_code}")
```

## Advanced Configuration

### SSL/TLS Configuration

```python
# Disable SSL verification (not recommended for production)
client = Client(base_url="https://api.example.com", verify_ssl=False)

# Use custom CA bundle
client = Client(base_url="https://api.example.com", cert="/path/to/ca-bundle.crt")

# Client certificate authentication
client = Client(
    base_url="https://api.example.com",
    cert=("/path/to/client.crt", "/path/to/client.key")
)
```

### Connection Pool Configuration

```python
client = Client(
    base_url="https://api.example.com",
    pool_limits={
        "max_keepalive_connections": 20,
        "max_connections": 100
    }
)
```

### Custom Headers

```python
# Default headers for all requests
client = Client(
    base_url="https://api.example.com",
    headers={
        "User-Agent": "MyApp/1.0",
        "Accept": "application/json"
    }
)

# Override per request
response = client.get("/users", headers={"Accept": "application/xml"})
```

## Complete Example

```python
from rest_client import Client, RetryConfig, TimeoutConfig, HTTPError

# Configure retry and timeout
retry_config = RetryConfig(max_retries=3, backoff_factor=0.5)
timeout_config = TimeoutConfig(connect=5.0, read=30.0)

# Create client with all options
with Client(
    base_url="https://api.example.com",
    bearer_token="your-token",
    headers={"User-Agent": "MyApp/1.0"},
    timeout=timeout_config,
    retry=retry_config,
    verify_ssl=True
) as client:
    try:
        # Get all users
        users = client.get("/users", params={"limit": 100}).json()

        # Create a new user
        new_user = client.post("/users", json={
            "name": "John Doe",
            "email": "john@example.com"
        }).json()

        print(f"Created user: {new_user['id']}")

        # Update the user
        updated = client.patch(f"/users/{new_user['id']}", json={
            "name": "Jane Doe"
        }).json()

        print(f"Updated user: {updated}")

    except HTTPError as e:
        print(f"API error: {e.status_code} - {e.message}")
```

## Async Example

```python
import asyncio
from rest_client import AsyncClient, HTTPError

async def main():
    async with AsyncClient(
        base_url="https://api.example.com",
        api_key="your-key"
    ) as client:
        try:
            # Concurrent requests
            tasks = [
                client.get(f"/users/{i}")
                for i in range(1, 11)
            ]
            responses = await asyncio.gather(*tasks)
            users = [r.json() for r in responses]

            print(f"Fetched {len(users)} users concurrently")

        except HTTPError as e:
            print(f"Error: {e}")

asyncio.run(main())
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=rest_client --cov-report=html
```

### Code Quality

```bash
# Format code
black rest_client tests

# Lint
ruff check rest_client tests

# Type checking
mypy rest_client
```

## Requirements

- Python 3.8+
- httpx >= 0.24.0
- certifi >= 2023.0.0

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please use the [GitHub issue tracker](https://github.com/yourusername/rest-client/issues)
"""
Basic usage examples for the Python REST Client library.

This module demonstrates common usage patterns for both synchronous
and asynchronous clients.
"""

import asyncio
from rest_client import Client, AsyncClient, HTTPError, RetryConfig, TimeoutConfig


def synchronous_example():
    """Demonstrate synchronous client usage."""
    print("=== Synchronous Client Example ===\n")

    # Using context manager (recommended)
    with Client(
        base_url="https://jsonplaceholder.typicode.com",
        headers={"User-Agent": "Python-REST-Client/0.1.0"}
    ) as client:
        try:
            # GET request
            print("Fetching user 1...")
            response = client.get("/users/1")
            user = response.json()
            print(f"User: {user['name']} ({user['email']})\n")

            # GET with query parameters
            print("Searching posts...")
            posts = client.get("/posts", params={"userId": 1}).json()
            print(f"Found {len(posts)} posts\n")

            # POST request
            print("Creating new post...")
            new_post = client.post(
                "/posts",
                json={
                    "title": "Test Post",
                    "body": "This is a test post",
                    "userId": 1
                }
            ).json()
            print(f"Created post with ID: {new_post.get('id')}\n")

            # PUT request
            print("Updating post...")
            updated = client.put(
                f"/posts/{new_post.get('id', 1)}",
                json={
                    "id": new_post.get('id', 1),
                    "title": "Updated Title",
                    "body": "Updated body",
                    "userId": 1
                }
            ).json()
            print(f"Updated post: {updated['title']}\n")

            # PATCH request
            print("Partially updating post...")
            patched = client.patch(
                f"/posts/{new_post.get('id', 1)}",
                json={"title": "Patched Title"}
            ).json()
            print(f"Patched post: {patched['title']}\n")

            # DELETE request
            print("Deleting post...")
            delete_response = client.delete(f"/posts/{new_post.get('id', 1)}")
            print(f"Delete status: {delete_response.status_code}\n")

        except HTTPError as e:
            print(f"HTTP Error: {e.status_code} - {e.message}")


async def asynchronous_example():
    """Demonstrate asynchronous client usage."""
    print("=== Asynchronous Client Example ===\n")

    async with AsyncClient(
        base_url="https://jsonplaceholder.typicode.com",
        headers={"User-Agent": "Python-REST-Client/0.1.0"}
    ) as client:
        try:
            # Single async request
            print("Fetching user 1 (async)...")
            response = await client.get("/users/1")
            user = response.json()
            print(f"User: {user['name']} ({user['email']})\n")

            # Concurrent requests
            print("Fetching multiple users concurrently...")
            tasks = [
                client.get(f"/users/{i}")
                for i in range(1, 6)
            ]
            responses = await asyncio.gather(*tasks)
            users = [r.json() for r in responses]
            print(f"Fetched {len(users)} users concurrently:")
            for u in users:
                print(f"  - {u['name']}")
            print()

        except HTTPError as e:
            print(f"HTTP Error: {e.status_code} - {e.message}")


def retry_example():
    """Demonstrate retry configuration."""
    print("=== Retry Configuration Example ===\n")

    # Configure retry behavior
    retry_config = RetryConfig(
        max_retries=3,
        retry_status_codes={408, 429, 500, 502, 503, 504},
        backoff_factor=0.5,
        max_backoff=10.0,
        jitter=True
    )

    with Client(
        base_url="https://jsonplaceholder.typicode.com",
        retry=retry_config
    ) as client:
        try:
            response = client.get("/posts/1")
            print(f"Successfully fetched post: {response.json()['title']}\n")
        except HTTPError as e:
            print(f"Failed after retries: {e}")


def timeout_example():
    """Demonstrate timeout configuration."""
    print("=== Timeout Configuration Example ===\n")

    # Configure timeouts
    timeout_config = TimeoutConfig(
        connect=5.0,
        read=10.0,
        write=10.0,
        pool=5.0
    )

    with Client(
        base_url="https://jsonplaceholder.typicode.com",
        timeout=timeout_config
    ) as client:
        try:
            response = client.get("/posts/1")
            print(f"Successfully fetched post: {response.json()['title']}\n")
        except Exception as e:
            print(f"Request failed: {e}")


def error_handling_example():
    """Demonstrate error handling."""
    print("=== Error Handling Example ===\n")

    with Client(
        base_url="https://jsonplaceholder.typicode.com",
        raise_for_status_enabled=True
    ) as client:
        try:
            # This will fail with 404
            response = client.get("/posts/999999")
            print(f"Post: {response.json()}")
        except HTTPError as e:
            print(f"Caught HTTPError: {e.status_code} - {e.message}\n")

    # Manual error handling (without exceptions)
    with Client(
        base_url="https://jsonplaceholder.typicode.com",
        raise_for_status_enabled=False
    ) as client:
        response = client.get("/posts/999999")
        if response.status_code == 200:
            print(f"Post: {response.json()}")
        elif response.status_code == 404:
            print(f"Post not found (status: {response.status_code})\n")


def main():
    """Run all examples."""
    print("Python REST Client - Usage Examples")
    print("=" * 50)
    print()

    # Synchronous examples
    synchronous_example()

    # Retry example
    retry_example()

    # Timeout example
    timeout_example()

    # Error handling example
    error_handling_example()

    # Asynchronous example
    print("Running async example...")
    asyncio.run(asynchronous_example())

    print("=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    main()

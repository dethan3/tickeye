import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio consistently for ASGI integration tests."""

    return "asyncio"

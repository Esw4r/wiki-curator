"""
pytest configuration for the wiki-curator test suite.

Sets asyncio_mode to "auto" so every async test function and fixture
is automatically treated as an asyncio coroutine without needing
the @pytest.mark.asyncio decorator on each one individually.
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio coroutine"
    )

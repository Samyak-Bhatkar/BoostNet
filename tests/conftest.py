"""BoostNet pytest fixtures.

Starts Mock CDN Server and Virtual Node Cluster for automated test runs.
"""

import asyncio
import pytest
import pytest_asyncio

from backend.config import MOCK_CDN_PORT
from backend.engine.node_manager import node_manager
from backend.simulator.mock_cdn_server import mock_cdn_server
from backend.simulator.virtual_nodes import virtual_cluster


@pytest_asyncio.fixture(autouse=True)
async def setup_test_environment():
    """Ensures Mock CDN and Virtual Node Cluster are active and reset for each test."""
    await mock_cdn_server.start()
    mock_cdn_server._ip_lock_initial_source = None
    await virtual_cluster.reset_cluster()
    yield virtual_cluster


@pytest_asyncio.fixture
async def active_cluster(setup_test_environment):
    return setup_test_environment

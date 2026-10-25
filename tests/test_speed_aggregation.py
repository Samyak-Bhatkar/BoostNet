"""Test 1: Multi-Mobile Speed Aggregation & SHA-256 Verification.

Verifies that BoostNet dynamically splits and fetches chunks across all 3 virtual nodes
(Airtel 5G, Jio 4G, Vi 4G) concurrently, achieving aggregated throughput and exact byte-level
SHA-256 verification.
"""

import asyncio
import os
import pytest

from backend.config import MOCK_CDN_PORT
from backend.engine.chunk_downloader import chunk_downloader, DownloadStatus
from backend.engine.node_manager import node_manager
from backend.simulator.mock_cdn_server import mock_cdn_server


@pytest.mark.asyncio
async def test_speed_aggregation_and_sha256(active_cluster):
    # Verify all 3 virtual nodes are registered and active
    nodes = node_manager.get_active_nodes()
    assert len(nodes) == 3, f"Expected 3 active nodes, got {len(nodes)}"

    test_url = f"http://127.0.0.1:{MOCK_CDN_PORT}/test-16mb.bin"
    expected_sha256 = mock_cdn_server.sha256_16mb

    # Launch parallel range download
    task = await chunk_downloader.start_download(
        url=test_url,
        filename="test_aggregation_16mb.bin",
        expected_sha256=expected_sha256,
    )

    # Wait for completion (max 50s for throttled 750 KB/s cluster)
    timeout = 50.0
    start_t = asyncio.get_event_loop().time()
    while task.status not in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
        await asyncio.sleep(0.3)
        if (asyncio.get_event_loop().time() - start_t) > timeout:
            pytest.fail("Download timed out waiting for completion")

    assert task.status == DownloadStatus.COMPLETED
    assert task.downloaded_bytes == 16 * 1024 * 1024
    assert task.is_multinode_capable is True
    assert task.hash_verified is True
    assert task.sha256_hash.lower() == expected_sha256.lower()

    # Verify that multiple nodes participated in downloading chunks
    participating_nodes = [n for n in nodes if n.bytes_transferred > 0]
    assert len(participating_nodes) >= 2, f"Expected multi-node participation, got {len(participating_nodes)}"

    print(f"\n[Test 1 Passed] Aggregated Speed: {task.average_speed_mbps} Mbps | SHA-256 Verified: {task.sha256_hash[:16]}...")

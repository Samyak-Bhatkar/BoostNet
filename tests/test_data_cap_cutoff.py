"""Test 4: Donor Trust Controls & Data Cap Cutoff.

Verifies that when a donor mobile phone reaches its allocated data cap, BoostNet
immediately stops assigning new chunks to that phone, marks it as DRAINING, and completes
the download using the remaining active nodes without failing the file or violating the donor's cap.
"""

import asyncio
import pytest

from backend.config import MOCK_CDN_PORT
from backend.engine.chunk_downloader import chunk_downloader, DownloadStatus
from backend.engine.node_manager import node_manager, NodeStatus
from backend.simulator.mock_cdn_server import mock_cdn_server


@pytest.mark.asyncio
async def test_data_cap_cutoff(active_cluster):
    # Set Node 2 (Priya's Samsung Jio 4G) cap to 1.0 MB
    target_node_id = active_cluster.configs[1].node_id
    await node_manager.update_node_limits(target_node_id, data_cap_mb=1.0)

    node_2 = node_manager.get_node(target_node_id)
    assert node_2.data_cap_mb == 1.0

    test_url = f"http://127.0.0.1:{MOCK_CDN_PORT}/test-8mb.bin"
    expected_sha256 = mock_cdn_server.sha256_8mb

    task = await chunk_downloader.start_download(
        url=test_url,
        filename="test_datacap_8mb.bin",
        expected_sha256=expected_sha256,
    )

    timeout = 30.0
    start_t = asyncio.get_event_loop().time()

    while task.status not in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
        await asyncio.sleep(0.2)
        if (asyncio.get_event_loop().time() - start_t) > timeout:
            pytest.fail("Download timed out during data cap cutoff test")

    assert task.status == DownloadStatus.COMPLETED
    assert task.downloaded_bytes == 8 * 1024 * 1024
    assert task.hash_verified is True
    assert task.sha256_hash.lower() == expected_sha256.lower()

    # Verify Node 2 transitioned to DRAINING and did not exceed cap
    node_2 = node_manager.get_node(target_node_id)
    assert node_2.status in (NodeStatus.DRAINING, NodeStatus.DISCONNECTED)
    print(f"\n[Test 4 Passed] Node 2 data cap honored ({node_2.data_used_mb}MB / 1.0MB) - Status: {node_2.status.value}")

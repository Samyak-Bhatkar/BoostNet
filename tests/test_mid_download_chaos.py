"""Test 2: Mid-Download Chaos & Fault Tolerance.

Verifies that if a mobile phone node disconnects or dies abruptly mid-download (e.g. at ~30%),
BoostNet's aria2-style work-stealing scheduler automatically catches the cancellation,
requeues the in-flight byte range, reallocates it to surviving nodes, and finishes the file
with zero data corruption (byte-exact SHA-256 match).
"""

import asyncio
import os
import pytest

from backend.config import MOCK_CDN_PORT
from backend.engine.chunk_downloader import chunk_downloader, DownloadStatus
from backend.engine.node_manager import node_manager, NodeStatus
from backend.simulator.mock_cdn_server import mock_cdn_server


@pytest.mark.asyncio
async def test_mid_download_chaos_fault_tolerance(active_cluster):
    test_url = f"http://127.0.0.1:{MOCK_CDN_PORT}/test-16mb.bin"
    expected_sha256 = mock_cdn_server.sha256_16mb

    task = await chunk_downloader.start_download(
        url=test_url,
        filename="test_chaos_16mb.bin",
        expected_sha256=expected_sha256,
    )

    # Monitor progress and trigger chaos kill on Node 3 (Aman's Vivo) when download is at ~30%
    killed = False
    target_node_id = active_cluster.configs[2].node_id # Vi 4G node

    timeout = 55.0
    start_t = asyncio.get_event_loop().time()

    while task.status not in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
        await asyncio.sleep(0.15)

        if not killed and task.downloaded_bytes > (4 * 1024 * 1024):
            print(f"\n[CHAOS TRIGGER] Killing node {target_node_id} at {task.progress_pct}% progress!")
            await active_cluster.kill_node(target_node_id)
            killed = True

        if (asyncio.get_event_loop().time() - start_t) > timeout:
            pytest.fail("Download timed out during chaos recovery test")

    assert task.status == DownloadStatus.COMPLETED
    assert task.downloaded_bytes == 16 * 1024 * 1024
    assert task.hash_verified is True
    assert task.sha256_hash.lower() == expected_sha256.lower()

    # Verify target node was indeed disconnected
    killed_node = node_manager.get_node(target_node_id)
    assert killed_node.status == NodeStatus.DISCONNECTED

    print(f"\n[Test 2 Passed] Chaos survived! File verified with SHA-256: {task.sha256_hash[:16]}...")

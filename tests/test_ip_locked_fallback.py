"""Test 3: IP-Locked Signed URL Fallback (Preflight Probe).

Verifies that when a strict upstream server binds a download token to a single IP address
(returning 403 Forbidden on secondary phone nodes), BoostNet's Preflight Multi-IP Probe
detects the restriction before splitting and automatically falls back to a Single-Node
Pinned Stream, preventing corrupted files and failed transfers.
"""

import asyncio
import aiohttp
import pytest

from backend.config import MOCK_CDN_PORT
from backend.engine.chunk_downloader import chunk_downloader, DownloadStatus
from backend.simulator.mock_cdn_server import mock_cdn_server


@pytest.mark.asyncio
async def test_ip_locked_fallback(active_cluster):
    # Reset mock CDN IP lock state
    async with aiohttp.ClientSession() as session:
        await session.post(f"http://127.0.0.1:{MOCK_CDN_PORT}/api/reset-ip-lock")

    test_url = f"http://127.0.0.1:{MOCK_CDN_PORT}/signed-ip-locked.bin"
    expected_sha256 = mock_cdn_server._ip_lock_sha256

    task = await chunk_downloader.start_download(
        url=test_url,
        filename="test_ip_locked.bin",
        expected_sha256=expected_sha256,
    )

    timeout = 35.0
    start_t = asyncio.get_event_loop().time()

    while task.status not in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
        await asyncio.sleep(0.2)
        if (asyncio.get_event_loop().time() - start_t) > timeout:
            pytest.fail("Download timed out during IP-locked fallback test")

    assert task.status == DownloadStatus.COMPLETED
    assert task.is_multinode_capable is False, "Expected fallback to single-node pinned stream"
    assert task.pinned_node_id is not None
    assert task.downloaded_bytes == len(mock_cdn_server._ip_lock_payload)
    assert task.hash_verified is True
    assert task.sha256_hash.lower() == expected_sha256.lower()

    print(f"\n[Test 3 Passed] Cleanly fell back to pinned node {task.pinned_node_id}! SHA-256 Verified.")

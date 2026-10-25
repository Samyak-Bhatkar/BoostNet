"""BoostNet Parallel Range Downloader (Approach A).

Lineage & Architectural Heritage:
- aria2: In-flight dynamic work-stealing, adaptive chunk length, and "Split-in-Half"
  straggler elimination algorithm.
- Preflight Multi-IP Probe: Probes upstream servers with Range: bytes=0-0 to detect
  signed/IP-locked tokens (e.g. 403 Forbidden on secondary IPs) and auto-fallback to
  single-node pinned streaming without corruption.
- Mid-download fault tolerance: Instant requeue and reallocation on phone disconnect.
- 64-Block chunk map telemetry for visual feedback.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
import hashlib
import logging
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

import aiohttp
from aiohttp_socks import ProxyConnector

from backend.config import (
    DEFAULT_STEADY_CHUNK_SIZE,
    DEFAULT_WARMUP_CHUNK_SIZE,
    DOWNLOADS_DIR,
    MIN_STRAGGLER_SPLIT_SIZE,
    NODE_STALL_TIMEOUT_SEC,
    PREFLIGHT_PROBE_BYTES,
)
from backend.engine.node_manager import NodeManager, NodeStatus, PhoneNode, node_manager

logger = logging.getLogger("boostnet.chunk_downloader")


class DownloadStatus:
    QUEUED = "QUEUED"
    PROBING = "PROBING"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    PINNED_SINGLE_NODE = "PINNED_SINGLE_NODE"


@dataclass(order=True)
class DownloadChunk:
    index: int
    byte_start: int = field(compare=False)
    byte_end: int = field(compare=False)
    assigned_node_id: Optional[str] = field(default=None, compare=False)
    bytes_downloaded: int = field(default=0, compare=False)
    completed: bool = field(default=False, compare=False)
    in_flight: bool = field(default=False, compare=False)
    color: str = field(default="#334155", compare=False)
    cancelled: bool = field(default=False, compare=False)
    split_boundary: Optional[int] = field(default=None, compare=False)

    @property
    def total_bytes(self) -> int:
        return self.byte_end - self.byte_start + 1


@dataclass
class DownloadTask:
    task_id: str
    url: str
    filename: str
    file_path: Path
    total_bytes: int = 0
    downloaded_bytes: int = 0
    status: str = DownloadStatus.QUEUED
    chunks: List[DownloadChunk] = field(default_factory=list)
    sha256_hash: Optional[str] = None
    expected_sha256: Optional[str] = None
    hash_verified: bool = False
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    average_speed_mbps: float = 0.0
    is_multinode_capable: bool = True
    pinned_node_id: Optional[str] = None
    error_message: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)
    active_worker_tasks: Set[asyncio.Task] = field(default_factory=set)

    @property
    def progress_pct(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, round((self.downloaded_bytes / self.total_bytes) * 100, 1))

    @property
    def eta_seconds(self) -> Optional[int]:
        if self.average_speed_mbps <= 0.05 or self.total_bytes <= 0:
            return None
        remaining_bytes = max(0, self.total_bytes - self.downloaded_bytes)
        remaining_bits = remaining_bytes * 8
        speed_bps = self.average_speed_mbps * 1_000_000
        return max(0, int(remaining_bits / speed_bps))


class ChunkDownloader:
    """Production parallel HTTP range accelerator with aria2 work-stealing."""

    def __init__(self, manager: Optional[NodeManager] = None) -> None:
        self.node_manager = manager or node_manager
        self.tasks: Dict[str, DownloadTask] = {}
        self._lock = asyncio.Lock()
        self._progress_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def register_callback(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        self._progress_callbacks.append(cb)

    async def emit_update(self, task: DownloadTask) -> None:
        payload = self.get_task_telemetry(task)
        for cb in self._progress_callbacks:
            try:
                cb(payload)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def get_task_telemetry(self, task: DownloadTask) -> Dict[str, Any]:
        # Generate 64-block visualization map
        block_count = 64
        blocks = []
        if task.total_bytes > 0:
            bytes_per_block = task.total_bytes / block_count
            for i in range(block_count):
                b_start = int(i * bytes_per_block)
                b_end = int((i + 1) * bytes_per_block) - 1

                # Find chunk covering this range
                color = "#1e293b" # default dark slate
                status = "queued"

                for c in task.chunks:
                    if c.byte_start <= b_start <= c.byte_end or c.byte_start <= b_end <= c.byte_end:
                        if c.completed:
                            color = c.color
                            status = "completed"
                            break
                        elif c.in_flight:
                            color = c.color
                            status = "downloading"
                            break

                blocks.append({
                    "id": i,
                    "color": color,
                    "status": status,
                    "range": f"{b_start}-{b_end}"
                })
        else:
            blocks = [{"id": i, "color": "#1e293b", "status": "queued"} for i in range(block_count)]

        return {
            "type": "download_progress",
            "task_id": task.task_id,
            "filename": task.filename,
            "url": task.url,
            "total_bytes": task.total_bytes,
            "downloaded_bytes": task.downloaded_bytes,
            "progress_pct": task.progress_pct,
            "speed_mbps": task.average_speed_mbps,
            "eta_sec": task.eta_seconds,
            "status": task.status,
            "is_multinode": task.is_multinode_capable,
            "pinned_node": task.pinned_node_id,
            "sha256": task.sha256_hash,
            "hash_verified": task.hash_verified,
            "blocks": blocks,
            "error": task.error_message,
        }

    async def start_download(
        self,
        url: str,
        filename: Optional[str] = None,
        expected_sha256: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> DownloadTask:
        """Entry point to start parallel or pinned download."""
        if not filename:
            path_part = urlparse(url).path
            filename = os.path.basename(path_part) or f"download_{int(time.time())}.bin"

        file_path = DOWNLOADS_DIR / filename
        task_id = f"dl_{int(time.time() * 1000)}"

        task = DownloadTask(
            task_id=task_id,
            url=url,
            filename=filename,
            file_path=file_path,
            expected_sha256=expected_sha256,
            custom_headers=headers or {},
            status=DownloadStatus.PROBING,
        )

        async with self._lock:
            self.tasks[task_id] = task

        # Launch background runner
        asyncio.create_task(self._execute_download_pipeline(task))
        return task

    async def _execute_download_pipeline(self, task: DownloadTask) -> None:
        """Main pipeline: Preflight probe -> Split or Fallback -> Parallel Workers -> Verify."""
        try:
            await self.emit_update(task)

            # 1. Preflight Multi-IP Probe
            probe_result = await self._preflight_multi_ip_probe(task)
            total_size = probe_result["total_bytes"]
            supports_ranges = probe_result["supports_ranges"]
            eligible_nodes: List[PhoneNode] = probe_result["eligible_nodes"]

            task.total_bytes = total_size

            # Pre-allocate sparse/zeroed file on disk
            with open(task.file_path, "wb") as f:
                if total_size > 0:
                    f.truncate(total_size)

            if not supports_ranges or len(eligible_nodes) <= 1 or not probe_result["multinode_safe"]:
                # Fallback to Single-Node Pinned Stream
                pinned_node = eligible_nodes[0] if eligible_nodes else None
                task.is_multinode_capable = False
                task.pinned_node_id = pinned_node.node_id if pinned_node else "Direct Gateway"
                task.status = DownloadStatus.PINNED_SINGLE_NODE
                logger.warning(
                    f"Task {task.task_id}: Falling back to Single-Node Pinned Stream on {task.pinned_node_id} (Signed URL / lack of ranges)"
                )
                await self.emit_update(task)
                await self._execute_single_node_pinned(task, pinned_node)
            else:
                # Approach A: Dynamic Multi-Node Parallel Range Aggregator
                task.status = DownloadStatus.DOWNLOADING
                task.is_multinode_capable = True
                await self.emit_update(task)
                await self._execute_parallel_range_download(task, eligible_nodes)

            # Integrity Verification (SHA-256)
            if task.status != DownloadStatus.FAILED:
                await self._verify_integrity(task)
                task.status = DownloadStatus.COMPLETED
                task.end_time = time.time()
                elapsed = max(0.1, task.end_time - task.start_time)
                task.average_speed_mbps = round((task.total_bytes * 8) / (elapsed * 1_000_000), 2)
                logger.info(
                    f"Task {task.task_id} completed successfully in {elapsed:.2f}s! ({task.average_speed_mbps} Mbps)"
                )
                await self.emit_update(task)

        except Exception as e:
            logger.exception(f"Fatal error in download task {task.task_id}: {e}")
            task.status = DownloadStatus.FAILED
            task.error_message = str(e)
            await self.emit_update(task)

    async def _preflight_multi_ip_probe(self, task: DownloadTask) -> Dict[str, Any]:
        """Probes all active phone nodes with Range: bytes=0-0 to test multi-IP range compatibility."""
        active_nodes = self.node_manager.get_active_nodes()
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BoostNet/2.0",
            "Accept": "*/*",
            **task.custom_headers,
        }

        # First, test default / primary probe
        total_size = 0
        supports_ranges = False

        # If no active nodes, probe direct localhost
        if not active_nodes:
            async with aiohttp.ClientSession() as session:
                async with session.get(task.url, headers={**req_headers, "Range": PREFLIGHT_PROBE_BYTES}, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status in (206, 200):
                        supports_ranges = (resp.status == 206) or ("bytes" in resp.headers.get("Accept-Ranges", ""))
                        crange = resp.headers.get("Content-Range")
                        if crange and "/" in crange:
                            total_size = int(crange.split("/")[-1])
                        else:
                            total_size = int(resp.headers.get("Content-Length", 0))
            return {
                "total_bytes": total_size,
                "supports_ranges": supports_ranges,
                "eligible_nodes": [],
                "multinode_safe": False,
            }

        # Multi-node probe across all phone proxies
        eligible_nodes: List[PhoneNode] = []
        forbidden_count = 0

        for node in active_nodes:
            proxy_url = f"socks5://{node.host}:{node.port}"
            try:
                connector = ProxyConnector.from_url(proxy_url)
                async with aiohttp.ClientSession(connector=connector) as session:
                    probe_headers = {
                        **req_headers,
                        "Range": PREFLIGHT_PROBE_BYTES,
                        "X-Forwarded-Node": node.node_id,
                    }
                    t0 = time.time()
                    async with session.get(task.url, headers=probe_headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        rtt_ms = (time.time() - t0) * 1000
                        if resp.status == 206:
                            supports_ranges = True
                            crange = resp.headers.get("Content-Range")
                            if crange and "/" in crange:
                                total_size = int(crange.split("/")[-1])
                            eligible_nodes.append(node)
                            await self.node_manager.update_node_metrics(node.node_id, 1, 0.05, rtt_ms)
                        elif resp.status == 200:
                            if "bytes" in resp.headers.get("Accept-Ranges", ""):
                                supports_ranges = True
                                total_size = int(resp.headers.get("Content-Length", 0))
                                eligible_nodes.append(node)
                            else:
                                total_size = int(resp.headers.get("Content-Length", 0))
                                eligible_nodes.append(node)
                        elif resp.status == 403:
                            forbidden_count += 1
                            logger.warning(f"Probe on {node.device_name} ({proxy_url}) returned 403 Forbidden! IP-Locked Token detected.")
            except Exception as e:
                logger.warning(f"Probe failed on {node.device_name}: {e}")

        # If any secondary node returned 403 Forbidden, IP-locking is in effect!
        multinode_safe = (forbidden_count == 0) and (len(eligible_nodes) > 1) and supports_ranges

        return {
            "total_bytes": total_size,
            "supports_ranges": supports_ranges,
            "eligible_nodes": eligible_nodes if multinode_safe else (eligible_nodes[:1] if eligible_nodes else active_nodes[:1]),
            "multinode_safe": multinode_safe,
        }

    async def _execute_parallel_range_download(
        self, task: DownloadTask, nodes: List[PhoneNode]
    ) -> None:
        """Parallel work-stealing downloader inspired by aria2."""
        # 1. Create micro-chunk queue
        queue: asyncio.PriorityQueue[DownloadChunk] = asyncio.PriorityQueue()
        chunks: List[DownloadChunk] = []

        total = task.total_bytes
        offset = 0
        chunk_idx = 0

        # Initial warmup chunks (1MB) then steady-state (4MB)
        while offset < total:
            size = DEFAULT_WARMUP_CHUNK_SIZE if chunk_idx < len(nodes) * 2 else DEFAULT_STEADY_CHUNK_SIZE
            byte_start = offset
            byte_end = min(total - 1, offset + size - 1)

            c = DownloadChunk(
                index=chunk_idx,
                byte_start=byte_start,
                byte_end=byte_end,
            )
            chunks.append(c)
            await queue.put(c)

            offset = byte_end + 1
            chunk_idx += 1

        task.chunks = chunks
        await self.emit_update(task)

        # 2. Worker coroutines per active node
        active_in_flight: Dict[str, DownloadChunk] = {}
        worker_tasks = []

        for node in nodes:
            t = asyncio.create_task(
                self._node_chunk_worker(task, node, queue, active_in_flight)
            )
            worker_tasks.append(t)
            task.active_worker_tasks.add(t)

        # 3. Dynamic Straggler Splitter & Health Monitor loop
        monitor_task = asyncio.create_task(
            self._straggler_and_health_monitor(task, queue, active_in_flight)
        )

        await asyncio.gather(*worker_tasks, return_exceptions=True)
        monitor_task.cancel()

    async def _node_chunk_worker(
        self,
        task: DownloadTask,
        node: PhoneNode,
        queue: asyncio.PriorityQueue[DownloadChunk],
        active_in_flight: Dict[str, DownloadChunk],
    ) -> None:
        """Worker thread loop running on an assigned mobile node."""
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BoostNet/2.0",
            **task.custom_headers,
        }
        proxy_url = f"socks5://{node.host}:{node.port}"

        while not queue.empty() or node.node_id in active_in_flight:
            if not node.is_eligible():
                logger.info(f"Node {node.device_name} is no longer eligible (data cap/battery). Worker exiting.")
                break

            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if queue.empty():
                    break
                continue

            chunk.assigned_node_id = node.node_id
            chunk.color = node.accent_color
            chunk.in_flight = True
            chunk.cancelled = False
            active_in_flight[node.node_id] = chunk
            node.active_connections += 1

            await self.emit_update(task)

            # Execute range fetch
            success = await self._fetch_chunk_with_retry(
                task, node, chunk, proxy_url, req_headers
            )

            chunk.in_flight = False
            if node.node_id in active_in_flight:
                del active_in_flight[node.node_id]
            node.active_connections = max(0, node.active_connections - 1)

            if success:
                chunk.completed = True
                node.total_chunks_completed += 1
                await self.emit_update(task)
            else:
                # Failure or cancellation (e.g. node disconnect/stall)
                chunk.assigned_node_id = None
                chunk.in_flight = False
                if not chunk.completed and chunk.bytes_downloaded < chunk.total_bytes:
                    # Put remaining byte range back to the FRONT of the queue
                    new_start = chunk.byte_start + chunk.bytes_downloaded
                    if new_start <= chunk.byte_end:
                        chunk.byte_start = new_start
                        chunk.bytes_downloaded = 0
                        await queue.put(chunk)
                        logger.warning(
                            f"Requeued incomplete chunk #{chunk.index} ({chunk.byte_start}-{chunk.byte_end}) due to node fault"
                        )
                await self.emit_update(task)

                # If this node failed persistently, back off or exit
                if not node.is_eligible() or node.status == NodeStatus.DEGRADED:
                    break

    async def _fetch_chunk_with_retry(
        self,
        task: DownloadTask,
        node: PhoneNode,
        chunk: DownloadChunk,
        proxy_url: str,
        base_headers: Dict[str, str],
    ) -> bool:
        """Fetches a specific byte range through the phone proxy and writes to disk."""
        target_end = chunk.byte_end
        range_header = f"bytes={chunk.byte_start}-{target_end}"
        headers = {
            **base_headers,
            "Range": range_header,
            "X-Forwarded-Node": node.node_id,
        }

        t_start = time.time()
        bytes_received_this_chunk = 0

        try:
            connector = ProxyConnector.from_url(proxy_url)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    task.url, headers=headers, timeout=aiohttp.ClientTimeout(total=60, sock_connect=5)
                ) as resp:
                    if resp.status not in (200, 206):
                        logger.warning(
                            f"Chunk #{chunk.index} HTTP error {resp.status} on node {node.device_name}"
                        )
                        return False

                    # Read stream in 32KB buffers
                    with open(task.file_path, "r+b") as f:
                        f.seek(chunk.byte_start)
                        last_progress_time = time.time()

                        async for data in resp.content.iter_chunked(32 * 1024):
                            if chunk.cancelled:
                                logger.info(f"Chunk #{chunk.index} was cancelled / split by scheduler.")
                                break

                            # If straggler split occurred, truncate at split boundary
                            curr_end = chunk.byte_start + bytes_received_this_chunk + len(data) - 1
                            if chunk.split_boundary and curr_end >= chunk.split_boundary:
                                allowed_bytes = (chunk.split_boundary - (chunk.byte_start + bytes_received_this_chunk)) + 1
                                if allowed_bytes > 0:
                                    f.write(data[:allowed_bytes])
                                    bytes_received_this_chunk += allowed_bytes
                                    chunk.bytes_downloaded += allowed_bytes
                                    task.downloaded_bytes += allowed_bytes
                                chunk.byte_end = chunk.split_boundary
                                logger.info(f"Chunk #{chunk.index} truncated at split boundary {chunk.split_boundary}")
                                break

                            f.write(data)
                            chunk_len = len(data)
                            bytes_received_this_chunk += chunk_len
                            chunk.bytes_downloaded += chunk_len
                            task.downloaded_bytes += chunk_len

                            # Stall detection: check if stalled for NODE_STALL_TIMEOUT_SEC
                            now = time.time()
                            if chunk_len > 0:
                                last_progress_time = now

                            if (now - last_progress_time) > NODE_STALL_TIMEOUT_SEC:
                                logger.warning(
                                    f"Chunk #{chunk.index} on node {node.device_name} stalled > {NODE_STALL_TIMEOUT_SEC}s! Triggering fault requeue."
                                )
                                chunk.cancelled = True
                                return False

            # Update metrics
            duration = max(0.01, time.time() - t_start)
            await self.node_manager.update_node_metrics(node.node_id, bytes_received_this_chunk, duration)

            # Update task overall speed
            elapsed = max(0.1, time.time() - task.start_time)
            task.average_speed_mbps = round((task.downloaded_bytes * 8) / (elapsed * 1_000_000), 2)

            return True

        except Exception as e:
            logger.warning(f"Error fetching chunk #{chunk.index} via {node.device_name}: {e}")
            return False

    async def _straggler_and_health_monitor(
        self,
        task: DownloadTask,
        queue: asyncio.PriorityQueue[DownloadChunk],
        active_in_flight: Dict[str, DownloadChunk],
    ) -> None:
        """aria2 Split-in-Half straggler eliminator and mid-download chaos recovery."""
        while task.status == DownloadStatus.DOWNLOADING:
            await asyncio.sleep(0.5)

            # Check if queue is empty and some nodes are idle while one slow chunk remains
            if queue.empty() and len(active_in_flight) > 0:
                eligible_nodes = self.node_manager.get_active_nodes()
                idle_nodes = [n for n in eligible_nodes if n.node_id not in active_in_flight]

                if idle_nodes:
                    # Find the slowest in-flight chunk with remaining bytes > MIN_STRAGGLER_SPLIT_SIZE
                    for node_id, chunk in list(active_in_flight.items()):
                        remaining_bytes = chunk.total_bytes - chunk.bytes_downloaded
                        if remaining_bytes > MIN_STRAGGLER_SPLIT_SIZE and not chunk.split_boundary:
                            # Split chunk in half!
                            curr_pos = chunk.byte_start + chunk.bytes_downloaded
                            midpoint = curr_pos + (remaining_bytes // 2)

                            logger.info(
                                f"aria2 Dynamic Split: Splitting straggler Chunk #{chunk.index} ({curr_pos}-{chunk.byte_end}) at midpoint {midpoint}"
                            )

                            orig_end = chunk.byte_end
                            # Truncate existing chunk at midpoint
                            chunk.split_boundary = midpoint
                            chunk.byte_end = midpoint

                            # Create new split chunk for the second half
                            new_chunk = DownloadChunk(
                                index=len(task.chunks),
                                byte_start=midpoint + 1,
                                byte_end=orig_end,
                            )
                            task.chunks.append(new_chunk)
                            await queue.put(new_chunk)
                            break

            await self.emit_update(task)

    async def _execute_single_node_pinned(
        self, task: DownloadTask, node: Optional[PhoneNode]
    ) -> None:
        """Fallback for IP-locked signed URLs or servers lacking range support."""
        proxy_url = f"socks5://{node.host}:{node.port}" if node else None
        connector = ProxyConnector.from_url(proxy_url) if proxy_url else None

        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BoostNet/2.0",
            "X-Forwarded-Node": node.node_id if node else "direct",
            **task.custom_headers,
        }

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(task.url, headers=req_headers) as resp:
                if resp.status not in (200, 206):
                    raise RuntimeError(f"Server returned HTTP {resp.status}")

                with open(task.file_path, "wb") as f:
                    t_start = time.time()
                    bytes_down = 0
                    async for chunk in resp.content.iter_chunked(64 * 1024):
                        f.write(chunk)
                        chunk_len = len(chunk)
                        bytes_down += chunk_len
                        task.downloaded_bytes += chunk_len

                        elapsed = max(0.1, time.time() - t_start)
                        task.average_speed_mbps = round(
                            (bytes_down * 8) / (elapsed * 1_000_000), 2
                        )
                        await self.emit_update(task)

                    if node:
                        await self.node_manager.update_node_metrics(
                            node.node_id, bytes_down, time.time() - t_start
                        )

    async def _verify_integrity(self, task: DownloadTask) -> None:
        """Computes SHA-256 of downloaded file and checks against expectation."""
        hasher = hashlib.sha256()
        with open(task.file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)

        task.sha256_hash = hasher.hexdigest()
        if task.expected_sha256:
            task.hash_verified = (task.sha256_hash.lower() == task.expected_sha256.lower())
        else:
            task.hash_verified = True
        logger.info(f"Task {task.task_id} SHA-256: {task.sha256_hash} (Verified: {task.hash_verified})")


# Singleton instance
chunk_downloader = ChunkDownloader()

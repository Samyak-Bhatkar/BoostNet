"""BoostNet Video & Media Stream Look-Ahead Proxy.

Lineage & Architectural Heritage:
- Solves the YouTube / streaming single-connection bottleneck where Chrome multiplexes
  video chunks over 1 TCP connection.
- Integrates yt-dlp stream extraction + Multi-Phone Sliding Window Ring Buffer.
- Prefetches upcoming 1 MB byte-range segments across all connected mobile phone nodes
  in parallel and pipes a continuous stream to the browser's <video> player or VLC/MPV.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
import logging
import time
from typing import AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from aiohttp_socks import ProxyConnector

from backend.engine.node_manager import NodeManager, PhoneNode, node_manager

logger = logging.getLogger("boostnet.stream_accelerator")


@dataclass
class StreamSegment:
    index: int
    byte_start: int
    byte_end: int
    data: Optional[bytes] = None
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    node_id: Optional[str] = None
    accent_color: str = "#38bdf8"


class StreamAccelerator:
    """Multi-phone look-ahead prefetch engine for media streams."""

    def __init__(self, manager: Optional[NodeManager] = None) -> None:
        self.node_manager = manager or node_manager
        self.segment_size = 1024 * 1024 # 1 MB look-ahead segments
        self.buffer_window_size = 4      # Prefetch 4 segments ahead in parallel

    async def resolve_media_url(self, raw_url: str) -> Dict[str, Any]:
        """Resolves direct stream URL using yt-dlp or direct inspection."""
        is_youtube = any(k in raw_url for k in ("youtube.com", "youtu.be", "googlevideo.com"))

        if is_youtube:
            try:
                import yt_dlp
                ydl_opts = {
                    "format": "best[ext=mp4]/best",
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                }
                loop = asyncio.get_event_loop()
                def extract():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(raw_url, download=False)
                info = await loop.run_in_executor(None, extract)
                direct_url = info.get("url") or raw_url
                title = info.get("title", "Video Stream")
                return {"direct_url": direct_url, "title": title}
            except Exception as e:
                logger.warning(f"yt-dlp extraction failed for {raw_url}: {e}. Trying direct URL.")

        return {"direct_url": raw_url, "title": "Media Stream"}

    async def stream_media_generator(
        self, direct_url: str, start_byte: int = 0
    ) -> AsyncGenerator[bytes, None]:
        """Asynchronous generator yielding 1MB segments prefetched across multiple phones."""
        active_nodes = self.node_manager.get_active_nodes()

        # Probe Content-Length
        total_size = 0
        async with aiohttp.ClientSession() as session:
            try:
                async with session.head(direct_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    total_size = int(resp.headers.get("Content-Length", 0))
            except Exception:
                pass

        if total_size <= 0:
            # Fallback direct streaming if Content-Length unknown
            async with aiohttp.ClientSession() as session:
                async with session.get(direct_url) as resp:
                    async for chunk in resp.content.iter_chunked(64 * 1024):
                        yield chunk
            return

        # Multi-phone segment look-ahead buffer
        current_offset = start_byte
        seg_idx = 0
        buffer_queue: Dict[int, StreamSegment] = {}

        while current_offset < total_size:
            # Maintain sliding window of prefetched segments
            while len(buffer_queue) < self.buffer_window_size and (current_offset + len(buffer_queue) * self.segment_size) < total_size:
                idx = seg_idx + len(buffer_queue)
                b_start = current_offset + (len(buffer_queue) * self.segment_size)
                b_end = min(total_size - 1, b_start + self.segment_size - 1)

                seg = StreamSegment(index=idx, byte_start=b_start, byte_end=b_end)
                buffer_queue[idx] = seg

                # Pick next node
                node = self.node_manager.select_next_node_weighted() if active_nodes else None
                asyncio.create_task(self._fetch_segment(direct_url, seg, node))

            # Pop next sequential segment in order
            next_seg = buffer_queue.get(seg_idx)
            if next_seg:
                await next_seg.ready.wait()
                if next_seg.data:
                    yield next_seg.data
                del buffer_queue[seg_idx]

                current_offset = next_seg.byte_end + 1
                seg_idx += 1
            else:
                break

    async def _fetch_segment(
        self, url: str, seg: StreamSegment, node: Optional[PhoneNode]
    ) -> None:
        """Fetches a single 1MB media segment via specified phone node proxy."""
        proxy_url = f"socks5://{node.host}:{node.port}" if node else None
        connector = ProxyConnector.from_url(proxy_url) if proxy_url else None
        headers = {"Range": f"bytes={seg.byte_start}-{seg.byte_end}"}

        t0 = time.time()
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    seg.data = await resp.read()
                    duration = max(0.01, time.time() - t0)
                    if node:
                        seg.node_id = node.node_id
                        seg.accent_color = node.accent_color
                        await self.node_manager.update_node_metrics(
                            node.node_id, len(seg.data), duration
                        )
        except Exception as e:
            logger.warning(f"Segment #{seg.index} prefetch failed via {node.device_name if node else 'direct'}: {e}")
            # Retry direct
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as resp:
                        seg.data = await resp.read()
            except Exception:
                pass
        finally:
            seg.ready.set()


# Singleton instance
stream_accelerator = StreamAccelerator()

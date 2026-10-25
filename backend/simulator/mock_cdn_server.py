"""BoostNet Mock CDN Test Server.

Serves deterministic test payloads with full Accept-Ranges / Content-Range support,
and includes an IP-locked /signed-ip-locked.bin endpoint to verify the Preflight
Multi-IP Probe fallback mechanism.
"""

from __future__ import annotations
import asyncio
import hashlib
import logging
import math
from typing import Dict, Optional
from aiohttp import web

from backend.config import MOCK_CDN_HOST, MOCK_CDN_PORT

logger = logging.getLogger("boostnet.mock_cdn")


def generate_deterministic_payload(size_bytes: int, seed: int = 42) -> bytes:
    """Generates deterministic pseudo-random bytes with high entropy."""
    # Pattern block of 64KB repeated
    block_size = 65536
    block = bytearray(block_size)
    val = seed
    for i in range(block_size):
        val = (val * 1103515245 + 12345) & 0x7FFFFFFF
        block[i] = val & 0xFF

    full_blocks = size_bytes // block_size
    remainder = size_bytes % block_size

    data = bytes(block) * full_blocks + bytes(block[:remainder])
    return data


class MockCDNServer:
    """Local HTTP CDN server providing deterministic test assets."""

    def __init__(self, host: str = MOCK_CDN_HOST, port: int = MOCK_CDN_PORT) -> None:
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        # Pre-generate deterministic payloads and their SHA-256 hashes
        logger.info("Pre-generating Mock CDN test payloads...")
        self.payload_8mb = generate_deterministic_payload(8 * 1024 * 1024, seed=55)
        self.sha256_8mb = hashlib.sha256(self.payload_8mb).hexdigest()

        self.payload_16mb = generate_deterministic_payload(16 * 1024 * 1024, seed=101)
        self.sha256_16mb = hashlib.sha256(self.payload_16mb).hexdigest()

        self.payload_32mb = generate_deterministic_payload(32 * 1024 * 1024, seed=202)
        self.sha256_32mb = hashlib.sha256(self.payload_32mb).hexdigest()

        self.payload_64mb = generate_deterministic_payload(64 * 1024 * 1024, seed=303)
        self.sha256_64mb = hashlib.sha256(self.payload_64mb).hexdigest()

        # IP-locked signed URL tracking
        self._ip_lock_initial_source: Optional[str] = None
        self._ip_lock_payload = self.payload_8mb
        self._ip_lock_sha256 = self.sha256_8mb

        self._setup_routes()

    def _setup_routes(self) -> None:
        self.app.router.add_get("/test-8mb.bin", self._handle_8mb)
        self.app.router.add_get("/test-16mb.bin", self._handle_16mb)
        self.app.router.add_get("/test-32mb.bin", self._handle_32mb)
        self.app.router.add_get("/test-64mb.bin", self._handle_64mb)
        self.app.router.add_get("/signed-ip-locked.bin", self._handle_ip_locked)
        self.app.router.add_post("/api/reset-ip-lock", self._reset_ip_lock)
        self.app.router.add_get("/api/hashes", self._get_hashes)

    async def _handle_8mb(self, request: web.Request) -> web.StreamResponse:
        return await self._handle_payload(request, self.payload_8mb)

    async def _handle_payload(self, request: web.Request, payload: bytes) -> web.StreamResponse:
        total_len = len(payload)
        range_header = request.headers.get("Range")

        headers = {
            "Content-Type": "application/octet-stream",
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }

        if request.method == "HEAD":
            headers["Content-Length"] = str(total_len)
            return web.Response(headers=headers)

        if not range_header or not range_header.startswith("bytes="):
            headers["Content-Length"] = str(total_len)
            resp = web.Response(body=payload, headers=headers)
            return resp

        # Parse range header
        try:
            ranges = range_header.replace("bytes=", "").split("-")
            start = int(ranges[0])
            end = int(ranges[1]) if ranges[1] else total_len - 1
            end = min(end, total_len - 1)
        except Exception:
            return web.Response(status=416, headers={"Content-Range": f"bytes */{total_len}"})

        chunk_len = end - start + 1
        headers["Content-Range"] = f"bytes {start}-{end}/{total_len}"
        headers["Content-Length"] = str(chunk_len)

        resp = web.Response(
            body=payload[start : end + 1],
            status=206,
            headers=headers,
        )
        return resp

    async def _handle_16mb(self, request: web.Request) -> web.StreamResponse:
        return await self._handle_payload(request, self.payload_16mb)

    async def _handle_32mb(self, request: web.Request) -> web.StreamResponse:
        return await self._handle_payload(request, self.payload_32mb)

    async def _handle_64mb(self, request: web.Request) -> web.StreamResponse:
        return await self._handle_payload(request, self.payload_64mb)

    async def _handle_ip_locked(self, request: web.Request) -> web.StreamResponse:
        """Endpoint that rejects requests from a second distinct proxy node."""
        client_remote = request.remote or "unknown"
        source_id = request.headers.get("X-Forwarded-Node") or client_remote

        if self._ip_lock_initial_source is None:
            self._ip_lock_initial_source = source_id
            logger.info(f"Signed URL token locked to initial connection: {source_id}")
        elif self._ip_lock_initial_source != source_id:
            # Different proxy node -> 403 Forbidden!
            logger.warning(
                f"IP-Locked download rejected request from secondary node: {source_id} (Locked to: {self._ip_lock_initial_source})"
            )
            return web.Response(
                status=403,
                text="403 Forbidden: Signed Token locked to initial client IP",
                content_type="text/plain",
            )

        return await self._handle_payload(request, self._ip_lock_payload)

    async def _reset_ip_lock(self, request: web.Request) -> web.Response:
        self._ip_lock_initial_source = None
        return web.json_response({"status": "ip_lock_reset"})

    async def _get_hashes(self, request: web.Request) -> web.Response:
        return web.json_response({
            "sha256_16mb": self.sha256_16mb,
            "sha256_32mb": self.sha256_32mb,
            "sha256_64mb": self.sha256_64mb,
            "sha256_ip_locked": self._ip_lock_sha256,
        })

    async def start(self) -> None:
        if self.site is not None:
            return
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port, reuse_address=True)
        await self.site.start()
        logger.info(f"BoostNet Mock CDN Server listening at http://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self.site:
            await self.site.stop()
            self.site = None
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
            logger.info("BoostNet Mock CDN Server stopped.")


# Singleton instance
mock_cdn_server = MockCDNServer()

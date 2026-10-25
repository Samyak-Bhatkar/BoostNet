"""BoostNet Autonomous Virtual Mobile Node Cluster.

Spawns real asynchronous SOCKS5 proxy servers emulating 3 distinct college mobile devices
with carrier-specific throttling, realistic RTT delays, and battery/data cap metrics:
- Node 1: Rahul's Moto G45 (Airtel 5G)  -> 3.2 Mbps, 25ms RTT, 250 MB cap (Cyan #06b6d4)
- Node 2: Priya's Samsung (Jio 4G)    -> 1.6 Mbps, 45ms RTT, 200 MB cap (Emerald #10b981)
- Node 3: Aman's Vivo (Vi 4G)          -> 1.2 Mbps, 60ms RTT, 150 MB cap (Violet #8b5cf6)
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass
import logging
import socket
import struct
import time
from typing import Dict, List, Optional, Tuple

from backend.config import (
    VIRTUAL_NODE_1_PORT,
    VIRTUAL_NODE_2_PORT,
    VIRTUAL_NODE_3_PORT,
)
from backend.engine.node_manager import NodeManager, NodeStatus, node_manager

logger = logging.getLogger("boostnet.virtual_nodes")


@dataclass
class VirtualNodeConfig:
    node_id: str
    device_name: str
    carrier: str
    port: int
    bandwidth_bytes_per_sec: int      # Rate limit in bytes/sec
    latency_ms: float                 # Artificial delay
    data_cap_mb: float
    battery_level: int
    accent_color: str


class VirtualSocks5Proxy:
    """Individual throttled SOCKS5 proxy server emulating an Android mobile device."""

    def __init__(self, config: VirtualNodeConfig) -> None:
        self.config = config
        self.host = "127.0.0.1"
        self.port = config.port
        self.server: Optional[asyncio.Server] = None
        self.is_running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self.server:
            return
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port, reuse_address=True
        )
        self.is_running = True
        logger.info(
            f"Virtual Node [{self.config.device_name}] active on {self.host}:{self.port} "
            f"({round(self.config.bandwidth_bytes_per_sec * 8 / 1_000_000, 2)} Mbps, {self.config.latency_ms}ms)"
        )

    async def stop(self) -> None:
        self.is_running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            logger.info(f"Virtual Node [{self.config.device_name}] stopped.")

    async def _handle_client(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        if not self.is_running:
            client_writer.close()
            return

        # Simulate cellular RTT on connection
        if self.config.latency_ms > 0:
            await asyncio.sleep(self.config.latency_ms / 1000.0)

        upstream_writer: Optional[asyncio.StreamWriter] = None

        try:
            # 1. SOCKS5 Handshake
            ver = await client_reader.read(1)
            if ver != b"\x05":
                client_writer.close()
                return

            nmethods = (await client_reader.read(1))[0]
            methods = await client_reader.read(nmethods)

            # Accept NO AUTH (0x05, 0x00)
            client_writer.write(b"\x05\x00")
            await client_writer.drain()

            # 2. SOCKS5 Request
            req = await client_reader.read(4)
            if len(req) < 4:
                client_writer.close()
                return

            ver, cmd, rsv, atyp = req
            if cmd != 0x01: # TCP CONNECT only
                client_writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
                await client_writer.drain()
                client_writer.close()
                return

            target_host: str = ""
            if atyp == 0x01: # IPv4
                target_host = socket.inet_ntoa(await client_reader.read(4))
            elif atyp == 0x03: # Domain
                dlen = (await client_reader.read(1))[0]
                target_host = (await client_reader.read(dlen)).decode("latin-1")
            elif atyp == 0x04: # IPv6
                target_host = socket.inet_ntop(socket.AF_INET6, await client_reader.read(16))
            else:
                client_writer.close()
                return

            target_port = struct.unpack("!H", await client_reader.read(2))[0]

            # 3. Connect to destination
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port), timeout=5.0
            )

            # Reply SUCCESS
            client_writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            await client_writer.drain()

            # 4. Bidirectional throttled piping
            p_out = asyncio.create_task(self._pipe_throttled(client_reader, upstream_writer, is_download=False))
            p_in = asyncio.create_task(self._pipe_throttled(upstream_reader, client_writer, is_download=True))
            done, pending = await asyncio.wait([p_out, p_in], return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()

        except Exception as e:
            logger.debug(f"Virtual node [{self.config.device_name}] session ended: {e}")
        finally:
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except Exception:
                pass
            if upstream_writer:
                try:
                    upstream_writer.close()
                    await upstream_writer.wait_closed()
                except Exception:
                    pass

    async def _pipe_throttled(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        is_download: bool,
    ) -> None:
        """Token-bucket rate limiter enforcing exact bandwidth constraints."""
        chunk_size = 16384 # 16 KB chunks
        max_rate = self.config.bandwidth_bytes_per_sec

        try:
            while self.is_running:
                t0 = time.time()
                data = await reader.read(chunk_size)
                if not data:
                    break

                writer.write(data)
                await writer.drain()

                if is_download and max_rate > 0:
                    # Enforce rate throttling
                    expected_time = len(data) / max_rate
                    elapsed = time.time() - t0
                    sleep_time = expected_time - elapsed
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)

        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass


class VirtualCluster:
    """Manages the lifecycle of the 3 simulated mobile nodes."""

    def __init__(self, manager: Optional[NodeManager] = None) -> None:
        self.node_manager = manager or node_manager
        self.configs: List[VirtualNodeConfig] = [
            VirtualNodeConfig(
                node_id=f"127.0.0.1:{VIRTUAL_NODE_1_PORT}",
                device_name="Rahul's Moto G45",
                carrier="Airtel 5G",
                port=VIRTUAL_NODE_1_PORT,
                bandwidth_bytes_per_sec=int(3.2 * 1_000_000 / 8), # 3.2 Mbps = 400 KB/s
                latency_ms=25.0,
                data_cap_mb=250.0,
                battery_level=88,
                accent_color="#06b6d4", # Cyan
            ),
            VirtualNodeConfig(
                node_id=f"127.0.0.1:{VIRTUAL_NODE_2_PORT}",
                device_name="Priya's Samsung Galaxy",
                carrier="Jio 4G",
                port=VIRTUAL_NODE_2_PORT,
                bandwidth_bytes_per_sec=int(1.6 * 1_000_000 / 8), # 1.6 Mbps = 200 KB/s
                latency_ms=45.0,
                data_cap_mb=200.0,
                battery_level=65,
                accent_color="#10b981", # Emerald
            ),
            VirtualNodeConfig(
                node_id=f"127.0.0.1:{VIRTUAL_NODE_3_PORT}",
                device_name="Aman's Vivo V29",
                carrier="Vi 4G",
                port=VIRTUAL_NODE_3_PORT,
                bandwidth_bytes_per_sec=int(1.2 * 1_000_000 / 8), # 1.2 Mbps = 150 KB/s
                latency_ms=60.0,
                data_cap_mb=150.0,
                battery_level=42,
                accent_color="#8b5cf6", # Violet
            ),
        ]
        self.proxies: Dict[str, VirtualSocks5Proxy] = {}
        self.is_active = False

    async def start_cluster(self) -> None:
        """Launches all 3 virtual nodes and registers them in the node manager."""
        for cfg in self.configs:
            proxy = VirtualSocks5Proxy(cfg)
            await proxy.start()
            self.proxies[cfg.node_id] = proxy

            # Register with node manager
            await self.node_manager.register_node(
                node_id=cfg.node_id,
                device_name=cfg.device_name,
                carrier=cfg.carrier,
                host=proxy.host,
                port=cfg.port,
                accent_color=cfg.accent_color,
                data_cap_mb=cfg.data_cap_mb,
                battery_level=cfg.battery_level,
                is_virtual=True,
            )

        self.is_active = True
        logger.info("Virtual Mobile Node Cluster is now ONLINE (3 nodes active).")

    async def stop_cluster(self) -> None:
        """Shuts down all 3 virtual nodes and removes them from node manager."""
        for node_id, proxy in self.proxies.items():
            await proxy.stop()
            await self.node_manager.remove_node(node_id)

        self.proxies.clear()
        self.is_active = False
        logger.info("Virtual Mobile Node Cluster is now OFFLINE.")

    async def kill_node(self, node_id: str) -> None:
        """Simulates mid-download phone disconnect / battery dying for chaos testing."""
        if node_id in self.proxies:
            logger.warning(f"CHAOS TEST: Killing virtual node {node_id} abruptly!")
            await self.proxies[node_id].stop()
            await self.node_manager.set_node_status(node_id, NodeStatus.DISCONNECTED)

    async def restart_node(self, node_id: str) -> None:
        """Restarts a previously killed virtual node."""
        cfg = next((c for c in self.configs if c.node_id == node_id), None)
        if cfg:
            proxy = VirtualSocks5Proxy(cfg)
            await proxy.start()
            self.proxies[node_id] = proxy
            await self.node_manager.set_node_status(node_id, NodeStatus.ACTIVE)
            logger.info(f"Re-spawned virtual node {node_id}")

    async def reset_cluster(self) -> None:
        """Resets all nodes to active state, restores any killed nodes, and resets transfer counters."""
        if not self.is_active:
            await self.start_cluster()
            return

        for cfg in self.configs:
            if cfg.node_id not in self.proxies or not self.proxies[cfg.node_id].is_running:
                await self.restart_node(cfg.node_id)
            else:
                await self.node_manager.set_node_status(cfg.node_id, NodeStatus.ACTIVE)

            node = self.node_manager.get_node(cfg.node_id)
            if node:
                node.bytes_transferred = 0
                node.total_chunks_completed = 0
                node.status = NodeStatus.ACTIVE
                node.data_cap_mb = cfg.data_cap_mb
                node.battery_level = cfg.battery_level
                node.active_connections = 0


# Singleton instance
virtual_cluster = VirtualCluster()

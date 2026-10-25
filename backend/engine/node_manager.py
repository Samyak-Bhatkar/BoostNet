"""BoostNet Node Registry & Dynamic Multipath Orchestrator.

Manages connected mobile phone worker nodes (both physical Wi-Fi mesh donors
and virtual simulated cluster nodes). Implements donor trust controls (hard data caps,
battery safety cutoffs), EWMA throughput/RTT tracking, and contention-ratio weighting.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("boostnet.node_manager")


class NodeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"


@dataclass
class PhoneNode:
    node_id: str                          # e.g. "192.168.43.102:1080" or "127.0.0.1:10801"
    device_name: str                      # e.g. "Rahul's Moto G45"
    carrier: str                          # e.g. "Airtel 5G"
    host: str                             # e.g. "192.168.43.102"
    port: int                             # SOCKS5 / HTTP proxy port
    accent_color: str                     # Cyan "#06b6d4", Emerald "#10b981", Violet "#8b5cf6"
    data_cap_mb: float = 250.0            # Hard data cap in MB
    bytes_transferred: int = 0            # Total bytes relayed through this node
    battery_level: int = 85               # 0-100%
    battery_cutoff_pct: int = 25          # Stop if battery falls below this
    status: NodeStatus = NodeStatus.ACTIVE
    active_connections: int = 0           # In-flight TCP/chunk connections
    ewma_throughput_bps: float = 2_000_000.0 # Initial guess: 2 Mbps
    ewma_rtt_ms: float = 30.0             # Initial guess: 30 ms
    weight: float = 1.0                   # Contention-ratio dynamic weight
    is_virtual: bool = False
    last_seen: float = field(default_factory=time.time)
    total_chunks_completed: int = 0
    in_flight_chunk_id: Optional[str] = None
    shared_tower_flag: bool = False

    @property
    def data_cap_bytes(self) -> int:
        return int(self.data_cap_mb * 1024 * 1024)

    @property
    def data_used_mb(self) -> float:
        return round(self.bytes_transferred / (1024 * 1024), 2)

    @property
    def data_used_pct(self) -> float:
        if self.data_cap_mb <= 0:
            return 0.0
        return min(100.0, round((self.data_used_mb / self.data_cap_mb) * 100, 1))

    @property
    def speed_mbps(self) -> float:
        return round((self.ewma_throughput_bps * 8) / 1_000_000, 2)

    def is_eligible(self) -> bool:
        """Check if node can accept new chunks/connections."""
        if self.status != NodeStatus.ACTIVE:
            return False
        if self.bytes_transferred >= self.data_cap_bytes:
            return False
        if self.battery_level <= self.battery_cutoff_pct:
            return False
        return True


class NodeManager:
    """Central registry and health monitor for all mobile phone nodes."""

    def __init__(self) -> None:
        self._nodes: Dict[str, PhoneNode] = {}
        self._lock = asyncio.Lock()
        self._listeners: List[asyncio.Queue] = []
        self._round_robin_counter = 0

    async def register_node(
        self,
        node_id: str,
        device_name: str,
        carrier: str,
        host: str,
        port: int,
        accent_color: str,
        data_cap_mb: float = 250.0,
        battery_level: int = 85,
        battery_cutoff_pct: int = 25,
        is_virtual: bool = False,
    ) -> PhoneNode:
        async with self._lock:
            existing = self._nodes.get(node_id)
            if existing:
                existing.device_name = device_name
                existing.carrier = carrier
                existing.host = host
                existing.port = port
                existing.accent_color = accent_color
                existing.data_cap_mb = data_cap_mb
                existing.battery_level = battery_level
                existing.battery_cutoff_pct = battery_cutoff_pct
                existing.status = NodeStatus.ACTIVE
                existing.last_seen = time.time()
                node = existing
                logger.info(f"Re-activated node: {node_id} ({device_name})")
            else:
                node = PhoneNode(
                    node_id=node_id,
                    device_name=device_name,
                    carrier=carrier,
                    host=host,
                    port=port,
                    accent_color=accent_color,
                    data_cap_mb=data_cap_mb,
                    battery_level=battery_level,
                    battery_cutoff_pct=battery_cutoff_pct,
                    is_virtual=is_virtual,
                )
                self._nodes[node_id] = node
                logger.info(f"Registered new node: {node_id} ({device_name} - {carrier})")

            self._recalculate_weights()
            await self._broadcast_update()
            return node

    async def update_node_metrics(
        self,
        node_id: str,
        bytes_transferred: int,
        duration_sec: float,
        rtt_ms: Optional[float] = None,
    ) -> None:
        async with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return

            node.bytes_transferred += bytes_transferred
            node.last_seen = time.time()

            # Update EWMA throughput with alpha=0.3
            if duration_sec > 0.05 and bytes_transferred > 0:
                instant_throughput_bps = bytes_transferred / duration_sec
                alpha = 0.3
                node.ewma_throughput_bps = (
                    alpha * instant_throughput_bps + (1 - alpha) * node.ewma_throughput_bps
                )

            # Update EWMA RTT
            if rtt_ms is not None and rtt_ms > 0:
                alpha_rtt = 0.25
                node.ewma_rtt_ms = alpha_rtt * rtt_ms + (1 - alpha_rtt) * node.ewma_rtt_ms

            # Enforce Data Cap Cutoff
            if node.bytes_transferred >= node.data_cap_bytes:
                if node.status == NodeStatus.ACTIVE:
                    node.status = NodeStatus.DRAINING
                    logger.warning(
                        f"Node {node.device_name} reached data cap ({node.data_cap_mb}MB). Transitioned to DRAINING."
                    )

            # Enforce Battery Cutoff
            if node.battery_level <= node.battery_cutoff_pct:
                if node.status == NodeStatus.ACTIVE:
                    node.status = NodeStatus.DRAINING
                    logger.warning(
                        f"Node {node.device_name} reached battery cutoff ({node.battery_level}% <= {node.battery_cutoff_pct}%). Transitioned to DRAINING."
                    )

            self._recalculate_weights()

    async def set_node_status(self, node_id: str, status: NodeStatus) -> None:
        async with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.status = status
                logger.info(f"Node {node_id} status updated to {status.value}")
                self._recalculate_weights()
                await self._broadcast_update()

    async def update_node_limits(
        self,
        node_id: str,
        data_cap_mb: Optional[float] = None,
        battery_cutoff_pct: Optional[int] = None,
    ) -> None:
        async with self._lock:
            node = self._nodes.get(node_id)
            if node:
                if data_cap_mb is not None:
                    node.data_cap_mb = data_cap_mb
                    # If cap increased above current usage, restore to ACTIVE if DRAINING
                    if node.bytes_transferred < node.data_cap_bytes and node.status == NodeStatus.DRAINING:
                        node.status = NodeStatus.ACTIVE
                if battery_cutoff_pct is not None:
                    node.battery_cutoff_pct = battery_cutoff_pct
                self._recalculate_weights()
                await self._broadcast_update()

    async def remove_node(self, node_id: str) -> None:
        async with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                logger.info(f"Evicted node {node_id}")
                self._recalculate_weights()
                await self._broadcast_update()

    def get_node(self, node_id: str) -> Optional[PhoneNode]:
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> List[PhoneNode]:
        return list(self._nodes.values())

    def get_active_nodes(self) -> List[PhoneNode]:
        return [n for n in self._nodes.values() if n.is_eligible()]

    def select_next_node_weighted(self) -> Optional[PhoneNode]:
        """Weighted selection based on contention ratio (go-dispatch-proxy algorithm)."""
        active = self.get_active_nodes()
        if not active:
            return None
        if len(active) == 1:
            return active[0]

        total_weight = sum(n.weight for n in active)
        if total_weight <= 0:
            self._round_robin_counter = (self._round_robin_counter + 1) % len(active)
            return active[self._round_robin_counter]

        # Use normalized lottery pick
        import random
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        for node in active:
            cumulative += node.weight
            if r <= cumulative:
                return node
        return active[-1]

    def _recalculate_weights(self) -> None:
        """Contention-ratio calculation adapted from go-dispatch-proxy.
        Weight = Goodput / (RTT_factor * (1 + active_connections * 0.5))
        """
        for node in self._nodes.values():
            if not node.is_eligible():
                node.weight = 0.0
                continue
            rtt_factor = max(0.5, node.ewma_rtt_ms / 30.0)
            conn_factor = 1.0 + (node.active_connections * 0.4)
            # Normalize throughput in Mbps
            speed_mbps = (node.ewma_throughput_bps * 8) / 1_000_000
            node.weight = max(0.1, round((speed_mbps / (rtt_factor * conn_factor)), 3))

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    async def _broadcast_update(self) -> None:
        snapshot = self.get_telemetry_snapshot()
        for q in list(self._listeners):
            try:
                q.put_nowait(snapshot)
            except asyncio.QueueFull:
                pass

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        active_nodes = self.get_active_nodes()
        all_nodes = self.get_all_nodes()

        combined_speed_bps = sum(n.ewma_throughput_bps for n in active_nodes)
        combined_speed_mbps = round((combined_speed_bps * 8) / 1_000_000, 2)

        # Baseline comparison: compare against single slowest or single median node
        single_baseline_mbps = (
            min((n.speed_mbps for n in active_nodes), default=1.5)
            if active_nodes
            else 1.5
        )
        speed_multiplier = (
            round(combined_speed_mbps / single_baseline_mbps, 1)
            if single_baseline_mbps > 0 and combined_speed_mbps > 0
            else 1.0
        )

        return {
            "type": "telemetry",
            "timestamp": time.time(),
            "combined_speed_mbps": combined_speed_mbps,
            "speed_multiplier": max(1.0, speed_multiplier),
            "active_node_count": len(active_nodes),
            "total_node_count": len(all_nodes),
            "nodes": [
                {
                    "node_id": n.node_id,
                    "device_name": n.device_name,
                    "carrier": n.carrier,
                    "host": n.host,
                    "port": n.port,
                    "accent_color": n.accent_color,
                    "speed_mbps": n.speed_mbps,
                    "rtt_ms": round(n.ewma_rtt_ms, 1),
                    "data_used_mb": n.data_used_mb,
                    "data_cap_mb": n.data_cap_mb,
                    "data_used_pct": n.data_used_pct,
                    "battery_level": n.battery_level,
                    "battery_cutoff_pct": n.battery_cutoff_pct,
                    "status": n.status.value,
                    "weight": n.weight,
                    "active_connections": n.active_connections,
                    "is_virtual": n.is_virtual,
                    "shared_tower_flag": n.shared_tower_flag,
                }
                for n in all_nodes
            ],
        }


# Singleton instance
node_manager = NodeManager()

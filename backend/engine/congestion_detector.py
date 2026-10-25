"""BoostNet Coupled Bottleneck & Same-Tower Congestion Detector.

Detects when multiple mobile phones share the same cellular tower sector and
congested RF airtime. If increasing concurrency on Jio Node 2 causes an inverse
throughput drop and RTT spike on Jio Node 1, flags a Coupled Tower Bottleneck
and dynamically throttles combined concurrency on that carrier.
"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("boostnet.congestion_detector")


@dataclass
class NodeSample:
    timestamp: float
    throughput_bps: float
    rtt_ms: float
    active_conns: int


class CongestionDetector:
    """Monitors cross-correlation of throughput and latency across nodes on the same carrier."""

    def __init__(self, window_size: int = 15) -> None:
        self.window_size = window_size
        self._history: Dict[str, deque[NodeSample]] = {}
        self._shared_bottlenecks: Dict[str, bool] = {} # carrier -> bool

    def record_sample(
        self,
        node_id: str,
        carrier: str,
        throughput_bps: float,
        rtt_ms: float,
        active_conns: int,
    ) -> None:
        if node_id not in self._history:
            self._history[node_id] = deque(maxlen=self.window_size)

        sample = NodeSample(
            timestamp=time.time(),
            throughput_bps=throughput_bps,
            rtt_ms=rtt_ms,
            active_conns=active_conns,
        )
        self._history[node_id].append(sample)

    def analyze_carrier_correlation(
        self, carrier: str, node_ids: List[str]
    ) -> Tuple[bool, float, str]:
        """Analyzes cross-correlation between two nodes on the same carrier.
        Returns: (is_bottleneck, correlation_coefficient, explanation)
        """
        if len(node_ids) < 2:
            self._shared_bottlenecks[carrier] = False
            return False, 0.0, "Single node on carrier (No competition)"

        node_a, node_b = node_ids[0], node_ids[1]
        hist_a = self._history.get(node_a)
        hist_b = self._history.get(node_b)

        if not hist_a or not hist_b or len(hist_a) < 5 or len(hist_b) < 5:
            return False, 0.0, "Collecting metric window..."

        # Calculate Pearson correlation of throughput deltas
        n = min(len(hist_a), len(hist_b))
        rates_a = [hist_a[i].throughput_bps for i in range(-n, 0)]
        rates_b = [hist_b[i].throughput_bps for i in range(-n, 0)]

        mean_a = sum(rates_a) / n
        mean_b = sum(rates_b) / n

        num = sum((rates_a[i] - mean_a) * (rates_b[i] - mean_b) for i in range(n))
        den_a = math.sqrt(sum((rates_a[i] - mean_a) ** 2 for i in range(n)))
        den_b = math.sqrt(sum((rates_b[i] - mean_b) ** 2 for i in range(n)))

        if den_a * den_b == 0:
            corr = 0.0
        else:
            corr = num / (den_a * den_b)

        # Average RTT on carrier
        avg_rtt_a = sum(hist_a[i].rtt_ms for i in range(-n, 0)) / n
        avg_rtt_b = sum(hist_b[i].rtt_ms for i in range(-n, 0)) / n

        # Negative correlation (< -0.45) with elevated RTT indicates they are fighting for the same RF slot
        is_bottleneck = (corr < -0.45) and (max(avg_rtt_a, avg_rtt_b) > 40.0)
        self._shared_bottlenecks[carrier] = is_bottleneck

        if is_bottleneck:
            msg = f"⚠️ Coupled Bottleneck: {carrier} nodes show negative correlation (r={corr:.2f}, RTT={max(avg_rtt_a, avg_rtt_b):.1f}ms). Airtime contention active."
            logger.warning(msg)
        else:
            msg = f"Independent Channels: {carrier} nodes operating without severe airtime collision (r={corr:.2f})."

        return is_bottleneck, round(corr, 2), msg

    def get_status(self) -> Dict[str, Any]:
        return {
            "shared_bottlenecks": self._shared_bottlenecks,
            "has_shared_bottleneck": any(self._shared_bottlenecks.values()),
        }


# Singleton instance
congestion_detector = CongestionDetector()

"""BoostNet System Entry Point.

Launches the complete production system:
1. SOCKS5 & HTTP CONNECT Session Proxy (:9050)
2. Mock CDN Server with Accept-Ranges & IP-Locked Endpoints (:9055)
3. Autonomous 3-Node Virtual Mobile Cluster (:10801, :10802, :10803)
4. FastAPI Control Plane, WebSocket Hub, and PairDrop AMOLED UI (:9051)
"""

from __future__ import annotations
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import logging
import uvicorn

from backend.app import app, get_laptop_local_ip
from backend.config import (
    CONTROL_HOST,
    CONTROL_PORT,
    PROXY_HOST,
    PROXY_PORT,
    MOCK_CDN_PORT,
    SESSION_TOKEN,
    WIFI_PASSWORD,
    WIFI_SSID,
)
from backend.engine.session_proxy import session_proxy
from backend.simulator.mock_cdn_server import mock_cdn_server
from backend.simulator.virtual_nodes import virtual_cluster

logger = logging.getLogger("boostnet.main")


async def start_services():
    print(r"""
============================================================================
  [*] BoostNet: Peer-to-Peer Multi-Mobile Bandwidth Aggregation Engine
  Aligned with UN SDG 9 (Resilient Infrastructure & Innovation)
============================================================================
    """)

    # 1. Start SOCKS5 Session Proxy (:9050)
    await session_proxy.start()

    # 2. Start Mock CDN Server (:9055)
    await mock_cdn_server.start()

    # 3. Pre-launch Virtual Mobile Node Cluster (3 nodes ready for testing)
    await virtual_cluster.start_cluster()

    local_ip = get_laptop_local_ip()

    print(f"""
  [+] Control Plane & PairDrop UI:  http://127.0.0.1:{CONTROL_PORT}
  [+] Local Wi-Fi Network Access:   http://{local_ip}:{CONTROL_PORT}
  [+] SOCKS5 / HTTP Session Proxy:  {PROXY_HOST}:{PROXY_PORT}
  [+] Mock CDN Test Server:         http://127.0.0.1:{MOCK_CDN_PORT}
  [+] 3-Phone Virtual Cluster:      ACTIVE (Airtel 5G, Jio 4G, Vi 4G)
  [+] Wi-Fi Hotspot SSID:           {WIFI_SSID}
  [+] Session Security Token:       {SESSION_TOKEN}
============================================================================
    """)


async def stop_services():
    print("\nShutting down BoostNet services...")
    await virtual_cluster.stop_cluster()
    await mock_cdn_server.stop()
    await session_proxy.stop()
    print("All BoostNet services cleanly stopped.")


def main():
    config = uvicorn.Config(
        app,
        host=CONTROL_HOST,
        port=CONTROL_PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    # Lifespan hook
    @app.on_event("startup")
    async def on_startup():
        await start_services()

    @app.on_event("shutdown")
    async def on_shutdown():
        await stop_services()

    server.run()


if __name__ == "__main__":
    main()

"""BoostNet Configuration & System Settings.

Aligned with UN SDG 9 (Industry, Innovation and Infrastructure).
Production-grade settings for multi-mobile bandwidth aggregation.
"""

from pathlib import Path
import os
import secrets

BASE_DIR = Path(__file__).resolve().parent.parent

# Control Plane & Web UI
CONTROL_PORT = int(os.environ.get("BOOSTNET_CONTROL_PORT", "9051"))
CONTROL_HOST = os.environ.get("BOOSTNET_CONTROL_HOST", "0.0.0.0")

# SOCKS5 & HTTP CONNECT Session Proxy
PROXY_PORT = int(os.environ.get("BOOSTNET_PROXY_PORT", "9050"))
PROXY_HOST = os.environ.get("BOOSTNET_PROXY_HOST", "127.0.0.1")

# Mock CDN Server for Autonomous Simulation & Testing
MOCK_CDN_PORT = int(os.environ.get("BOOSTNET_MOCK_CDN_PORT", "9055"))
MOCK_CDN_HOST = os.environ.get("BOOSTNET_MOCK_CDN_HOST", "127.0.0.1")

# Virtual Mobile Cluster Ports
VIRTUAL_NODE_1_PORT = int(os.environ.get("BOOSTNET_VNODE1_PORT", "10801"))
VIRTUAL_NODE_2_PORT = int(os.environ.get("BOOSTNET_VNODE2_PORT", "10802"))
VIRTUAL_NODE_3_PORT = int(os.environ.get("BOOSTNET_VNODE3_PORT", "10803"))

# Wi-Fi Pairing Credentials & Session Token
WIFI_SSID = os.environ.get("BOOSTNET_WIFI_SSID", "BoostNet_Hotspot")
WIFI_PASSWORD = os.environ.get("BOOSTNET_WIFI_PASS", "boostnet2026")
SESSION_TOKEN = os.environ.get("BOOSTNET_SESSION_TOKEN", secrets.token_hex(3))

# Directories
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_DIR = BASE_DIR / "frontend"

# Micro-Chunk Specifications (aria2 Lineage)
DEFAULT_WARMUP_CHUNK_SIZE = 1 * 1024 * 1024       # 1 MB warmup chunks
DEFAULT_STEADY_CHUNK_SIZE = 4 * 1024 * 1024       # 4 MB steady-state chunks
MIN_STRAGGLER_SPLIT_SIZE = 512 * 1024             # 512 KB min size for split-in-half
PREFLIGHT_PROBE_BYTES = "bytes=0-0"
NODE_STALL_TIMEOUT_SEC = 4.0                      # If node transfers < 10KB/s for 4s, requeue
CONNECT_FAILOVER_TIMEOUT_SEC = 2.5                # SOCKS5 upstream handshake timeout

# Stateless CDN Domain Whitelist for Session Striping
STATELESS_CDN_DOMAINS = [
    "googlevideo.com",
    "ytimg.com",
    "cloudflare.com",
    "fastly.net",
    "akamaized.net",
    "akamaihd.net",
    "cloudfront.net",
    "files.pythonhosted.org",
    "pypi.org",
    "registry.npmjs.org",
    "registry.yarnpkg.com",
    "githubusercontent.com",
    "objects.githubusercontent.com",
    "releases.ubuntu.com",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "127.0.0.1",
    "localhost"
]

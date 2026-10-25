# ⚡ BoostNet: Peer-to-Peer Multi-Mobile Bandwidth Aggregation Engine

> **Bridging the College Campus Connectivity Gap through Multi-Carrier Channel Bonding**  
> *Aligned with UN Sustainable Development Goal 9: Industry, Innovation, and Infrastructure*

---

## 🌐 The Problem: Campus Connectivity & The "Same Tower" Bottleneck

In university lecture halls and hostel blocks, hundreds of students frequently experience crippled internet speeds despite having active 4G/5G mobile data plans. This occurs due to two distinct physics and network bottlenecks:

1. **Same-Tower Cellular Contention:** When 500 students in the same auditorium use the same telecom provider (e.g., Jio), they all compete for the same physical cell tower PRBs (Physical Resource Blocks). Aggregating two phones on the exact same congested cell carrier yields negligible gains because the radio bottleneck exists upstream at the base transceiver station.
2. **Heterogeneous Multi-Carrier Asymmetry:** However, if Rahul has **Airtel 5G**, Priya has **Jio 4G**, and Aman has **Vodafone Idea (Vi) 4G**, each device communicates with physically distinct cell towers and frequency bands. By bonding connections across distinct carriers, aggregate bandwidth scales multiplicatively.

**BoostNet** is an autonomous peer-to-peer bandwidth aggregation proxy and parallel range downloader designed for laptops in low-bandwidth educational environments.

---

## 🏛️ Open-Source Architecture Lineage

BoostNet builds directly upon the architectural wisdom of four battle-tested open-source foundations:

| Upstream Project | Core Architectural Pattern Implemented in BoostNet |
|:---|:---|
| **[`schlagmichdoch/PairDrop`](https://github.com/schlagmichdoch/PairDrop)** | Pure AMOLED `#000000` aesthetic, HTML5 Canvas concentric pulsing radar rings, polar coordinate peer placement, circular SVG progress rings, and zero-config local network peer discovery. |
| **[`go-dispatch-proxy`](https://github.com/moriyoshi/go-dispatch-proxy)** | Contention-ratio weighted round-robin scheduling (`Weight = (Speed / Max_Speed) * (Min_RTT / RTT)`), zero-copy async stream pipes, and real-time interface health scoring. |
| **[`aria2/aria2`](https://github.com/aria2/aria2)** | Dynamic multi-source HTTP range splitting, in-flight work-stealing, and the signature **"Split-in-Half"** straggler elimination algorithm. |
| **[`Visible-Wifi-Cellular`](https://github.com/themarpe/Visible-Wifi-Cellular)** | Android dual-transport binding using `WifiNetworkSpecifier` (for local laptop communication) while enforcing all upstream internet traffic over `TRANSPORT_CELLULAR` via `Network.getSocketFactory()`. |

---

## ⚡ System Architecture: The Dual-Engine Model

BoostNet operates as a dual-engine architecture tailored to the physical constraints of different protocols:

```
                                  [ BoostNet UI (:9051) ]
                                             |
                   +-------------------------+-------------------------+
                   |                                                   |
      [ Approach A: Range Downloader ]                    [ Approach B: Session Proxy ]
                   |                                                   |
      * Preflight Multi-IP Probe                          * SOCKS5 / HTTP CONNECT (:9050)
      * aria2 "Split-in-Half" Stragglers                  * QUIC -> TCP Fallback (UDP 0x07)
      * Mid-Download Chaos Requeue                        * Stateless CDN vs Sticky Auth Pinning
      * 64-Block Live Chunk Map                           * Same-Tower Congestion Correlation
                   |                                                   |
                   +-------------------------+-------------------------+
                                             |
                        [ Contention-Ratio Weighted Scheduler ]
                                             |
             +-------------------------------+-------------------------------+
             |                               |                               |
    [ Rahul's Moto G45 ]            [ Priya's Galaxy ]              [ Aman's Vivo V29 ]
       Airtel 5G (Cyan)                Jio 4G (Emerald)                Vi 4G (Violet)
      3.2 Mbps | 25ms RTT             1.6 Mbps | 45ms RTT             1.2 Mbps | 60ms RTT
```

### Approach A: Multi-Phone Smart Range Downloader (Large Files & ISOs)
- **Preflight Multi-IP Probe:** Before splitting a download, BoostNet issues micro-probes (`bytes=0-4095`) across all active phones. If an upstream CDN enforces single-IP token binding (returning `HTTP 403 Forbidden` on secondary IPs), BoostNet automatically aborts multi-chunk mode and falls back to a **Single-Node Pinned Stream**, preventing data corruption.
- **aria2 "Split-in-Half" Straggler Elimination:** If one phone stalls on a slow 4G sector, idle fast nodes steal work by dynamically halving the remaining byte range of the slowest in-flight chunk.
- **Mid-Download Chaos Recovery:** If a donor phone disconnects, walks away, or runs low on battery, in-flight byte chunks are automatically requeued to surviving nodes without failing the file.
- **Byte-Exact Integrity:** Automatic SHA-256 hash calculation and verification against upstream server hashes.

### Approach B: Hybrid Session Proxy & Stream Accelerator (Live Web & YouTube)
- **SOCKS5 & HTTP CONNECT Load Balancer (`127.0.0.1:9050`):** System proxy compatible with Chrome, Firefox, curl, and Windows system settings.
- **QUIC-to-TCP Auto-Fallback:** Google Chrome and YouTube default to HTTP/3 (QUIC over UDP). Mobile hotspots frequently drop or throttle UDP, and UDP cannot be reliably striped across multiple upstream NATs without VPN server infrastructure. BoostNet intercepts SOCKS5 `UDP ASSOCIATE (0x03)` and immediately rejects it with `0x07 (Command not supported)`, compelling browsers to cleanly fall back to high-performance multiplexed TCP HTTP/2.
- **Stateless CDN Striping vs. Sticky Host Affinity:** Video and asset domains (`*.googlevideo.com`, CDN subdomains) are dynamically striped across all phones. Stateful authentication domains (`github.com`, bank portals) are pinned deterministically to a single phone using consistent hashing (`crc32(domain) % eligible_nodes`).
- **Media Stream Accelerator (`/api/v1/stream-proxy`):** Intercepts streaming URLs, extracts video fragments with `yt-dlp`, and feeds a multi-threaded look-ahead prefetch ring buffer.

---

## 🔒 Donor Trust, Battery & Data Cap Protections

BoostNet is designed for mutual trust among college peers:
- **Zero-Config QR Pairing:** Generates pairing QR codes encoding the laptop's Wi-Fi hotspot credentials and session auth token (`/api/v1/pairing-qr`).
- **Hard Data Cap Enforcement:** Each donor sets a strict allowance (e.g., 250 MB). When 90% is reached, the UI warns the host; at 100%, the node transitions to `DRAINING` status and zero additional chunks are scheduled.
- **Battery Preservation Cutoff:** If a donor's battery drops below 25%, BoostNet automatically disconnects the device.

---

## 🧪 Automated Verification Test Suite

BoostNet includes a comprehensive automated test harness in `tests/` that executes against the built-in throttled Virtual Mobile Cluster and Mock CDN Server:

| Test Module | Description | Verified Outcome |
|:---|:---|:---|
| `test_speed_aggregation.py` | Multi-phone concurrent range download across Airtel 5G, Jio 4G, and Vi 4G | **PASSED** (4.42 Mbps aggregated throughput, exact SHA-256 match) |
| `test_mid_download_chaos.py` | Abrupt node termination at 25% progress during 16MB download | **PASSED** (Caught cancellation, requeued chunk, byte-exact SHA-256 verified) |
| `test_ip_locked_fallback.py` | Upstream signed token returning `403 Forbidden` on secondary IPs | **PASSED** (Preflight probe detected lock, cleanly pinned to single node) |
| `test_data_cap_cutoff.py` | Donor phone with 1.0 MB data cap during 8MB download | **PASSED** (Honored 1.0 MB cap, entered `DRAINING`, remaining nodes finished file) |
| `test_session_proxy.py` | SOCKS5 UDP rejection (QUIC fallback), CDN striping, and domain affinity | **PASSED** (`0x07` returned on UDP, domain affinity pinned, SOCKS5 tunnel verified) |

```bash
# Run the complete test suite
python -m pytest tests/ -v -s
# Result: 5 passed in 107.54s
```

---

## 🚀 Quickstart & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Windows 10/11 or Linux

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/your-username/BoostNet.git
cd BoostNet
pip install -r requirements.txt
```

### 2. Launch BoostNet
Double-click `run_boostnet.bat` or execute:
```bash
python main.py
```

### 3. Open the PairDrop-Inspired UI
Navigate to **`http://127.0.0.1:9051`** in any modern web browser.
- **Simulate 3 Phones:** Click the `⚡ Simulate 3 Phones` button in the header to activate the virtual mobile cluster (Rahul's Moto G45 Airtel 5G, Priya's Samsung Jio 4G, Aman's Vivo Vi 4G).
- **Turbo Range Download:** Paste any direct download URL (or use the built-in `http://127.0.0.1:9055/test-16mb.bin`) and click **⚡ Turbo Download** to observe the 64-block aria2 visualizer light up in Cyan, Emerald, and Violet.
- **Browser Proxy:** Configure your browser or system SOCKS5 proxy to `127.0.0.1:9050` to route daily browsing through the multi-phone hybrid proxy.

---

## 📱 Companion Modules

### 1. Chrome Extension (`chrome-extension/`)
- Manifest V3 browser extension.
- Automatically intercepts file downloads over 2 MB.
- Forwards session cookies, referrers, and URLs directly to BoostNet's Turbo Downloader.

### 2. Android Donor App Reference (`android-donor-app/`)
- Production Kotlin modules demonstrating Android OS-level dual-transport binding:
  - `CellularSocksBridge.kt`: Embedded SOCKS5 proxy server.
  - `QrPairingManager.kt`: Wi-Fi hotspot association via `WifiNetworkSpecifier` and cellular socket binding via `ConnectivityManager.NetworkCallback`.
  - `BoostNetForegroundService.kt`: Persistent foreground service with live notification controls.

---

## 📜 License
Licensed under the Apache License 2.0. Aligned with UN SDG 9 for educational open access.

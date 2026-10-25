"""Assemble a self-contained, zero-dependency index.html bundle for BoostNet.

Inlines styles-main.css, responsive mobile CSS, radar-canvas.js, chunk-visualizer.js,
and app.js with instant Cloud Demo mode and mobile setup guide.
"""

from pathlib import Path

ROOT = Path(r"c:\SAMYAKFILES\Users\AppData\Local\Programs\DATA SCIENCE COURSE\BoostNet")
FRONTEND_DIR = ROOT / "frontend"
API_FRONTEND_DIR = ROOT / "api" / "frontend"

css_file = FRONTEND_DIR / "css" / "styles-main.css"
radar_file = FRONTEND_DIR / "js" / "radar-canvas.js"
chunk_file = FRONTEND_DIR / "js" / "chunk-visualizer.js"
app_file = FRONTEND_DIR / "js" / "app.js"
html_template = FRONTEND_DIR / "index.html"

css_content = css_file.read_text(encoding="utf-8")
radar_content = radar_file.read_text(encoding="utf-8")
chunk_content = chunk_file.read_text(encoding="utf-8")
app_content = app_file.read_text(encoding="utf-8")

# Additional responsive mobile styles
extra_mobile_css = """
/* Responsive Mobile & AMOLED Hardening (UN SDG 9 Mobile-First Experience) */
svg {
    max-width: 100%;
}

.brand-logo svg {
    width: 22px !important;
    height: 22px !important;
    max-width: 22px !important;
    max-height: 22px !important;
    fill: #000000 !important;
}

@media (max-width: 768px) {
    header {
        height: auto;
        min-height: 56px;
        padding: 8px 12px;
        flex-wrap: wrap;
        gap: 8px;
    }

    .brand-text h1 {
        font-size: 1rem;
    }

    .brand-text p {
        display: none;
    }

    .header-actions {
        gap: 6px;
        flex-wrap: wrap;
    }

    .action-pill {
        padding: 6px 10px;
        font-size: 0.72rem;
    }

    #center-host-node {
        width: 110px;
        height: 110px;
    }

    .host-icon-wrapper {
        width: 32px;
        height: 32px;
        margin-bottom: 2px;
    }

    .host-icon-wrapper svg {
        width: 18px;
        height: 18px;
    }

    .host-speed-label {
        font-size: 0.95rem;
    }

    .host-boost-pill {
        font-size: 0.58rem;
        padding: 1px 6px;
    }

    .peer-node {
        width: 86px;
        height: 86px;
    }

    .peer-svg-ring {
        width: 96px;
        height: 96px;
        top: -5px;
        left: -5px;
    }

    .peer-svg-ring circle {
        cx: 48;
        cy: 48;
        r: 41;
    }

    .peer-avatar {
        width: 28px;
        height: 28px;
        margin-bottom: 2px;
    }

    .peer-avatar svg {
        width: 14px;
        height: 14px;
    }

    .peer-name {
        font-size: 0.62rem;
        max-width: 70px;
    }

    .peer-carrier {
        font-size: 0.55rem;
    }

    .peer-speed-badge {
        font-size: 0.55rem;
        padding: 2px 6px;
        bottom: -10px;
    }

    #empty-peers-notice {
        top: 62%;
        padding: 0 16px;
    }

    #empty-peers-notice h3 {
        font-size: 0.85rem;
    }

    #empty-peers-notice p {
        font-size: 0.72rem;
    }

    .drawer-header {
        height: 48px;
        padding: 0 12px;
    }

    .drawer-tabs {
        overflow-x: auto;
        gap: 4px;
        scrollbar-width: none;
    }

    .drawer-tabs::-webkit-scrollbar {
        display: none;
    }

    .tab-btn {
        padding: 6px 10px;
        font-size: 0.72rem;
        white-space: nowrap;
    }

    .drawer-content {
        padding: 14px 12px;
    }

    .chunk-grid {
        grid-template-columns: repeat(16, 1fr);
        gap: 3px;
    }

    .chunk-block {
        height: 14px;
    }

    .download-controls {
        flex-direction: column;
    }

    .btn-primary {
        justify-content: center;
        height: 40px;
    }

    .stream-grid {
        grid-template-columns: 1fr;
    }
}
"""

combined_css = css_content + "\n" + extra_mobile_css

# Modernize chunk visualizer for case insensitivity
chunk_content_fixed = chunk_content.replace(
    'if (item.status === "completed") {',
    'const status = (item.status || "").toLowerCase();\n            if (status === "completed") {'
).replace(
    '} else if (item.status === "downloading") {',
    '} else if (status === "downloading") {'
)

# Modernize app_content for fast instant demo on cloud and mobile radius
app_content_fixed = app_content.replace(
    '        // If local backend doesn\'t connect within 2.5s (e.g. on Vercel), fall back to Cloud Demo Mode',
    '''        // Instant cloud demo check: If deployed on Vercel or non-localhost, start demo immediately
        if (!window.location.hostname.includes("127.0.0.1") && !window.location.hostname.includes("localhost")) {
            this.startDemoMode();
        }

        // If local backend doesn't connect within 2.5s, fall back to Cloud Demo Mode'''
).replace(
    '        const radius = Math.min(window.innerWidth, window.innerHeight) * 0.28;',
    '''        const isMobile = window.innerWidth <= 768;
        const radiusFactor = isMobile ? 0.35 : 0.28;
        const radius = Math.min(window.innerWidth, window.innerHeight) * radiusFactor;'''
).replace(
    '            const circumference = 364.4;',
    '''            const isMobile = window.innerWidth <= 768;
            const circumference = isMobile ? 257.6 : 364.4;'''
).replace(
    '''        // SVG progress circumference = 2 * PI * 58 ≈ 364.4
        el.innerHTML = `
            <svg class="peer-svg-ring" viewBox="0 0 130 130">
                <circle class="bg" cx="65" cy="65" r="58"></circle>
                <circle class="progress" cx="65" cy="65" r="58"
                        stroke="${node.accent_color}"
                        stroke-dasharray="364.4"
                        stroke-dashoffset="364.4"></circle>
            </svg>''',
    '''        const isMobile = window.innerWidth <= 768;
        const ringSize = isMobile ? 96 : 130;
        const center = ringSize / 2;
        const r = isMobile ? 41 : 58;
        const circumference = (2 * Math.PI * r).toFixed(1);

        el.innerHTML = `
            <svg class="peer-svg-ring" viewBox="0 0 ${ringSize} ${ringSize}">
                <circle class="bg" cx="${center}" cy="${center}" r="${r}"></circle>
                <circle class="progress" cx="${center}" cy="${center}" r="${r}"
                        stroke="${node.accent_color}"
                        stroke-dasharray="${circumference}"
                        stroke-dashoffset="${circumference}"></circle>
            </svg>'''
)

# Add Mobile Guide button event listener
app_content_fixed = app_content_fixed.replace(
    '        // QR Pairing Modal',
    '''        // Mobile Guide Modal
        const mobileGuideBtn = document.getElementById("btn-mobile-guide");
        if (mobileGuideBtn) {
            mobileGuideBtn.addEventListener("click", () => {
                document.getElementById("mobile-guide-modal").classList.add("active");
            });
        }

        // QR Pairing Modal'''
)

html_markup = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>BoostNet | Multi-Mobile Bandwidth Aggregation Engine</title>
    <meta name="description" content="Peer-to-peer mobile bandwidth aggregation, parallel HTTP byte-range accelerator, and intelligent session-striping proxy for college laptops (UN SDG 9)"/>
    <meta name="theme-color" content="#000000"/>
    <style>
{combined_css}
    </style>
</head>
<body>
    <!-- Concentric Radar Background (PairDrop Lineage) -->
    <canvas id="radar-canvas"></canvas>

    <!-- Header Navigation -->
    <header>
        <div class="brand">
            <div class="brand-logo" style="width: 38px; height: 38px;">
                <svg width="22" height="22" viewBox="0 0 24 24" style="width: 22px; height: 22px; fill: #000000;">
                    <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"></path>
                </svg>
            </div>
            <div class="brand-text">
                <h1>BoostNet <span class="tag">SDG 9</span></h1>
                <p>Multi-Mobile Bandwidth Aggregator</p>
            </div>
        </div>

        <div class="header-actions">
            <!-- 1-Click Virtual Lab Simulation Toggle -->
            <button class="action-pill" id="btn-toggle-sim" title="Spawn or kill 3 simulated Airtel/Jio/Vi mobile phones">
                ⚡ Simulate 3 Phones
            </button>

            <!-- Mobile Phone Guide Pill -->
            <button class="action-pill" id="btn-mobile-guide" title="How to use BoostNet on your phone">
                📱 Mobile Setup
            </button>

            <!-- SOCKS5 Proxy Status Pill -->
            <div class="action-pill active" title="Local SOCKS5 / HTTP Proxy listening on 127.0.0.1:9050">
                <span class="status-dot"></span>
                <span>Proxy :9050 ON</span>
            </div>

            <!-- QR Code Pairing Button -->
            <button class="icon-btn" id="btn-pairing-qr" title="Scan QR Code from Android Phone">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M4 4h6v6H4V4zm2 2v2h2V6H6zm8-2h6v6h-6V4zm2 2v2h2V6h-2zM4 14h6v6H4v-6zm2 2v2h2v-2H6zm10 0h2v2h-2v-2zm-2-2h2v2h-2v-2zm4 4h2v2h-2v-2zm-2 2h2v2h-2v-2zm4-2h2v2h-2v-2z"></path>
                </svg>
            </button>

            <!-- Info / About Button -->
            <button class="icon-btn" id="btn-about" title="Architecture & Open-Source Lineage">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M11 17h2v-6h-2v6zm1-15C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zM11 9h2V7h-2v2z"></path>
                </svg>
            </button>
        </div>
    </header>

    <!-- Radar Center Stage -->
    <div id="radar-container">
        <!-- Center Host Node (You / Laptop Host) -->
        <div id="center-host-node">
            <div class="host-icon-wrapper">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"></path>
                </svg>
            </div>
            <div class="host-speed-label" id="host-combined-speed">0.0 <small>Mbps ▲</small></div>
            <div class="host-boost-pill" id="host-boost-multiplier">1.0x Boost</div>
            <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 2px;" id="host-active-count">0 Active Nodes</div>
        </div>

        <!-- Orbiting Mobile Peer Nodes Container -->
        <div id="orbiting-peers-container"></div>

        <!-- Empty State Notice -->
        <div id="empty-peers-notice">
            <h3>No Mobile Nodes Connected</h3>
            <p>Scan the QR code on an Android phone or click <strong>"Simulate 3 Phones"</strong> to aggregate bandwidth.</p>
        </div>
    </div>

    <!-- Bottom Slide-Up Telemetry Drawer (PairDrop-Style Panel) -->
    <div id="telemetry-drawer">
        <div class="drawer-header">
            <div class="drawer-tabs">
                <button class="tab-btn active" data-tab="downloader">
                    ⚡ Turbo Range Downloader (Approach A)
                </button>
                <button class="tab-btn" data-tab="stream">
                    🎥 Stream Accelerator (Ring Buffer)
                </button>
                <button class="tab-btn" data-tab="proxy">
                    🌐 Session Proxy Matrix (Approach B)
                </button>
            </div>
            <svg class="drawer-toggle-icon" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"></path>
            </svg>
        </div>

        <div class="drawer-content">
            <!-- Tab 1: Turbo Downloader UI -->
            <div class="tab-pane active" id="tab-downloader">
                <div class="download-controls">
                    <div class="input-group">
                        <input type="text" id="download-url-input" placeholder="Paste file download URL (or pick a test preset below)..." value="http://127.0.0.1:9055/test-32mb.bin"/>
                    </div>
                    <button class="btn-primary" id="btn-start-download">
                        ⚡ Turbo Download
                    </button>
                </div>

                <!-- Quick Presets for Demo & Testing -->
                <div class="quick-presets">
                    <span>Quick Test Presets:</span>
                    <button class="preset-chip" data-url="http://127.0.0.1:9055/test-16mb.bin">16 MB Mock CDN</button>
                    <button class="preset-chip" data-url="http://127.0.0.1:9055/test-32mb.bin">32 MB Mock CDN</button>
                    <button class="preset-chip" data-url="http://127.0.0.1:9055/test-64mb.bin">64 MB Mock CDN</button>
                    <button class="preset-chip" data-url="http://127.0.0.1:9055/signed-ip-locked.bin">Signed IP-Locked 403 Test</button>
                </div>

                <!-- Active Download Telemetry & 64-Block Visualizer -->
                <div class="chunk-map-card">
                    <div class="chunk-map-header">
                        <h4>
                            <span id="dl-current-filename">ubuntu-24.04-dataset.iso</span>
                            <span style="color:var(--text-muted); font-size: 0.75rem;" id="dl-stats-text">Ready</span>
                        </h4>
                        <div class="chunk-telemetry-badge" id="dl-current-speed">0.0 Mbps (ETA: --)</div>
                    </div>

                    <!-- Progress Bar -->
                    <div style="height: 6px; background: var(--surface-3); border-radius: 3px; overflow: hidden; margin-bottom: 12px;">
                        <div id="dl-progress-bar" style="height: 100%; width: 0%; background: linear-gradient(90deg, var(--accent-emerald), var(--accent-cyan)); transition: width 0.3s ease;"></div>
                    </div>

                    <!-- 64-Block aria2 Chunk Map Grid -->
                    <div class="chunk-grid" id="chunk-grid"></div>

                    <!-- Legend & SHA-256 Checksum -->
                    <div class="chunk-legend">
                        <div class="legend-item"><span class="legend-dot" style="background:#06b6d4;"></span> Rahul's Moto (Airtel 5G)</div>
                        <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> Priya's Samsung (Jio 4G)</div>
                        <div class="legend-item"><span class="legend-dot" style="background:#8b5cf6;"></span> Aman's Vivo (Vi 4G)</div>
                        <div class="legend-item"><span class="legend-dot" style="background:#1e293b;"></span> Queued Chunks</div>
                        <div style="margin-left: auto;" id="dl-sha256-text">SHA-256: <code>Idle</code></div>
                    </div>
                </div>
            </div>

            <!-- Tab 2: Stream Accelerator UI -->
            <div class="tab-pane" id="tab-stream">
                <div class="download-controls">
                    <div class="input-group">
                        <input type="text" id="stream-url-input" placeholder="Paste YouTube or video stream URL for multi-phone look-ahead prefetch..." value="http://127.0.0.1:9055/test-16mb.bin"/>
                    </div>
                    <button class="btn-primary" id="btn-start-stream">
                        🎥 Accelerate Stream
                    </button>
                </div>

                <div class="stream-grid">
                    <div class="stream-player-card">
                        <div class="video-container">
                            <video id="stream-video-player" controls preload="metadata"></video>
                        </div>
                        <div style="padding: 10px; font-size: 0.75rem; color: var(--text-muted);">
                            Piping 1MB byte-range segments via Multi-Phone Sliding Window Ring Buffer.
                        </div>
                    </div>

                    <div class="ring-buffer-card">
                        <h4 style="font-size: 0.85rem; margin-bottom: 8px;">Sliding Window Look-Ahead Prefetch Buffer</h4>
                        <p style="font-size: 0.75rem; color: var(--text-muted);">Upcoming 1 MB media segments pre-fetched in parallel across all mobile nodes:</p>

                        <div class="ring-buffer-visualizer">
                            <div class="buffer-slot" style="border-color: var(--accent-cyan); color: var(--accent-cyan);">
                                <span>Seg #0</span>
                                <strong>Airtel</strong>
                            </div>
                            <div class="buffer-slot" style="border-color: var(--accent-emerald); color: var(--accent-emerald);">
                                <span>Seg #1</span>
                                <strong>Jio</strong>
                            </div>
                            <div class="buffer-slot" style="border-color: var(--accent-violet); color: var(--accent-violet);">
                                <span>Seg #2</span>
                                <strong>Vi</strong>
                            </div>
                            <div class="buffer-slot" style="border-color: var(--accent-cyan); color: var(--accent-cyan);">
                                <span>Seg #3</span>
                                <strong>Airtel</strong>
                            </div>
                        </div>

                        <div style="margin-top: 16px; font-size: 0.75rem; color: var(--text-muted); line-height: 1.5;">
                            ⚡ <strong>QUIC Fallback:</strong> SOCKS5 server rejects UDP ASSOCIATE with <code>0x07</code>, seamlessly forcing Chrome from QUIC to TCP for parallel aggregation without touching <code>chrome://flags</code>.
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab 3: Session Proxy Matrix UI -->
            <div class="tab-pane" id="tab-proxy">
                <!-- Coupled Bottleneck / Same-Tower Congestion Banner -->
                <div class="congestion-alert-banner" id="congestion-banner" style="display: none;">
                    ⚠️ Shared Tower Bottleneck Detected (Jio SIMs) — Airtime Contention Mitigation Active
                </div>

                <div class="session-table-wrapper">
                    <table class="session-table">
                        <thead>
                            <tr>
                                <th>Target Host</th>
                                <th>Carrier / Node</th>
                                <th>Routing Type</th>
                                <th>Data Transferred</th>
                                <th>Duration</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="session-table-body">
                            <tr>
                                <td colspan="6" style="text-align: center; color: var(--text-muted);">
                                    No active proxy sessions (:9050). Open Chrome or run pip install to see traffic.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Mobile Setup Guide Modal -->
    <div class="modal-overlay" id="mobile-guide-modal">
        <div class="modal-card" style="max-width: 580px;">
            <div class="modal-header">
                <h3>📱 How to Use BoostNet on Mobile</h3>
                <button class="icon-btn modal-close-btn" style="width: 32px; height: 32px;">✕</button>
            </div>
            <div class="modal-body" style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.6;">
                <p style="margin-bottom: 12px;">
                    BoostNet bonds multiple phones (Airtel + Jio + Vi) into one unified broadband pipe for your college laptop, bypassing library congestion without cables or root access.
                </p>

                <h4 style="color: var(--accent-emerald); margin-bottom: 6px;">How It Works:</h4>
                <ol style="padding-left: 20px; margin-bottom: 14px;">
                    <li style="margin-bottom: 6px;">
                        <strong>Step 1 — Connect to Local Wi-Fi:</strong> Keep your laptop and phones on the same Wi-Fi (e.g. laptop hotspot or dorm router).
                    </li>
                    <li style="margin-bottom: 6px;">
                        <strong>Step 2 — Scan Pairing QR:</strong> Click the <strong>QR Code</strong> button in the header from your laptop, and scan the QR code using your phone's camera.
                    </li>
                    <li style="margin-bottom: 6px;">
                        <strong>Step 3 — Dual-Transport Binding:</strong> The BoostNet mobile worker keeps local Wi-Fi active for laptop talk while routing download chunks over cellular (4G/5G).
                    </li>
                    <li style="margin-bottom: 6px;">
                        <strong>Step 4 — Donor Trust Limits:</strong> Set custom limits directly from the dashboard: e.g. maximum 250 MB data cap and pause if phone battery drops below 25%.
                    </li>
                </ol>

                <div style="background: var(--surface-2); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 10px; font-size: 0.75rem;">
                    💡 <strong>Live Cloud Showcase:</strong> When viewing on Vercel, click <strong>"⚡ Simulate 3 Phones"</strong> or <strong>"⚡ Turbo Download"</strong> to watch the multi-carrier aggregation demo right in your browser!
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-primary modal-close-btn">Understood</button>
            </div>
        </div>
    </div>

    <!-- QR Code Pairing Modal (PairDrop Style) -->
    <div class="modal-overlay" id="qr-pairing-modal">
        <div class="modal-card">
            <div class="modal-header">
                <h3>Pair Android Phone</h3>
                <button class="icon-btn modal-close-btn" style="width: 32px; height: 32px;">✕</button>
            </div>
            <div class="modal-body">
                <div class="modal-qr-container">
                    <div class="qr-image-wrapper">
                        <img id="qr-modal-image" alt="Pairing QR Code"/>
                    </div>
                    <div style="font-size: 0.85rem; font-weight: 700; color: var(--accent-emerald);">
                        Session PIN: <span id="qr-modal-pin">8f4a2e</span>
                    </div>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.6; background: var(--surface-2); padding: 12px; border-radius: 8px;">
                    <div><strong>Wi-Fi SSID:</strong> <span id="qr-modal-ssid">BoostNet_Hotspot</span></div>
                    <div><strong>Password:</strong> <span id="qr-modal-pass">boostnet2026</span></div>
                    <div style="margin-top: 6px; font-size: 0.72rem; color: var(--text-muted); word-break: break-all;">
                        URI: <code id="qr-modal-uri">boostnet://pair?...</code>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-secondary modal-close-btn">Close</button>
            </div>
        </div>
    </div>

    <!-- Node Details & Donor Trust Modal -->
    <div class="modal-overlay" id="node-details-modal">
        <div class="modal-card">
            <div class="modal-header">
                <h3 id="modal-node-title">Rahul's Moto G45 (Airtel 5G)</h3>
                <button class="icon-btn modal-close-btn" style="width: 32px; height: 32px;">✕</button>
            </div>
            <div class="modal-body">
                <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 16px;">
                    <div><strong>Local Socket:</strong> <span id="modal-node-ip">192.168.43.102:1080</span></div>
                    <div><strong>Speed / Latency:</strong> <span id="modal-node-speed">3.2 Mbps</span> (<span id="modal-node-rtt">25ms</span>)</div>
                    <div><strong>Data Used:</strong> <span id="modal-node-used">112 / 250 MB (44.8%)</span></div>
                </div>

                <div style="margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 6px;">
                        <span>Hard Data Cap Allowance</span>
                        <strong id="label-node-data-cap" style="color: var(--accent-emerald);">250 MB</strong>
                    </div>
                    <input type="range" id="slider-node-data-cap" min="20" max="1000" step="10" value="250" style="width: 100%; accent-color: var(--accent-emerald);"/>
                </div>

                <div style="margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 6px;">
                        <span>Battery Safety Cutoff</span>
                        <strong id="label-node-battery-cutoff" style="color: var(--accent-rose);">25%</strong>
                    </div>
                    <input type="range" id="slider-node-battery-cutoff" min="10" max="50" step="5" value="25" style="width: 100%; accent-color: var(--accent-rose);"/>
                </div>

                <div style="display: flex; gap: 8px;">
                    <button class="btn-secondary" id="btn-drain-node" style="flex: 1;">Drain & Pause Node</button>
                    <button class="btn-secondary" id="btn-evict-node" style="color: var(--accent-rose); border-color: rgba(244,63,94,0.3);">Evict Node</button>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-secondary modal-close-btn">Cancel</button>
                <button class="btn-primary" id="btn-save-node-limits">Save Settings</button>
            </div>
        </div>
    </div>

    <!-- About & Open-Source Lineage Modal -->
    <div class="modal-overlay" id="about-modal">
        <div class="modal-card" style="max-width: 640px;">
            <div class="modal-header">
                <h3>About BoostNet Architecture</h3>
                <button class="icon-btn modal-close-btn" style="width: 32px; height: 32px;">✕</button>
            </div>
            <div class="modal-body" style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.6;">
                <p style="margin-bottom: 12px;">
                    <strong>BoostNet</strong> aggregates cellular data connections across nearby mobile devices using local Wi-Fi mesh networking and dynamic micro-chunk multiplexing, delivering multi-carrier throughput to college laptops without requiring paid cloud servers or USB cables.
                </p>

                <h4 style="color: var(--text-primary); margin-bottom: 8px;">Open-Source Architecture Lineage:</h4>
                <table style="width: 100%; font-size: 0.75rem; border-collapse: collapse; margin-bottom: 16px;">
                    <tr style="border-bottom: 1px solid var(--border-subtle); color: var(--text-muted);">
                        <th style="padding: 6px 0;">Repository</th>
                        <th>Architectural Pattern Implemented in BoostNet</th>
                    </tr>
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 6px 0; color: var(--accent-cyan); font-weight: 600;">schlagmichdoch/PairDrop</td>
                        <td>Concentric pulsing radar canvas geometry, polar peer avatars, pure black AMOLED theme</td>
                    </tr>
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 6px 0; color: var(--accent-emerald); font-weight: 600;">go-dispatch-proxy</td>
                        <td>Contention-ratio weighted round-robin scheduling, zero-copy async stream pipes</td>
                    </tr>
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 6px 0; color: var(--accent-violet); font-weight: 600;">aria2/aria2</td>
                        <td>Dynamic Split & In-Flight Work-Stealing ("Split-in-Half" straggler elimination)</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: var(--accent-amber); font-weight: 600;">Visible-Wifi-Cellular</td>
                        <td>Android dual-transport binding (WifiNetworkSpecifier + TRANSPORT_CELLULAR socketFactory)</td>
                    </tr>
                </table>

                <p style="font-size: 0.72rem; color: var(--text-muted);">
                    Aligned with UN SDG 9 (Industry, Innovation, and Infrastructure) to bridge the digital connectivity gap in low-bandwidth educational institutions.
                </p>
            </div>
            <div class="modal-footer">
                <button class="btn-primary modal-close-btn">Got It</button>
            </div>
        </div>
    </div>

    <!-- Self-Contained Zero-Dependency Scripts -->
    <script>
{radar_content}
    </script>
    <script>
{chunk_content_fixed}
    </script>
    <script>
{app_content_fixed}
    </script>
</body>
</html>
"""

# Write to both frontend/index.html and api/frontend/index.html
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
(FRONTEND_DIR / "index.html").write_text(html_markup, encoding="utf-8")

API_FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
(API_FRONTEND_DIR / "index.html").write_text(html_markup, encoding="utf-8")

print(f"[+] Successfully bundled self-contained index.html ({len(html_markup)} bytes)")

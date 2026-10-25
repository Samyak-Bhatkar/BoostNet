/**
 * BoostNet Frontend Orchestrator
 * Lineage: PairDrop UI State Machine & Event Dispatcher
 * Manages WebSocket telemetry, polar peer node layout, and telemetry drawers.
 */

class BoostNetApp {
    constructor() {
        this.ws = null;
        this.nodes = [];
        this.selectedNodeId = null;
        this.chunkVisualizer = null;
        this.radarCanvas = null;
        this.isVirtualActive = false;

        this.init();
    }

    init() {
        this.radarCanvas = new RadarCanvas("radar-canvas");
        this.chunkVisualizer = new ChunkVisualizer("chunk-grid");

        this.bindEvents();
        this.connectWebSocket();
    }

    bindEvents() {
        // Drawer toggle
        const drawer = document.getElementById("telemetry-drawer");
        const drawerHeader = document.querySelector(".drawer-header");
        if (drawerHeader) {
            drawerHeader.addEventListener("click", (e) => {
                // If clicked on tab button, don't toggle drawer
                if (e.target.closest(".tab-btn")) return;
                drawer.classList.toggle("expanded");
            });
        }

        // Tab buttons
        document.querySelectorAll(".tab-btn").forEach((btn) => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const targetTab = btn.dataset.tab;
                this.switchTab(targetTab);
                drawer.classList.add("expanded");
            });
        });

        // 1-Click Virtual Phone Cluster Toggle
        const simBtn = document.getElementById("btn-toggle-sim");
        if (simBtn) {
            simBtn.addEventListener("click", () => this.toggleVirtualCluster());
        }

        // QR Pairing Modal
        const qrBtn = document.getElementById("btn-pairing-qr");
        if (qrBtn) {
            qrBtn.addEventListener("click", () => this.openQrModal());
        }

        // Info / About Modal
        const aboutBtn = document.getElementById("btn-about");
        if (aboutBtn) {
            aboutBtn.addEventListener("click", () => this.openAboutModal());
        }

        // Close modal buttons
        document.querySelectorAll(".modal-close-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".modal-overlay").forEach((m) => m.classList.remove("active"));
            });
        });

        // Start Download Form
        const dlBtn = document.getElementById("btn-start-download");
        const dlInput = document.getElementById("download-url-input");
        if (dlBtn && dlInput) {
            dlBtn.addEventListener("click", () => this.startDownload(dlInput.value));
            dlInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") this.startDownload(dlInput.value);
            });
        }

        // Demo Presets
        document.querySelectorAll(".preset-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                const url = chip.dataset.url;
                if (dlInput) dlInput.value = url;
                this.startDownload(url);
            });
        });

        // Stream Accelerator Button
        const streamBtn = document.getElementById("btn-start-stream");
        const streamInput = document.getElementById("stream-url-input");
        if (streamBtn && streamInput) {
            streamBtn.addEventListener("click", () => this.startStream(streamInput.value));
        }

        // Node Limits Update Save
        const saveLimitsBtn = document.getElementById("btn-save-node-limits");
        if (saveLimitsBtn) {
            saveLimitsBtn.addEventListener("click", () => this.saveNodeLimits());
        }

        // Pause/Drain Button
        const drainBtn = document.getElementById("btn-drain-node");
        if (drainBtn) {
            drainBtn.addEventListener("click", () => this.toggleNodeDrain());
        }

        // Evict Button
        const evictBtn = document.getElementById("btn-evict-node");
        if (evictBtn) {
            evictBtn.addEventListener("click", () => this.evictNode());
        }
    }

    switchTab(tabId) {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

        const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
        const targetPane = document.getElementById(`tab-${tabId}`);

        if (targetBtn) targetBtn.classList.add("active");
        if (targetPane) targetPane.classList.add("active");
    }

    connectWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log("BoostNet Telemetry WebSocket connected.");
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleTelemetryUpdate(data);
            } catch (e) {
                console.error("Telemetry parsing error:", e);
            }
        };

        this.ws.onclose = () => {
            console.warn("WebSocket closed. Reconnecting in 2 seconds...");
            setTimeout(() => this.connectWebSocket(), 2000);
        };

        this.ws.onerror = (err) => {
            console.error("WebSocket error:", err);
            this.ws.close();
        };
    }

    handleTelemetryUpdate(data) {
        if (data.type === "telemetry") {
            this.updateCenterHostNode(data);
            this.updateOrbitingPeers(data.nodes || []);
            this.updateVirtualClusterState(data.virtual_cluster_active);
            this.updateSessionTable(data.sessions || []);
            this.updateCongestionStatus(data.congestion || {});
        } else if (data.type === "download_progress") {
            this.updateDownloadProgress(data);
        }
    }

    updateCenterHostNode(telemetry) {
        const speedEl = document.getElementById("host-combined-speed");
        const boostEl = document.getElementById("host-boost-multiplier");
        const countEl = document.getElementById("host-active-count");

        if (speedEl) speedEl.innerHTML = `${telemetry.combined_speed_mbps} <small>Mbps ▲</small>`;
        if (boostEl) boostEl.innerText = `${telemetry.speed_multiplier}x Boost`;
        if (countEl) countEl.innerText = `${telemetry.active_node_count} Active Nodes`;
    }

    updateOrbitingPeers(nodes) {
        this.nodes = nodes;
        const container = document.getElementById("orbiting-peers-container");
        const emptyNotice = document.getElementById("empty-peers-notice");

        if (!container) return;

        if (nodes.length === 0) {
            container.innerHTML = "";
            if (emptyNotice) emptyNotice.style.display = "flex";
            return;
        }

        if (emptyNotice) emptyNotice.style.display = "none";

        // Polar layout geometry
        const cx = window.innerWidth / 2;
        const cy = window.innerHeight / 2;
        const radius = Math.min(window.innerWidth, window.innerHeight) * 0.28;

        // Sync peer DOM elements
        const existingMap = new Map();
        container.querySelectorAll(".peer-node").forEach((el) => {
            existingMap.set(el.dataset.nodeId, el);
        });

        nodes.forEach((node, idx) => {
            const angle = (2 * Math.PI * idx) / nodes.length - Math.PI / 2;
            const x = cx + radius * Math.cos(angle);
            const y = cy + radius * Math.sin(angle);

            let peerEl = existingMap.get(node.node_id);
            if (!peerEl) {
                peerEl = this.createPeerElement(node);
                container.appendChild(peerEl);
            }

            // Position with translate
            peerEl.style.left = `${x}px`;
            peerEl.style.top = `${y}px`;
            peerEl.style.transform = "translate(-50%, -50%)";

            this.updatePeerElement(peerEl, node);
            existingMap.delete(node.node_id);
        });

        // Remove evicted peers
        existingMap.forEach((el) => el.remove());
    }

    createPeerElement(node) {
        const el = document.createElement("div");
        el.className = "peer-node";
        el.dataset.nodeId = node.node_id;

        // SVG progress circumference = 2 * PI * 58 ≈ 364.4
        el.innerHTML = `
            <svg class="peer-svg-ring" viewBox="0 0 130 130">
                <circle class="bg" cx="65" cy="65" r="58"></circle>
                <circle class="progress" cx="65" cy="65" r="58"
                        stroke="${node.accent_color}"
                        stroke-dasharray="364.4"
                        stroke-dashoffset="364.4"></circle>
            </svg>
            <div class="peer-avatar" style="border: 2px solid ${node.accent_color};">
                <svg viewBox="0 0 24 24" fill="${node.accent_color}">
                    <path d="M15.5 1h-8C6.12 1 5 2.12 5 3.5v17C5 21.88 6.12 23 7.5 23h8c1.38 0 2.5-1.12 2.5-2.5v-17C18 2.12 16.88 1 15.5 1zm-4 21c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm4.5-4H7V4h9v14z"></path>
                </svg>
            </div>
            <div class="peer-name">${node.device_name}</div>
            <div class="peer-carrier">${node.carrier}</div>
            <div class="peer-speed-badge">
                <span class="speed-val">${node.speed_mbps} Mbps</span>
                <span style="color: var(--text-muted); font-size: 0.6rem;">•</span>
                <span class="rtt-val">${node.rtt_ms}ms</span>
            </div>
        `;

        el.addEventListener("click", () => this.openNodeDetailsModal(node.node_id));
        return el;
    }

    updatePeerElement(el, node) {
        const ring = el.querySelector("circle.progress");
        if (ring) {
            const circumference = 364.4;
            const pct = Math.min(100, Math.max(0, node.data_used_pct));
            const offset = circumference - (circumference * pct) / 100;
            ring.style.strokeDashoffset = offset;
            ring.style.stroke = node.accent_color;
        }

        const speedVal = el.querySelector(".speed-val");
        if (speedVal) speedVal.innerText = `${node.speed_mbps} Mbps`;

        const rttVal = el.querySelector(".rtt-val");
        if (rttVal) rttVal.innerText = `${node.rtt_ms}ms`;

        if (node.status === "DRAINING") {
            el.style.opacity = "0.7";
            el.style.filter = "grayscale(0.5)";
        } else if (node.status === "DEGRADED") {
            el.style.borderColor = "var(--accent-amber)";
        } else {
            el.style.opacity = "1";
            el.style.filter = "none";
        }
    }

    updateVirtualClusterState(isActive) {
        this.isVirtualActive = !!isActive;
        const simBtn = document.getElementById("btn-toggle-sim");
        if (simBtn) {
            if (this.isVirtualActive) {
                simBtn.classList.add("active");
                simBtn.innerHTML = `<span class="status-dot"></span> Virtual Cluster (3 Nodes Active)`;
            } else {
                simBtn.classList.remove("active");
                simBtn.innerHTML = `⚡ Simulate 3 Phones`;
            }
        }
    }

    async toggleVirtualCluster() {
        try {
            const res = await fetch("/api/v1/virtual-nodes/toggle", { method: "POST" });
            const data = await res.json();
            console.log("Virtual cluster toggled:", data);
        } catch (e) {
            console.error("Failed to toggle virtual cluster:", e);
        }
    }

    async openQrModal() {
        try {
            const res = await fetch("/api/v1/pairing-qr");
            const data = await res.json();

            const imgEl = document.getElementById("qr-modal-image");
            const pinEl = document.getElementById("qr-modal-pin");
            const ssidEl = document.getElementById("qr-modal-ssid");
            const passEl = document.getElementById("qr-modal-pass");
            const uriEl = document.getElementById("qr-modal-uri");

            if (imgEl) imgEl.src = data.qr_image_data_url;
            if (pinEl) pinEl.innerText = data.session_token;
            if (ssidEl) ssidEl.innerText = data.ssid;
            if (passEl) passEl.innerText = data.password;
            if (uriEl) uriEl.innerText = data.pairing_uri;

            document.getElementById("qr-pairing-modal").classList.add("active");
        } catch (e) {
            console.error("Failed to load QR pairing payload:", e);
        }
    }

    openNodeDetailsModal(nodeId) {
        this.selectedNodeId = nodeId;
        const node = this.nodes.find((n) => n.node_id === nodeId);
        if (!node) return;

        document.getElementById("modal-node-title").innerText = `${node.device_name} (${node.carrier})`;
        document.getElementById("modal-node-ip").innerText = node.node_id;
        document.getElementById("modal-node-speed").innerText = `${node.speed_mbps} Mbps`;
        document.getElementById("modal-node-rtt").innerText = `${node.rtt_ms} ms`;
        document.getElementById("modal-node-used").innerText = `${node.data_used_mb} MB (${node.data_used_pct}%)`;

        const capSlider = document.getElementById("slider-node-data-cap");
        const capLabel = document.getElementById("label-node-data-cap");
        if (capSlider && capLabel) {
            capSlider.value = node.data_cap_mb;
            capLabel.innerText = `${node.data_cap_mb} MB`;
            capSlider.oninput = () => {
                capLabel.innerText = `${capSlider.value} MB`;
            };
        }

        const batterySlider = document.getElementById("slider-node-battery-cutoff");
        const batteryLabel = document.getElementById("label-node-battery-cutoff");
        if (batterySlider && batteryLabel) {
            batterySlider.value = node.battery_cutoff_pct;
            batteryLabel.innerText = `${node.battery_cutoff_pct}%`;
            batterySlider.oninput = () => {
                batteryLabel.innerText = `${batterySlider.value}%`;
            };
        }

        const drainBtn = document.getElementById("btn-drain-node");
        if (drainBtn) {
            drainBtn.innerText = node.status === "DRAINING" ? "Resume Node" : "Drain & Pause Node";
        }

        document.getElementById("node-details-modal").classList.add("active");
    }

    async saveNodeLimits() {
        if (!this.selectedNodeId) return;
        const cap = parseFloat(document.getElementById("slider-node-data-cap").value);
        const battery = parseInt(document.getElementById("slider-node-battery-cutoff").value);

        try {
            await fetch(`/api/v1/nodes/${encodeURIComponent(this.selectedNodeId)}/limits`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ data_cap_mb: cap, battery_cutoff_pct: battery }),
            });
            document.getElementById("node-details-modal").classList.remove("active");
        } catch (e) {
            console.error("Failed to update node limits:", e);
        }
    }

    async toggleNodeDrain() {
        if (!this.selectedNodeId) return;
        const node = this.nodes.find((n) => n.node_id === this.selectedNodeId);
        if (!node) return;

        const newStatus = node.status === "DRAINING" ? "ACTIVE" : "DRAINING";
        try {
            await fetch(`/api/v1/nodes/${encodeURIComponent(this.selectedNodeId)}/status`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus }),
            });
            document.getElementById("node-details-modal").classList.remove("active");
        } catch (e) {
            console.error("Failed to toggle node drain:", e);
        }
    }

    async evictNode() {
        if (!this.selectedNodeId) return;
        try {
            await fetch(`/api/v1/nodes/${encodeURIComponent(this.selectedNodeId)}`, {
                method: "DELETE",
            });
            document.getElementById("node-details-modal").classList.remove("active");
        } catch (e) {
            console.error("Failed to evict node:", e);
        }
    }

    openAboutModal() {
        document.getElementById("about-modal").classList.add("active");
    }

    async startDownload(url) {
        if (!url) return;
        const statusEl = document.getElementById("download-status-banner");
        if (statusEl) {
            statusEl.style.display = "block";
            statusEl.innerHTML = `⚡ Preflight Multi-IP Probe in progress across phone nodes...`;
        }

        // Expand drawer to show chunk map
        document.getElementById("telemetry-drawer").classList.add("expanded");
        this.switchTab("downloader");

        try {
            const res = await fetch("/api/v1/downloads", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: url }),
            });
            const data = await res.json();
            console.log("Download started:", data);
        } catch (e) {
            console.error("Download failed to launch:", e);
        }
    }

    updateDownloadProgress(data) {
        const fileEl = document.getElementById("dl-current-filename");
        const speedEl = document.getElementById("dl-current-speed");
        const progressEl = document.getElementById("dl-progress-bar");
        const statsEl = document.getElementById("dl-stats-text");
        const shaEl = document.getElementById("dl-sha256-text");

        if (fileEl) fileEl.innerText = data.filename;
        if (speedEl) speedEl.innerText = `${data.speed_mbps} Mbps (ETA: ${data.eta_sec || 0}s)`;

        if (progressEl) progressEl.style.width = `${data.progress_pct}%`;

        if (statsEl) {
            const downMb = (data.downloaded_bytes / (1024 * 1024)).toFixed(1);
            const totalMb = (data.total_bytes / (1024 * 1024)).toFixed(1);
            statsEl.innerText = `${downMb} / ${totalMb} MB (${data.progress_pct}%) • Status: ${data.status}`;
        }

        if (shaEl && data.sha256) {
            shaEl.innerHTML = `SHA-256: <code>${data.sha256.substring(0, 16)}...</code> ${data.hash_verified ? '<span style="color:var(--accent-emerald);">[Verified ✓]</span>' : ''}`;
        }

        // Update 64-block aria2 chunk visualizer
        if (this.chunkVisualizer && data.blocks) {
            this.chunkVisualizer.updateBlocks(data.blocks);
        }
    }

    startStream(url) {
        if (!url) return;
        const video = document.getElementById("stream-video-player");
        if (video) {
            const streamProxyUrl = `/api/v1/stream-proxy?url=${encodeURIComponent(url)}`;
            video.src = streamProxyUrl;
            video.play().catch((e) => console.log("Autoplay waiting for user:", e));
        }

        // Expand drawer to stream tab
        document.getElementById("telemetry-drawer").classList.add("expanded");
        this.switchTab("stream");
    }

    updateSessionTable(sessions) {
        const tbody = document.getElementById("session-table-body");
        if (!tbody) return;

        if (sessions.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No active proxy sessions (:9050). Open Chrome or run pip install to see traffic.</td></tr>`;
            return;
        }

        tbody.innerHTML = sessions.map((s) => `
            <tr>
                <td style="font-family: var(--font-mono);">${s.host}</td>
                <td><span style="color: ${s.accent_color}; font-weight:600;">${s.carrier}</span></td>
                <td>
                    <span class="${s.routing_type.includes('Striped') ? 'badge-striped' : 'badge-sticky'}">
                        ${s.routing_type}
                    </span>
                </td>
                <td style="font-family: var(--font-mono);">${(s.bytes / 1024).toFixed(1)} KB</td>
                <td>${s.duration_sec}s</td>
                <td><span style="color: ${s.status === 'ACTIVE' ? 'var(--accent-emerald)' : 'var(--text-muted)'};">${s.status}</span></td>
            </tr>
        `).join("");
    }

    updateCongestionStatus(congestion) {
        const banner = document.getElementById("congestion-banner");
        if (!banner) return;

        if (congestion.has_shared_bottleneck) {
            banner.style.display = "flex";
            banner.innerText = `⚠️ Shared Tower Bottleneck Detected (Jio SIMs) — Airtime Contention Mitigation Active`;
        } else {
            banner.style.display = "none";
        }
    }
}

// Instantiate on DOM load
window.addEventListener("DOMContentLoaded", () => {
    window.app = new BoostNetApp();
});

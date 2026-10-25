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

        let isConnected = false;
        try {
            this.ws = new WebSocket(wsUrl);
        } catch (e) {
            console.warn("WebSocket initialization failed, activating Cloud Demo Mode:", e);
            this.startDemoMode();
            return;
        }

        // If local backend doesn't connect within 2.5s (e.g. on Vercel), fall back to Cloud Demo Mode
        const fallbackTimer = setTimeout(() => {
            if (!isConnected) {
                console.info("BoostNet: Cloud showcase mode active (running autonomous demo simulation).");
                this.startDemoMode();
            }
        }, 2500);

        this.ws.onopen = () => {
            isConnected = true;
            clearTimeout(fallbackTimer);
            this.stopDemoMode();
            console.log("BoostNet Telemetry WebSocket connected to local backend.");
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
            if (!isConnected) {
                this.startDemoMode();
            }
            setTimeout(() => this.connectWebSocket(), 5000);
        };

        this.ws.onerror = (err) => {
            if (!isConnected) {
                this.startDemoMode();
            }
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
            console.warn("Toggling demo cluster locally on cloud showcase");
            this.isVirtualActive = !this.isVirtualActive;
            this.updateVirtualClusterState(this.isVirtualActive);
            if (this.isVirtualActive) {
                this.updateOrbitingPeers(this.demoNodes || []);
                this.updateCenterHostNode({ combined_speed_mbps: 6.0, speed_multiplier: 3.0, active_node_count: 3 });
            } else {
                this.updateOrbitingPeers([]);
                this.updateCenterHostNode({ combined_speed_mbps: 0.0, speed_multiplier: 1.0, active_node_count: 0 });
            }
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
            console.warn("Using demo QR pairing payload on cloud showcase");
            const pinEl = document.getElementById("qr-modal-pin");
            const ssidEl = document.getElementById("qr-modal-ssid");
            const passEl = document.getElementById("qr-modal-pass");
            const uriEl = document.getElementById("qr-modal-uri");

            if (pinEl) pinEl.innerText = "bn_demo_84920481";
            if (ssidEl) ssidEl.innerText = "BoostNet-College-Hotspot";
            if (passEl) passEl.innerText = "boostnet2026";
            if (uriEl) uriEl.innerText = "boostnet://pair?token=bn_demo_84920481&host=192.168.137.1&port=9050";
            document.getElementById("qr-pairing-modal").classList.add("active");
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
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            console.log("Download started:", data);
        } catch (e) {
            console.warn("Running simulated interactive download on cloud showcase:", e);
            this.runDemoDownload(url);
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

    startDemoMode() {
        if (this.demoInterval) return;
        console.log("BoostNet: Running in Autonomous Demo/Simulation Mode (for Vercel/Cloud Showcase)");

        const proxyPill = document.querySelector(".header-actions .action-pill.active span:last-child");
        if (proxyPill) proxyPill.innerText = "Cloud Demo Mode";

        this.demoNodes = [
            {
                node_id: "127.0.0.1:10801",
                device_name: "Rahul's Moto G45",
                carrier: "Airtel 5G",
                host: "127.0.0.1",
                port: 10801,
                status: "ACTIVE",
                battery_level: 88,
                battery_cutoff_pct: 25,
                data_cap_mb: 250.0,
                bytes_transferred: 14 * 1024 * 1024,
                speed_mbps: 3.2,
                rtt_ms: 25,
                data_used_mb: 14.0,
                data_used_pct: 5.6,
                accent_color: "#06b6d4"
            },
            {
                node_id: "127.0.0.1:10802",
                device_name: "Priya's Samsung Galaxy",
                carrier: "Jio 4G",
                host: "127.0.0.1",
                port: 10802,
                status: "ACTIVE",
                battery_level: 74,
                battery_cutoff_pct: 25,
                data_cap_mb: 200.0,
                bytes_transferred: 9 * 1024 * 1024,
                speed_mbps: 1.6,
                rtt_ms: 45,
                data_used_mb: 9.0,
                data_used_pct: 4.5,
                accent_color: "#10b981"
            },
            {
                node_id: "127.0.0.1:10803",
                device_name: "Aman's Vivo V29",
                carrier: "Vi 4G",
                host: "127.0.0.1",
                port: 10803,
                status: "ACTIVE",
                battery_level: 42,
                battery_cutoff_pct: 25,
                data_cap_mb: 150.0,
                bytes_transferred: 6 * 1024 * 1024,
                speed_mbps: 1.2,
                rtt_ms: 60,
                data_used_mb: 6.0,
                data_used_pct: 4.0,
                accent_color: "#8b5cf6"
            }
        ];

        this.demoTelemetry = {
            type: "telemetry",
            active_node_count: 3,
            combined_speed_mbps: 6.0,
            speed_multiplier: 3.0,
            virtual_cluster_active: true,
            nodes: this.demoNodes,
            sessions: [
                { session_id: "ses_1", host: "r1---sn-googlevideo.com:443", carrier: "Airtel 5G", accent_color: "#06b6d4", routing_type: "Striped (Stateless CDN)", bytes: 1048576, status: "ACTIVE", duration_sec: 14.2 },
                { session_id: "ses_2", host: "r2---sn-googlevideo.com:443", carrier: "Jio 4G", accent_color: "#10b981", routing_type: "Striped (Stateless CDN)", bytes: 819200, status: "ACTIVE", duration_sec: 12.0 },
                { session_id: "ses_3", host: "github.com:443", carrier: "Vi 4G", accent_color: "#8b5cf6", routing_type: "Sticky (Host Affinity)", bytes: 32768, status: "ACTIVE", duration_sec: 8.5 }
            ],
            congestion: {
                has_shared_bottleneck: false,
                status: "OPTIMAL"
            }
        };

        this.handleTelemetryUpdate(this.demoTelemetry);

        // Fluctuate speeds subtly for realistic feel
        this.demoInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.stopDemoMode();
                return;
            }
            if (!this.demoNodes || this.demoNodes.length === 0) return;
            const j1 = (Math.random() * 0.4 - 0.2);
            const j2 = (Math.random() * 0.3 - 0.15);
            const j3 = (Math.random() * 0.2 - 0.1);
            this.demoNodes[0].speed_mbps = parseFloat(Math.max(1.8, 3.2 + j1).toFixed(2));
            this.demoNodes[1].speed_mbps = parseFloat(Math.max(0.9, 1.6 + j2).toFixed(2));
            this.demoNodes[2].speed_mbps = parseFloat(Math.max(0.6, 1.2 + j3).toFixed(2));
            this.demoTelemetry.combined_speed_mbps = parseFloat(
                (this.demoNodes[0].speed_mbps + this.demoNodes[1].speed_mbps + this.demoNodes[2].speed_mbps).toFixed(1)
            );
            this.handleTelemetryUpdate(this.demoTelemetry);
        }, 1800);
    }

    stopDemoMode() {
        if (this.demoInterval) {
            clearInterval(this.demoInterval);
            this.demoInterval = null;
        }
        const proxyPill = document.querySelector(".header-actions .action-pill.active span:last-child");
        if (proxyPill) proxyPill.innerText = "Proxy :9050 ON";
    }

    runDemoDownload(url) {
        const filename = (url && url.split("/").pop()) || "test-16mb.bin";
        const statusEl = document.getElementById("download-status-banner");
        if (statusEl) {
            statusEl.style.display = "block";
            statusEl.innerHTML = `⚡ [Demo Mode] Preflight Multi-IP Probe verified across Airtel 5G, Jio 4G, Vi 4G (HTTP 206 Accept-Ranges OK)`;
        }

        const totalBytes = 16 * 1024 * 1024;
        let downloadedBytes = 0;
        const totalBlocks = 64;
        const blocks = Array.from({ length: totalBlocks }, (_, i) => ({
            index: i,
            progress_pct: 0,
            status: "PENDING",
            color: null
        }));

        const nodeColors = ["#06b6d4", "#10b981", "#8b5cf6"];
        let blockCursor = 0;

        if (this.demoDownloadInterval) clearInterval(this.demoDownloadInterval);

        this.demoDownloadInterval = setInterval(() => {
            const step = Math.min(3, totalBlocks - blockCursor);
            for (let s = 0; s < step; s++) {
                const bIdx = blockCursor + s;
                if (bIdx < totalBlocks) {
                    blocks[bIdx].status = "COMPLETED";
                    blocks[bIdx].progress_pct = 100;
                    blocks[bIdx].color = nodeColors[bIdx % 3];
                }
            }
            blockCursor += step;
            downloadedBytes = Math.min(totalBytes, Math.floor((blockCursor / totalBlocks) * totalBytes));

            const pct = Math.floor((downloadedBytes / totalBytes) * 100);
            const isDone = blockCursor >= totalBlocks;

            this.updateDownloadProgress({
                filename: filename,
                downloaded_bytes: downloadedBytes,
                total_bytes: totalBytes,
                progress_pct: pct,
                speed_mbps: (4.4 + (Math.random() * 0.4 - 0.2)).toFixed(2),
                eta_sec: isDone ? 0 : Math.max(1, Math.round((totalBlocks - blockCursor) * 0.4)),
                status: isDone ? "COMPLETED" : "DOWNLOADING",
                sha256: "62f9b00b08ccfa3fd38bd262ab13302dd85b95694393e22a6ff2e37a69d57b6c",
                hash_verified: isDone,
                blocks: blocks
            });

            if (isDone) {
                clearInterval(this.demoDownloadInterval);
                this.demoDownloadInterval = null;
                if (statusEl) {
                    statusEl.innerHTML = `🎉 [Demo Mode] Download Complete! SHA-256 byte-exact match verified across all phone chunks.`;
                }
            }
        }, 300);
    }
}

// Instantiate on DOM load
window.addEventListener("DOMContentLoaded", () => {
    window.app = new BoostNetApp();
});

/**
 * BoostNet Concentric Radar Canvas Engine
 * Direct architectural lineage: schlagmichdoch/PairDrop canvas-worker.js
 * Renders smooth pulsing concentric radar rings with AMOLED emerald glow.
 */

class RadarCanvas {
    constructor(canvasId = "radar-canvas") {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext("2d");

        this.baseColor = "16, 185, 129"; // Emerald RGB
        this.baseOpacity = 0.18;
        this.speed = 1.0;
        this.animate = true;
        this.currentFrame = 0;

        this.init();
        window.addEventListener("resize", () => this.resize());
    }

    init() {
        this.resize();
        this.startAnimation();
    }

    resize() {
        this.w = window.innerWidth;
        this.h = window.innerHeight;
        this.canvas.width = this.w;
        this.canvas.height = this.h;
        this.x0 = this.w / 2;
        this.y0 = this.h / 2;
        this.dw = Math.round(Math.min(this.w, this.h) / 8);
    }

    startAnimation() {
        const loop = (timestamp) => {
            if (this.animate) {
                this.draw(timestamp);
            }
            requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
    }

    draw(timestamp) {
        this.ctx.clearRect(0, 0, this.w, this.h);

        // Calculate pulsing offset: 0 to dw
        const cycleMs = 3000;
        const phase = (timestamp % cycleMs) / cycleMs;
        const pulseOffset = phase * this.dw;

        const maxRadius = Math.max(this.w, this.h) * 0.7;

        // Draw concentric circles from center
        for (let r = pulseOffset; r < maxRadius; r += this.dw) {
            if (r < 75) continue; // Don't draw over center host node

            const distanceFactor = 1 - (r / maxRadius);
            const opacity = Math.max(0, this.baseOpacity * distanceFactor);

            this.ctx.beginPath();
            this.ctx.arc(this.x0, this.y0, r, 0, Math.PI * 2);
            this.ctx.strokeStyle = `rgba(${this.baseColor}, ${opacity})`;
            this.ctx.lineWidth = 1.5;
            this.ctx.stroke();
        }

        // Faint crosshair grid lines (radar styling)
        this.ctx.beginPath();
        this.ctx.moveTo(this.x0 - maxRadius, this.y0);
        this.ctx.lineTo(this.x0 + maxRadius, this.y0);
        this.ctx.moveTo(this.x0, this.y0 - maxRadius);
        this.ctx.lineTo(this.x0, this.y0 + maxRadius);
        this.ctx.strokeStyle = `rgba(${this.baseColor}, 0.04)`;
        this.ctx.lineWidth = 1;
        this.ctx.stroke();
    }
}

window.RadarCanvas = RadarCanvas;

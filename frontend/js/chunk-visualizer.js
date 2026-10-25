/**
 * BoostNet 64-Block Chunk Map Visualizer
 * Lineage: BitTorrent piece maps & aria2 segment visualizer
 * Renders 64 dynamic blocks showing real-time multi-phone range allocation.
 */

class ChunkVisualizer {
    constructor(containerId = "chunk-grid") {
        this.container = document.getElementById(containerId);
        this.totalBlocks = 64;
        this.blocks = [];
        this.init();
    }

    init() {
        if (!this.container) return;
        this.container.innerHTML = "";
        this.blocks = [];

        for (let i = 0; i < this.totalBlocks; i++) {
            const block = document.createElement("div");
            block.className = "chunk-block";
            block.dataset.index = i;
            block.title = `Block #${i}: Idle`;
            this.container.appendChild(block);
            this.blocks.push(block);
        }
    }

    updateBlocks(blockData) {
        if (!blockData || !this.blocks.length) return;

        blockData.forEach((item, idx) => {
            if (idx >= this.blocks.length) return;
            const el = this.blocks[idx];

            if (item.status === "completed") {
                el.style.backgroundColor = item.color || "#10b981";
                el.style.color = item.color || "#10b981";
                el.className = "chunk-block completed";
                el.title = `Block #${idx}: Completed (${item.range || ''})`;
            } else if (item.status === "downloading") {
                el.style.backgroundColor = item.color || "#06b6d4";
                el.style.color = item.color || "#06b6d4";
                el.className = "chunk-block downloading";
                el.title = `Block #${idx}: Downloading via Phone (${item.range || ''})`;
            } else {
                el.style.backgroundColor = "#1e293b";
                el.className = "chunk-block";
                el.title = `Block #${idx}: Queued`;
            }
        });
    }

    reset() {
        this.blocks.forEach((el, idx) => {
            el.style.backgroundColor = "#1e293b";
            el.className = "chunk-block";
            el.title = `Block #${idx}: Idle`;
        });
    }
}

window.ChunkVisualizer = ChunkVisualizer;

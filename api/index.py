"""BoostNet Cloud Showcase API for Vercel Serverless.

Serves the PairDrop-inspired AMOLED frontend and mock telemetry endpoints for
the online live demo. Real multi-phone SOCKS5 bonding runs locally on the user's laptop.
"""

from __future__ import annotations
import mimetypes
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse

app = FastAPI(
    title="BoostNet Bandwidth Aggregation Engine",
    description="Multi-Mobile Bandwidth Aggregation Cloud Showcase",
    version="2.0.0",
)

CURRENT_DIR = Path(__file__).resolve().parent
FRONTEND_DIRS = [
    CURRENT_DIR / "frontend",
    CURRENT_DIR.parent / "frontend",
    Path("frontend"),
    Path("/var/task/frontend"),
    Path("/var/task/api/frontend"),
]


def find_frontend_file(rel_path: str) -> Path | None:
    clean_path = rel_path.lstrip("/")
    if clean_path.startswith("static/"):
        clean_path = clean_path[7:]

    for base in FRONTEND_DIRS:
        candidate = base / clean_path
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def get_index_html() -> str:
    for base in FRONTEND_DIRS:
        index_file = base / "index.html"
        if index_file.exists():
            return index_file.read_text(encoding="utf-8")
    return "<h1>BoostNet Cloud Showcase Active</h1>"


# 1. Root & Vercel rewrite endpoints
@app.get("/")
@app.get("/api")
@app.get("/api/index.py")
async def serve_root():
    return HTMLResponse(content=get_index_html())


DEMO_QR_DATA_URL = "data:image/png;base64,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"


# 2. API Endpoints
@app.get("/api/v1/pairing-qr")
@app.get("/v1/pairing-qr")
async def get_pairing_qr():
    return {
        "status": "ok",
        "session_token": "bn_demo_84920481",
        "ssid": "BoostNet-College-Hotspot",
        "password": "boostnet2026",
        "pairing_uri": "boostnet://pair?token=bn_demo_84920481&host=192.168.137.1&port=9050",
        "qr_image_data_url": DEMO_QR_DATA_URL,
    }


@app.post("/api/v1/virtual-nodes/toggle")
@app.post("/v1/virtual-nodes/toggle")
async def toggle_virtual_nodes():
    return {"status": "ok", "active": True, "mode": "cloud_showcase"}


@app.post("/api/v1/downloads")
@app.post("/v1/downloads")
async def start_download():
    return {"status": "ok", "message": "Cloud showcase simulation active"}


@app.post("/api/v1/nodes/{node_id}/limits")
@app.post("/v1/nodes/{node_id}/limits")
async def update_node_limits(node_id: str):
    return {"status": "ok", "node_id": node_id}


@app.post("/api/v1/nodes/{node_id}/status")
@app.post("/v1/nodes/{node_id}/status")
async def update_node_status(node_id: str):
    return {"status": "ok", "node_id": node_id}


@app.delete("/api/v1/nodes/{node_id}")
@app.delete("/v1/nodes/{node_id}")
async def evict_node(node_id: str):
    return {"status": "ok", "node_id": node_id}


# 3. Static Assets & Catch-all route
@app.get("/{full_path:path}")
async def serve_static_or_fallback(full_path: str):
    file_match = find_frontend_file(full_path)
    if file_match:
        mime_type, _ = mimetypes.guess_type(str(file_match))
        return FileResponse(file_match, media_type=mime_type or "application/octet-stream")

    return HTMLResponse(content=get_index_html())

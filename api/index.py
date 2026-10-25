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


# 2. API Endpoints
@app.get("/api/v1/pairing-qr")
async def get_pairing_qr():
    return {
        "status": "ok",
        "session_token": "bn_demo_84920481",
        "ssid": "BoostNet-College-Hotspot",
        "password": "boostnet2026",
        "pairing_uri": "boostnet://pair?token=bn_demo_84920481&host=192.168.137.1&port=9050",
        "qr_image_data_url": "",
    }


@app.post("/api/v1/virtual-nodes/toggle")
async def toggle_virtual_nodes():
    return {"status": "ok", "active": True, "mode": "cloud_showcase"}


@app.post("/api/v1/downloads")
async def start_download():
    return {"status": "ok", "message": "Cloud showcase simulation active"}


# 3. Static Assets & Catch-all route
@app.get("/{full_path:path}")
async def serve_static_or_fallback(full_path: str):
    file_match = find_frontend_file(full_path)
    if file_match:
        mime_type, _ = mimetypes.guess_type(str(file_match))
        return FileResponse(file_match, media_type=mime_type or "application/octet-stream")

    return HTMLResponse(content=get_index_html())

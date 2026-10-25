"""BoostNet Cloud Showcase API for Vercel Serverless.

Serves the PairDrop-inspired AMOLED frontend and mock telemetry endpoints for
the online live demo. Real multi-phone SOCKS5 bonding runs locally on the user's laptop.
"""

from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="BoostNet Bandwidth Aggregation Engine",
    description="Multi-Mobile Bandwidth Aggregation Cloud Showcase",
    version="2.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>BoostNet Engine Active</h1>")


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

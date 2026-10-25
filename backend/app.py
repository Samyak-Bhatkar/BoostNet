"""BoostNet Control Plane & Telemetry Server.

FastAPI Application providing:
- Zero-Config QR Pairing Handshake (/api/v1/pairing-qr & /api/v1/nodes/register)
- Node Registry & Donor Trust Controls (/api/v1/nodes)
- Approach A Turbo Download Engine (/api/v1/downloads)
- Media Stream Accelerator (/api/v1/stream-proxy)
- Approach B Session Proxy Matrix (/api/v1/sessions)
- 1-Click Virtual Mobile Node Cluster (/api/v1/virtual-nodes/toggle)
- High-Performance WebSocket Telemetry (/ws/telemetry)
"""

from __future__ import annotations
import asyncio
import base64
import io
import logging
from pathlib import Path
import socket
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import qrcode

from backend.config import (
    CONTROL_HOST,
    CONTROL_PORT,
    DOWNLOADS_DIR,
    FRONTEND_DIR,
    SESSION_TOKEN,
    WIFI_PASSWORD,
    WIFI_SSID,
)
from backend.engine.chunk_downloader import chunk_downloader
from backend.engine.congestion_detector import congestion_detector
from backend.engine.node_manager import NodeStatus, PhoneNode, node_manager
from backend.engine.session_proxy import session_proxy
from backend.engine.stream_accelerator import stream_accelerator
from backend.simulator.virtual_nodes import virtual_cluster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("boostnet.app")

app = FastAPI(
    title="BoostNet Bandwidth Aggregation Engine",
    description="Multi-Mobile Bandwidth Aggregation & Acceleration System for College Laptops (UN SDG 9)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_laptop_local_ip() -> str:
    """Detects laptop's active local Wi-Fi or LAN IP address."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            # Does not send actual packets; resolves local routing interface
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"


# --- Pydantic Request Models ---
class NodeRegistrationRequest(BaseModel):
    token: str
    device_name: str = Field(..., examples=["Rahul's Moto G45"])
    carrier: str = Field(..., examples=["Airtel 5G"])
    socks_port: int = Field(default=1080, ge=1024, le=65535)
    data_cap_mb: float = Field(default=250.0, ge=10.0)
    battery_level: int = Field(default=85, ge=0, le=100)
    battery_cutoff_pct: int = Field(default=25, ge=5, le=50)
    accent_color: Optional[str] = None


class NodeStatusUpdateRequest(BaseModel):
    status: NodeStatus


class NodeLimitsUpdateRequest(BaseModel):
    data_cap_mb: Optional[float] = None
    battery_cutoff_pct: Optional[int] = None


class StartDownloadRequest(BaseModel):
    url: str
    filename: Optional[str] = None
    expected_sha256: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


# --- Pairing & Registration Endpoints ---
@app.get("/api/v1/pairing-qr")
async def get_pairing_qr(ssid: Optional[str] = None, password: Optional[str] = None):
    """Generates the PairDrop-inspired pairing URI and dark-mode QR code."""
    laptop_ip = get_laptop_local_ip()
    use_ssid = ssid or WIFI_SSID
    use_pass = password or WIFI_PASSWORD

    params = urlencode({
        "ssid": use_ssid,
        "pass": use_pass,
        "host": laptop_ip,
        "port": CONTROL_PORT,
        "token": SESSION_TOKEN,
    })
    pairing_uri = f"boostnet://pair?{params}"

    # Render dark-mode friendly Emerald on Pure Black QR code
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(pairing_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#10b981", back_color="#000000")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "pairing_uri": pairing_uri,
        "ssid": use_ssid,
        "password": use_pass,
        "laptop_ip": laptop_ip,
        "control_port": CONTROL_PORT,
        "session_token": SESSION_TOKEN,
        "qr_image_data_url": f"data:image/png;base64,{qr_b64}",
    }


@app.post("/api/v1/nodes/register")
async def register_node(payload: NodeRegistrationRequest, request: Request):
    """Handshake called automatically by Android app after scanning QR."""
    if payload.token != SESSION_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid session token PIN")

    # Extract phone's IP from TCP socket
    phone_ip = request.client.host if request.client else "127.0.0.1"
    node_id = f"{phone_ip}:{payload.socks_port}"

    # Default accent color palette
    existing_count = len(node_manager.get_all_nodes())
    palette = ["#06b6d4", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899", "#3b82f6"]
    color = payload.accent_color or palette[existing_count % len(palette)]

    node = await node_manager.register_node(
        node_id=node_id,
        device_name=payload.device_name,
        carrier=payload.carrier,
        host=phone_ip,
        port=payload.socks_port,
        accent_color=color,
        data_cap_mb=payload.data_cap_mb,
        battery_level=payload.battery_level,
        battery_cutoff_pct=payload.battery_cutoff_pct,
        is_virtual=False,
    )

    return {
        "status": "paired",
        "assigned_node_id": node.node_id,
        "laptop_ip": get_laptop_local_ip(),
        "device_name": node.device_name,
    }


# --- Node Management Endpoints ---
@app.get("/api/v1/nodes")
async def list_nodes():
    return node_manager.get_telemetry_snapshot()


@app.post("/api/v1/nodes/{node_id:path}/status")
async def update_node_status(node_id: str, payload: NodeStatusUpdateRequest):
    await node_manager.set_node_status(node_id, payload.status)
    return {"status": "ok", "node_id": node_id, "new_status": payload.status.value}


@app.post("/api/v1/nodes/{node_id:path}/limits")
async def update_node_limits(node_id: str, payload: NodeLimitsUpdateRequest):
    await node_manager.update_node_limits(
        node_id, payload.data_cap_mb, payload.battery_cutoff_pct
    )
    return {"status": "ok", "node_id": node_id}


@app.delete("/api/v1/nodes/{node_id:path}")
async def evict_node(node_id: str):
    await node_manager.remove_node(node_id)
    return {"status": "evicted", "node_id": node_id}


# --- Approach A: Turbo Range Downloader Endpoints ---
@app.post("/api/v1/downloads")
async def create_download(req: StartDownloadRequest):
    task = await chunk_downloader.start_download(
        url=req.url,
        filename=req.filename,
        expected_sha256=req.expected_sha256,
        headers=req.headers,
    )
    return chunk_downloader.get_task_telemetry(task)


@app.get("/api/v1/downloads")
async def list_downloads():
    return [
        chunk_downloader.get_task_telemetry(task)
        for task in chunk_downloader.tasks.values()
    ]


@app.get("/api/v1/downloads/{task_id}")
async def get_download_status(task_id: str):
    task = chunk_downloader.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return chunk_downloader.get_task_telemetry(task)


# --- Approach B: Session Proxy Telemetry ---
@app.get("/api/v1/sessions")
async def get_proxy_sessions():
    return {
        "proxy_port": session_proxy.port,
        "proxy_host": session_proxy.host,
        "sessions": session_proxy.get_active_sessions_telemetry(),
    }


@app.get("/api/v1/congestion")
async def get_congestion_status():
    return congestion_detector.get_status()


# --- Media Stream Accelerator ---
@app.get("/api/v1/stream-resolve")
async def resolve_stream(url: str):
    return await stream_accelerator.resolve_media_url(url)


@app.get("/api/v1/stream-proxy")
async def stream_proxy(url: str, start: int = 0):
    resolved = await stream_accelerator.resolve_media_url(url)
    direct_url = resolved["direct_url"]

    generator = stream_accelerator.stream_media_generator(direct_url, start_byte=start)
    return StreamingResponse(
        generator,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


# --- Virtual Node Cluster Controls (1-Click Test Lab) ---
@app.post("/api/v1/virtual-nodes/toggle")
async def toggle_virtual_cluster():
    """1-Click button on PairDrop UI to spawn or tear down 3 virtual mobile nodes."""
    if virtual_cluster.is_active:
        await virtual_cluster.stop_cluster()
        return {"status": "inactive", "message": "Virtual mobile cluster stopped"}
    else:
        await virtual_cluster.start_cluster()
        return {"status": "active", "message": "3 Virtual mobile nodes spawned"}


@app.post("/api/v1/virtual-nodes/chaos-kill")
async def chaos_kill_node(node_id: str):
    """Simulates mid-download phone disconnect."""
    await virtual_cluster.kill_node(node_id)
    return {"status": "killed", "node_id": node_id}


@app.post("/api/v1/virtual-nodes/restart")
async def restart_virtual_node(node_id: str):
    await virtual_cluster.restart_node(node_id)
    return {"status": "restarted", "node_id": node_id}


@app.get("/api/v1/virtual-nodes/status")
async def get_virtual_cluster_status():
    return {
        "is_active": virtual_cluster.is_active,
        "nodes": [
            {
                "node_id": cfg.node_id,
                "device_name": cfg.device_name,
                "carrier": cfg.carrier,
                "bandwidth_mbps": round((cfg.bandwidth_bytes_per_sec * 8) / 1_000_000, 2),
                "latency_ms": cfg.latency_ms,
                "data_cap_mb": cfg.data_cap_mb,
                "accent_color": cfg.accent_color,
            }
            for cfg in virtual_cluster.configs
        ],
    }


# --- WebSocket Telemetry Hub ---
active_websockets: List[WebSocket] = []


@app.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    node_queue = node_manager.subscribe()

    try:
        # Initial snapshot
        await websocket.send_json(node_manager.get_telemetry_snapshot())

        # Forward downloader progress
        def on_download_progress(data: Dict[str, Any]):
            asyncio.create_task(_broadcast_to_ws(websocket, data))

        chunk_downloader.register_callback(on_download_progress)

        while True:
            # Send live telemetry every 500ms
            telemetry = node_manager.get_telemetry_snapshot()
            telemetry["sessions"] = session_proxy.get_active_sessions_telemetry()
            telemetry["virtual_cluster_active"] = virtual_cluster.is_active
            telemetry["congestion"] = congestion_detector.get_status()

            # Active download summaries
            telemetry["downloads"] = [
                chunk_downloader.get_task_telemetry(t)
                for t in chunk_downloader.tasks.values()
                if t.status in ("DOWNLOADING", "PROBING", "PINNED_SINGLE_NODE")
            ]

            await websocket.send_json(telemetry)
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket client disconnected: {e}")
    finally:
        node_manager.unsubscribe(node_queue)
        if websocket in active_websockets:
            active_websockets.remove(websocket)


async def _broadcast_to_ws(ws: WebSocket, payload: Dict[str, Any]) -> None:
    try:
        await ws.send_json(payload)
    except Exception:
        pass


# Mount Frontend Assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

    @app.get("/")
    async def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>BoostNet Engine Active (Frontend loading...)</h1>")

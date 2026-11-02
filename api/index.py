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


DEMO_PAIRING_QR = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAhIAAAISAQAAAACxRhsSAAAFP0lEQVR4nO1dbY6jMAy1AWl+tjeYo9CbjfZIe4NylL0B/BwJ5JWdD2JKV9qlGXU77/2ghYSImifHX0lZ6CiG5vAQRBjDA/LwgDw8IA8PyMMD8vCAPDwgDw/I45nlwREd0cAd8WVipuGsxud5YSJaQnvorK0Blwc/xzE0B+9XYIynlkcvinG93gr1vzqyAzO/CdFJhPm8sFypte7ynL/lEJpjtxswRj15TFE78od8svx4n/WiqtLTTCKipxMrRSOC8n38cxxBc+juAIzxv8hjeguqNND2MhkdFw7ath/12pc8x98DY3wjeQyqSovD2YjZSqBtoUUrP8c/AGO8rjy6+HlSY3PKlycmUc3K/ZWIByYSorkjPbV+8oS/pcEYry6Pwdz3s87sOuV/jFGBEum839upGgR6yhfn/j/dbzmE5tjtBoxRS59KceU0qypdWIYzBT+KhvdP/fZpsSoW3x/vZQvw9PHyoBBgUv+INBolV+Wpze6qRV3USlvtjtzZcMV78YA86vFUlJ2nOZHwpPzT1uvJWiNPrSGo3LUBPN0APK3nR002yb+J2ZxCtGhDOwePSv0o6q+fLMOFifqfaqnS0kV1i/fiAXl8hT5dYQFT/aIJqGCpBltAv4WUlbXivXhAHrXkIT8sMzoFPckpq6+c1Ey/ulDRDLDD9Kb8THYs3ssG4Gk1faqQjGCfhmxpsEVNlZp6nQvrFfp0F+Bp1XmfCibapJ5P9VsiqzWYq5+MBMz7G4CntXgq6r0bIhMDd60h1aHEMFW77QeebgGeVuOpyMZJoqhFgxmayJqsUujTPwE8rRrnl+zvJ/c/xUrLLtF6DTdDn+4BPK0371NbHGJmSpuDkWqpKDMN0uSfjFTM+7cAT+vap1eb8kOeKU7+ad43BZp8qwjYp3cAnlblKRk2/n68Fk3YpE/Xa9CntwBPK/J0DtRLwdGUy8+ef+pc9oN9ugvwtNp6049xrTVdmHrRQj5bH6XXtDrVqBzr+fNaFOSj9gCeVsxHtUltFkZqqUqL/P56Df7+HsDTivFTcXT0NmtMo67+PuzTPwE8rcfTMUeZyCqh9TQtMI21pi55ivrT+wBPq8ZPKXv5qy2wZqti6Gq9lvohb7oFeFq5DkXKBFR0knIgIB5i1Ar1UvcBntbzo05ZgY45fh8oGteihENWqoif3gd4WtE+pZjfz/bpZpFUYcLGFX3IR90BeFprfRTHfSY6vzi6m7kXIu5/aTTVAlaTrvHXSKo2YH3ULsDT2vmouXD1U84/WwXpEFvXe/FePCCPinV97S3/itV7q1UQl/jDPr0P8LRiXEpxynn7dWXJumo/UNQVVyEftQfwtG4+qncF/DEQlXdBia5+GSHAvL8L8LSuPu2T5x8b1hxpWr23hqmwb899gKfV/P1edAOU6aybnWQ/Xjc+u9kbbQxbpsQdJh/2HA3GcIA87s77hrJO3xVNpSnf1aka4O9vAI7V/78TueaqU19/GlKmQ9g3Jbc++DmOoTl4vwJjPHl+XzGm9XlhpZSiSO2n8ilX3g99+rzvtnnR/U/7dbOTTTl0SpQWvlVRp/osv6XBGN9JHgszv2twKm15bv8oYUtT+JK3m6r/HH8NjPG68uhuL7Uz6TanEjY61z896X/qJqi2+bmFBEaNCEwd8vvP/W6bF/6/E9EDhy16Q+00kQzndmbrO7zPesfSyXCxLo96jgZjOEAeu/ZpRFuUQ6csVN5xYi1C1fMQ8Yd9ugNw7PHyYP/XJf+CAe/FA/LwgDw8IA8PyMMD8vCAPDwgDw/Iw+OV5PEb2JUtEaGLJ3MAAAAASUVORK5CYII="
DEMO_WIFI_QR = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAZoAAAGaAQAAAAAefbjOAAADI0lEQVR4nO1cS46jQAy1Q6QsQZoD5ChwgzlSq4/UNwhH6RvAMhKRR/4UkJlFdylMo6TeW6CCYHXFZdnPnzQLZaM/5MsQQSgARQSgiAAUEYAiAlBEAIp4JkVw4EhEY1y404uCaEwvdLtsLxMQ2kARrSgGIu7qKzM3SiAbIpGhEu6oss8TC4XKC1DEmByA2cGlvjK1MhHz+cr2QniQnbaXBQg9oojjP0/Gk1A7kFDP1ST9byKh8f4VqLwgRYi5h765MZGu/t9f+hYgtJuPqJUjqCtoP4/E7edJ2BwFUeXsYV3Jwjm9viJ6yyQaZZbJBDzheFMD6ejmqcZe28sDhB73EbI86JvKiYMQXVPoMA+yACp/eUWw1xm0FNEOSiHILuotxpPIu6YZ6kZ22l4mIPSIIsgLDTIYqZy0AKFkwm6NaM4vajLq716g8sCrW4QMRiEqsdOP1WDFqWn9MiyihCr2OVWj3BgsfthKS5jBNmfK+RTfKRMQSvDqdOuOQv2BO4rl00lDx+I84CMKMaPxuG5pRMCIorYRzaAaO20vCxDagkcY1D04gVRvoZ4hVrU2uYx3KsAjiogakxUuPTh4mmF80gxELSI9g0WUEzXk4vWIaI5rrUr8mYK7enqy75QFCN37CIPZgWM+faeSyUeAWZZjRrUaw8iJQKrLsKjhXVDta3QeU/bZXhYgtAGPoJk7mj9YUlAPInOagezz5W2PgizS3enPpNKfmb3MBAO5RhG5xnDHKCLrsFXknLCI8iZmOFYDcfuhN/UQQ3ZEt2PqkP/s9g4Q2jX7rKP3Ke9nIxP2iTFLH5zQqex9tpcFCG3FLNvU11jziPtIAh5RiO3JPB/BrOlm77/l0YAxsvZDE4/YZ3uZgNDjPILjrpqExoa4HZoYrfNO1/hrop7BI4rshl98RP+v7lfEFESNorJPmuelVpMS4BFPfLiH7YT6NFIlF+URXsycs47dt/cFILSpIvrl552rIe2T8BuYZalTdZSq2GkaNxUzY4UqdhH1CMcyYpkmp+ZeB2aoChFi/GeypzinA4QcUEQAighAEQEoIgBFBH5OEX8A1bBlBXeX1ToAAAAASUVORK5CYII="
DEMO_QR_DATA_URL = DEMO_PAIRING_QR


# 2. API Endpoints
@app.get("/api/v1/pairing-qr")
@app.get("/v1/pairing-qr")
async def get_pairing_qr():
    return {
        "status": "ok",
        "session_token": "bn_demo_84920481",
        "ssid": "BoostNet-College-Hotspot",
        "password": "boostnet2026",
        "pairing_uri": "boostnet://pair?ssid=BoostNet-College-Hotspot&pass=boostnet2026&host=192.168.137.1&port=9051&token=bn_demo_84920481",
        "wifi_uri": "WIFI:T:WPA;S:BoostNet-College-Hotspot;P:boostnet2026;;",
        "qr_image_data_url": DEMO_PAIRING_QR,
        "wifi_qr_image_data_url": DEMO_WIFI_QR,
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

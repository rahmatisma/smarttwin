"""Local demo server: python -m uvicorn app.replay_demo:app --app-dir backend --port 8001"""
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.auth import require_operator
from app.core.config import settings
from app.services.replay_demo_service import replay_demo_service, ReplayDemoController


@asynccontextmanager
async def lifespan(app):
    yield
    replay_demo_service.stop()


app = FastAPI(title="SmartTwin SUMO Replay Demo", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])


class SourceRequest(BaseModel):
    offline: list[Literal["north", "east", "south", "west"]]
    ageSeconds: Literal[60, 300, 900] = 300
    trigger: bool = False


@app.get("/state")
def state():
    return replay_demo_service.state()


@app.post("/start", dependencies=[Depends(require_operator)])
def start():
    try:
        return replay_demo_service.start()
    except Exception as exc:
        raise HTTPException(503, f"SUMO demo gagal dimulai: {exc}") from exc


@app.post("/sources", dependencies=[Depends(require_operator)])
def sources(request: SourceRequest):
    try:
        return replay_demo_service.set_sources(request.offline, request.ageSeconds, request.trigger)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/stop", dependencies=[Depends(require_operator)])
def stop():
    return replay_demo_service.stop()


@app.get("/frame")
def frame():
    path = ReplayDemoController.PROJECT_ROOT / "cache" / "simulation" / "frame_replay-demo.jpg"
    if not path.exists():
        raise HTTPException(404, "Menunggu frame SUMO.")
    try:
        return Response(path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    except OSError as exc:
        raise HTTPException(503, "Frame sedang diperbarui.") from exc

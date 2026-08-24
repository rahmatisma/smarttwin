from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from app.services.traffic_service import (
    TrafficService,
    TrafficServiceError,
)

from app.schemas.traffic_response import (
    TrafficDetailResponse,
    TrafficListResponse,
)

from app.services.ws_manager import (
    traffic_ws_manager,
)

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/v1/traffic",
    tags=["Traffic"],
)

legacy_router = APIRouter(
    prefix="/api/traffic",
    tags=["Traffic"],
)

traffic_service = TrafficService()


# ============================================================
# LIVE TRAFFIC
# ============================================================

@router.get("/live-csv")
def get_live_csv(
    video_time: float | None = Query(
        default=None,
    ),
):
    """
    Mengambil traffic state terbaru dari Supabase.

    Flow:

        Supabase
            ↓
        TrafficStateBuilder
            ↓
        BuiltTrafficState
            ↓
        Frontend / SUMO

    Tidak membaca CSV.

    Tidak menjalankan LSTM.

    Tidak membutuhkan koneksi SUMO.
    """

    try:

        # ----------------------------------------------------
        # BUILDER
        # ----------------------------------------------------

        builder = TrafficStateBuilder(
            TrafficStateBuilderConfig(
                windowSeconds=5,
            )
        )

        # ----------------------------------------------------
        # BUILD DARI SUPABASE
        # ----------------------------------------------------

        states = (
            builder.buildFromSupabase(
                intersectionId="simpang4-pingit",
                limit=1,
                save=True,
            )
        )

        # ----------------------------------------------------
        # NO DATA
        # ----------------------------------------------------

        if not states:

            return {
                "success": True,
                "data": None,
                "timestamp": None,
                "requestedVideoTime": video_time,
                "source": "supabase",
                "message": (
                    "Belum ada traffic state "
                    "yang memiliki trafficLaneMetrics."
                ),
            }

        # ----------------------------------------------------
        # LATEST STATE
        # ----------------------------------------------------

        latest_state = states[-1]

        return {
            "success": True,

            "data": latest_state.model_dump(
                mode="json"
            ),

            "timestamp": (
                latest_state.windowEnd.isoformat()
            ),

            "requestedVideoTime": video_time,

            "source": "supabase",
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================
# GET LATEST TRAFFIC
# ============================================================

@router.get(
    "/{intersectionId}",
    response_model=TrafficListResponse,
)
def get_latest_traffic(
    intersectionId: str,

    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
):

    """
    Mengambil traffic state terbaru
    untuk satu intersection.

    Endpoint ini membaca:

        TrafficService
            ↓
        Repository
            ↓
        Supabase
    """

    try:

        data = (
            traffic_service
            .get_latest_traffic(
                intersection_id=
                    intersectionId,
                limit=limit,
            )
        )

        return {
            "success": True,

            "intersectionId":
                intersectionId,

            "count":
                len(data),

            "data":
                data,
        }

    except TrafficServiceError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


# ============================================================
# REALTIME TRAFFIC WEBSOCKET
# ============================================================

@router.websocket("/ws")
async def traffic_websocket(
    websocket: WebSocket,
) -> None:

    await traffic_ws_manager.connect(
        websocket
    )

    try:

        while True:

            await websocket.receive_text()

    except WebSocketDisconnect:

        traffic_ws_manager.disconnect(
            websocket
        )

    except Exception:

        traffic_ws_manager.disconnect(
            websocket
        )


# ============================================================
# NOTIFY TRAFFIC UPDATE
# ============================================================

@router.post("/notify")
async def notify_traffic_update(
    payload: dict[str, Any],
) -> dict[str, str]:

    await traffic_ws_manager.broadcast(
        payload
    )

    return {
        "status": "broadcast"
    }


# ============================================================
# GET ONE TRAFFIC STATE
# ============================================================

@router.get(
    "/{intersectionId}/states/{trafficStateId}",
    response_model=TrafficDetailResponse,
)
def get_traffic_state(
    intersectionId: str,
    trafficStateId: int,
):

    """
    Mengambil satu traffic state lengkap.
    """

    try:

        data = (
            traffic_service
            .get_traffic_state(
                intersection_id=
                    intersectionId,

                traffic_state_id=
                    trafficStateId,
            )
        )

        if data is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Traffic state "
                    "tidak ditemukan."
                ),
            )

        return {
            "success": True,

            "intersectionId":
                intersectionId,

            "data":
                data,
        }

    except TrafficServiceError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


# ============================================================
# LEGACY ROUTES
# ============================================================

legacy_router.add_api_route(
    "/{intersectionId}",
    get_latest_traffic,
    methods=["GET"],
)

legacy_router.add_api_route(
    "/{intersectionId}/states/{trafficStateId}",
    get_traffic_state,
    methods=["GET"],
)

legacy_router.add_api_websocket_route(
    "/ws",
    traffic_websocket,
)

legacy_router.add_api_route(
    "/notify",
    notify_traffic_update,
    methods=["POST"],
)
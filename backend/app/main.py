import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.traffic import (
    router as traffic_router,
    legacy_router as traffic_legacy_router,
)

from app.api.routes.cctv import (
    close_hf_client,
    router as cctv_router,
)

from app.api.routes.signal import router as signal_router
from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.simulation import router as simulation_router
from app.api.routes.health import router as health_router


logger = logging.getLogger("uvicorn.error")


# =========================================================
# FORECAST ROUTER
# =========================================================
#
# Forecast/LSTM sengaja dibuat optional.
#
# Alasannya:
# - backend traffic tetap harus bisa start
# - CCTV tetap harus bisa start
# - signal tetap harus bisa start
# - recommendation tetap harus bisa start
# - simulation tetap harus bisa start
#
# Kalau dependency/model forecast bermasalah,
# hanya endpoint /api/forecast/* yang tidak tersedia.
#
# =========================================================

forecast_router = None

try:
    from app.api.routes.forecast import router as forecast_router

    logger.info(
        "Forecast router berhasil dimuat."
    )

except Exception as exc:
    forecast_router = None

    logger.warning(
        "Forecast router gagal dimuat. "
        "Endpoint /api/forecast/* tidak tersedia. "
        "Endpoint backend lainnya tetap berjalan. "
        "Error: %s",
        exc,
    )


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="SmartTwin Backend",
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# =========================================================
# ROUTERS
# =========================================================

# Traffic
app.include_router(traffic_router)

app.include_router(traffic_legacy_router)


# CCTV
app.include_router(cctv_router)


# Traffic Signal
app.include_router(signal_router)


# Recommendation
app.include_router(recommendation_router)


# SUMO / Simulation
app.include_router(simulation_router)


# Health
app.include_router(health_router)


# Forecast / LSTM
#
# Hanya dimasukkan kalau import berhasil.
#
if forecast_router is not None:
    app.include_router(forecast_router)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():
    return {
        "service": "SmartTwin Backend",
        "status": "running",
    }


# =========================================================
# SHUTDOWN
# =========================================================

@app.on_event("shutdown")
async def shutdown_hf_client():
    await close_hf_client()
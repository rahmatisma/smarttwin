import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

    # Chrome mengirim Access-Control-Request-Private-Network di preflight
    # saat halaman publik (localhost dianggap begitu di beberapa konteks)
    # mengakses alamat privat (127.0.0.1). Tanpa ini, preflight ditolak
    # 400 total -- bukan cuma PNA yang gagal, SEMUA request ke backend
    # dari browser (termasuk yang lama, bukan cuma /recommendation).
    allow_private_network=True,
)


# =========================================================
# GLOBAL EXCEPTION HANDLER
# =========================================================
#
# Exception yang tidak tertangkap di route/service (mis. koneksi
# Supabase putus sesaat -- httpx.RemoteProtocolError) sebelumnya lolos
# ke ServerErrorMiddleware bawaan Starlette, yang berada DI LUAR
# CORSMiddleware -- jadi response 500-nya tidak pernah dapat header
# CORS. Browser lalu melaporkan ini sebagai "blocked by CORS policy"
# yang membingungkan, padahal akar masalahnya cuma error 500 biasa.
#
# Handler ini membuat FastAPI's ExceptionMiddleware (yang ada DI DALAM
# CORSMiddleware) yang menangkap exception-nya, jadi response error
# tetap lewat CORSMiddleware dan dapat header yang benar.
@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unhandled exception saat memproses %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
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
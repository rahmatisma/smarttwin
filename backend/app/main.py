import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Harus dilakukan sebelum import routes/services karena singleton decision
# engine dibuat ketika modul service di-import.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings

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
from app.api.routes.history import router as history_router
from app.api.routes.digital_twin import router as digital_twin_router
from app.services.simulation_service import simulation_service


logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        # Tutup thread/TraCI lebih dahulu agar proses SUMO tidak tertinggal,
        # baru tutup koneksi HTTP eksternal.
        simulation_service.stop()
        await close_hf_client()


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
    lifespan=lifespan,
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=settings.cors_origins_list,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
    
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],

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

# Scenario Generator / Digital Twin comparison
app.include_router(digital_twin_router)


# Riwayat keputusan
app.include_router(history_router)


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
async def shutdown_services():
    # Tutup thread/TraCI lebih dahulu supaya process SUMO tidak tertinggal
    # setelah Ctrl+C, baru tutup koneksi HTTP eksternal.
    simulation_service.stop_all()
    await close_hf_client()

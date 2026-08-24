import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.traffic import (
    router as traffic_router,
    legacy_router as traffic_legacy_router,
)
from app.api.routes.cctv import close_hf_client, router as cctv_router
from app.api.routes.signal import router as signal_router
from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.simulation import router as simulation_router
from app.api.routes.health import router as health_router

logger = logging.getLogger("uvicorn.error")

# forecast_router SENGAJA dibungkus try/except -- fitur LSTM ini masih
# aktif berkembang (dependency baru/modul baru bisa muncul kapan saja)
# dan sudah 3x malam ini (25 Agustus 2026) bikin backend gagal start
# TOTAL gara-gara satu import di sini rusak, mematikan endpoint
# cctv/traffic/signal/simulation yang tidak ada hubungannya sama
# sekali. Kalau forecast_router gagal di-import, backend tetap nyala
# normal dengan endpoint lain -- cuma /api/forecast/* yang hilang,
# bukan seluruh backend. Cek log start-up (baris "forecast_router
# gagal dimuat") kalau /api/forecast/* ternyata 404.
try:
    from app.api.routes.forecast import router as forecast_router
except Exception as exc:  # noqa: BLE001
    forecast_router = None
    logger.warning(
        "forecast_router gagal dimuat, /api/forecast/* tidak tersedia "
        "(endpoint lain tetap jalan normal): %s",
        exc,
    )

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

app.include_router(traffic_router)
app.include_router(traffic_legacy_router)
app.include_router(cctv_router)
app.include_router(signal_router)
app.include_router(recommendation_router)
app.include_router(simulation_router)
app.include_router(health_router)
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
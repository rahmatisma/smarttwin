from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.traffic import router as traffic_router
from app.api.routes.cctv import close_hf_client, router as cctv_router
from app.api.routes.signal import router as signal_router
from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.simulation import router as simulation_router
from app.api.routes.health import router as health_router
# from app.api.routes.forecast import router as forecast_router

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
app.include_router(cctv_router)
app.include_router(signal_router)
app.include_router(recommendation_router)
app.include_router(simulation_router)
app.include_router(health_router)
# app.include_router(forecast_router)


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
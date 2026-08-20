from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.traffic import router as traffic_router


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

app.include_router(
    traffic_router
)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
def root():
    return {
        "message": "SmartTwin Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }
from fastapi import APIRouter

from app.core.config import settings
from app.services.simulation_service import simulation_service
from app.services.recommendation_service import recommendation_service


router = APIRouter(
    prefix="/api/v1/health",
    tags=["Health"],
)


@router.get("")
def health_check():
    return {
        "status": "ok",
        "service": "smarttwin-backend",
    }


@router.get("/details")
def detailed_health_check():
    """Readiness lokal tanpa memaksa koneksi atau loading model eksternal."""
    engine = recommendation_service.engine
    is_ppo = engine.__class__.__name__ == "PPOEngine"

    try:
        from app.services.forecast_service import forecast_service

        forecast = forecast_service.health()
    except Exception as exc:
        forecast = {"available": False, "error": type(exc).__name__}

    simulation = simulation_service.get_simulation_state()
    return {
        "status": "ok",
        "service": "smarttwin-backend",
        "auth": {
            "required": settings.auth_required,
            "operatorRoles": sorted(settings.operator_roles_list),
        },
        "forecast": forecast,
        "decisionEngine": {
            "active": engine.__class__.__name__,
            "ppoAvailable": bool(getattr(engine, "available", False)) if is_ppo else False,
            "fallbackEnabled": is_ppo,
            "loadError": getattr(engine, "load_error", None) if is_ppo else None,
        },
        "simulation": {
            "running": simulation["running"],
            "paused": simulation["paused"],
            "scenario": simulation.get("scenario"),
            "seed": simulation.get("seed"),
            "startedAt": simulation.get("startedAt"),
        },
    }

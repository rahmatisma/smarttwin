from fastapi import APIRouter, Depends
import os
from pathlib import Path

from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.recommendation_service import recommendation_service
from app.core.auth import get_current_user, require_operator


router = APIRouter(
    prefix="/recommendation",
    tags=["Recommendation"],
)
from app.schemas.traffic import TrafficState


@router.get("/engine-status")
def get_decision_engine_status():
    """Diagnostik PPO yang tidak bergantung pada Supabase atau traffic live."""
    engine = recommendation_service.engine
    is_ppo = engine.__class__.__name__ == "PPOEngine"
    model_path = getattr(engine, "model_path", None)
    return {
        "configuredMode": os.getenv("SMARTTWIN_DECISION_ENGINE", "rule-based"),
        "activeEngine": engine.__class__.__name__,
        "ppoAvailable": bool(getattr(engine, "available", False)) if is_ppo else False,
        "fallbackEnabled": is_ppo,
        "modelFile": Path(model_path).name if model_path else None,
        "loadError": getattr(engine, "load_error", None) if is_ppo else None,
    }


@router.post("/engine-test", dependencies=[Depends(require_operator)])
def test_decision_engine(
    state: TrafficState,
    currentPhase: str = "north",
    currentGreenSeconds: int = 30,
):
    """Inferensi read-only dari TrafficState langsung untuk verifikasi pre-demo."""
    engine = recommendation_service.engine
    recommendation = engine.recommend(
        state,
        currentPhase=currentPhase,
        currentGreenSeconds=currentGreenSeconds,
    )
    cycle = engine.recommend_cycle(state, currentPhase=currentPhase)
    dump = lambda value: value.model_dump() if hasattr(value, "model_dump") else value.__dict__
    return {
        "success": True,
        "recommendation": dump(recommendation),
        "cyclePlan": dump(cycle),
    }


@router.post(
    "",
    response_model=RecommendationResponse,
    dependencies=[Depends(get_current_user)],
)
def get_recommendation(
    request: RecommendationRequest,
):
    return recommendation_service.get_recommendation(
        request
    )

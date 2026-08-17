from fastapi import APIRouter

from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.recommendation_service import recommendation_service


router = APIRouter(
    prefix="/recommendation",
    tags=["Recommendation"],
)


@router.post(
    "",
    response_model=RecommendationResponse,
)
def get_recommendation(
    request: RecommendationRequest,
):
    return recommendation_service.get_recommendation(
        request
    )
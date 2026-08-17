from pydantic import BaseModel, Field

from app.schemas.traffic import Approach


class ForecastPoint(BaseModel):
    approach: Approach

    horizonMinutes: int = Field(ge=0)

    predictedVolume: float = Field(ge=0)
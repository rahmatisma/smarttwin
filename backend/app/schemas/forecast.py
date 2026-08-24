from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.traffic import Approach

class ForecastPoint(BaseModel):
    approach: Approach
    horizonMinutes: int = Field(ge=0)
    predictedVolume: float = Field(ge=0)

class ForecastApproach(BaseModel):
    approach: str
    queueLengthVeh: float

class ForecastPrediction(BaseModel):
    predictionTime: datetime
    horizonSeconds: int
    approaches: list[ForecastApproach]

class ForecastResult(BaseModel):
    intersectionId: str
    generatedAt: datetime
    sourceWindowStart: datetime
    sourceWindowEnd: datetime
    modelName: str
    modelVersion: str
    predictions: list[ForecastPrediction]
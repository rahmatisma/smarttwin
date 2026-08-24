from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.traffic import Approach


class ForecastPoint(BaseModel):
    approach: Approach

    horizonMinutes: int = Field(ge=0)

    predictedVolume: float = Field(ge=0)


# ============================================================
# LSTM LIVE FORECAST (WIP -- lihat app/services/forecast_service.py)
# ============================================================
#
# Bentuk di bawah ini disalin persis dari cara forecast_service.py
# mengkonstruksi objeknya (per-approach breakdown per titik prediksi).
# CATATAN: frontend/src/types/traffic.ts punya ForecastResponse/
# ForecastPrediction dengan bentuk BERBEDA TOTAL (flat, tanpa
# breakdown per-approach, nama field juga beda). Belum direkonsiliasi
# -- ini cuma menutup ImportError yang bikin seluruh backend gagal
# start, bukan menyelesaikan desainnya.

class ForecastApproach(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    approach: Approach

    queueLengthVeh: float = Field(default=0.0, alias="queueLengthVeh", ge=0.0)


class ForecastPrediction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    predictionTime: datetime = Field(alias="predictionTime")

    horizonSeconds: int = Field(alias="horizonSeconds", ge=0)

    approaches: list[ForecastApproach]


class ForecastResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    intersectionId: str = Field(alias="intersectionId")

    generatedAt: datetime = Field(alias="generatedAt")

    sourceWindowStart: datetime = Field(alias="sourceWindowStart")
    sourceWindowEnd: datetime = Field(alias="sourceWindowEnd")

    modelName: str = Field(alias="modelName")
    modelVersion: str = Field(alias="modelVersion")

    predictions: list[ForecastPrediction]
from app.schemas.forecast import ForecastPoint
from app.schemas.traffic import Approach


def get_forecast() -> list[ForecastPoint]:
    return [
        ForecastPoint(
            approach=Approach.NORTH,
            horizonMinutes=0,
            predictedVolume=214,
        ),
        ForecastPoint(
            approach=Approach.SOUTH,
            horizonMinutes=0,
            predictedVolume=225,
        ),
        ForecastPoint(
            approach=Approach.EAST,
            horizonMinutes=0,
            predictedVolume=327,
        ),
        ForecastPoint(
            approach=Approach.WEST,
            horizonMinutes=0,
            predictedVolume=214,
        ),

        ForecastPoint(
            approach=Approach.NORTH,
            horizonMinutes=3,
            predictedVolume=227,
        ),
        ForecastPoint(
            approach=Approach.SOUTH,
            horizonMinutes=3,
            predictedVolume=239,
        ),
        ForecastPoint(
            approach=Approach.EAST,
            horizonMinutes=3,
            predictedVolume=347,
        ),
        ForecastPoint(
            approach=Approach.WEST,
            horizonMinutes=3,
            predictedVolume=227,
        ),
    ]
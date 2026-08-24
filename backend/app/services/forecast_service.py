from __future__ import annotations

from datetime import datetime, timedelta

from app.models.lstm_forecast import LSTMForecaster
from app.repositories.forecast_repository import (
    ForecastRepository,
)
from app.schemas.forecast import (
    ForecastPrediction,
    ForecastResult,
)


FEATURE_NAMES = [
    "totalDiZona",
    "motorDiZona",
    "mobilDiZona",
    "trukDiZona",
    "busDiZona",
]

INTERVAL_SECONDS = 5


class ForecastService:

    def __init__(
        self,
        forecaster: LSTMForecaster,
        repository: ForecastRepository,
    ):
        self.forecaster = forecaster
        self.repository = repository

    # =========================================================
    # FORECAST
    # =========================================================

    def forecast(
        self,
        intersectionId: str,
        horizonMinutes: int,
    ) -> ForecastResult:

        if horizonMinutes <= 0:
            raise ValueError(
                "horizonMinutes harus lebih besar dari 0."
            )

        states = (
            self.repository.getTrafficHistory(
                intersectionId=intersectionId,
                limit=self.forecaster.sequenceLength,
            )
        )

        if len(states) < self.forecaster.sequenceLength:
            raise ValueError(
                "Data traffic belum cukup untuk forecast. "
                f"Dibutuhkan "
                f"{self.forecaster.sequenceLength} timestep, "
                f"tersedia {len(states)}."
            )

        historyFeatures = [
            self._stateToFeatures(state)
            for state in states
        ]

        prediction = (
            self.forecaster.predict(
                historyFeatures
            )
        )

        if prediction.ndim == 3:
            prediction = prediction[0]

        if prediction.ndim != 2:
            raise ValueError(
                "Output LSTM tidak sesuai. "
                f"Shape: {prediction.shape}"
            )

        latestState = states[-1]

        generatedAt = self._parseDatetime(
            latestState["windowEnd"]
        )

        predictions = []

        maxSteps = min(
            len(prediction),
            horizonMinutes
            * 60
            // INTERVAL_SECONDS,
        )

        for index in range(maxSteps):

            values = prediction[index]

            predictionTime = (
                generatedAt
                + timedelta(
                    seconds=(
                        INTERVAL_SECONDS
                        * (index + 1)
                    )
                )
            )

            predictions.append(
                ForecastPrediction(
                    timestamp=predictionTime,
                    predictedVehicleCount=max(
                        0.0,
                        float(values[0]),
                    ),
                    predictedQueueLengthVeh=0.0,
                    predictedQueueLengthMEst=0.0,
                    predictedDensityIndex=0.0,
                    predictedSpeedKmh=None,
                )
            )

        return ForecastResult(
            intersectionId=intersectionId,
            horizonMinutes=horizonMinutes,
            model="LSTM",
            predictions=predictions,
        )

    # =========================================================
    # TRAFFIC STATE -> LSTM FEATURES
    # =========================================================

    def _stateToFeatures(
        self,
        state: dict,
    ) -> dict:

        total = 0.0
        motorcycle = 0.0
        car = 0.0
        truck = 0.0
        bus = 0.0

        for approach in state.get(
            "approaches",
            [],
        ):

            total += float(
                approach.get(
                    "volume",
                    0,
                ) or 0
            )

            motorcycle += float(
                approach.get(
                    "motorcycleCount",
                    0,
                ) or 0
            )

            car += float(
                approach.get(
                    "carCount",
                    0,
                ) or 0
            )

            truck += float(
                approach.get(
                    "truckCount",
                    0,
                ) or 0
            )

            bus += float(
                approach.get(
                    "busCount",
                    0,
                ) or 0
            )

        return {
            "totalDiZona": total,
            "motorDiZona": motorcycle,
            "mobilDiZona": car,
            "trukDiZona": truck,
            "busDiZona": bus,
        }

    # =========================================================
    # DATETIME
    # =========================================================

    def _parseDatetime(
        self,
        value,
    ) -> datetime:

        if isinstance(
            value,
            datetime,
        ):
            return value

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
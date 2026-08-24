from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model

from app.repositories.forecast_repository import (
    ForecastRepository,
)
from app.schemas.forecast import (
    ForecastPrediction,
    ForecastResult,
)


MODEL_DIR = Path(__file__).resolve().parents[2] / "models"

MODEL_PATH = MODEL_DIR / "lstm_model.keras"

SCALER_PATH = MODEL_DIR / "scaler.pkl"

SEQUENCE_LENGTH = 30

FEATURES = [
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
]


class RealtimeForecastService:

    def __init__(self) -> None:

        self.repository = ForecastRepository()

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model LSTM tidak ditemukan: {MODEL_PATH}"
            )

        if not SCALER_PATH.exists():
            raise FileNotFoundError(
                f"Scaler tidak ditemukan: {SCALER_PATH}"
            )

        self.model = load_model(
            MODEL_PATH,
            compile=False,
        )

        self.scaler = joblib.load(
            SCALER_PATH
        )

    # ========================================================
    # BUILD MINUTE DATA
    # ========================================================

    def _prepare_minute_data(
        self,
        rows: list[dict],
    ) -> pd.DataFrame:

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        df["windowStart"] = pd.to_datetime(
            df["windowStart"],
            utc=True,
        )

        # Aggregate seluruh approach menjadi
        # satu traffic state per intersection per menit.
        df["minute"] = (
            df["windowStart"]
            .dt.floor("min")
        )

        grouped = (
            df.groupby("minute")
            .agg(
                vehicleCount=(
                    "volume",
                    "sum",
                ),
                queueLengthVeh=(
                    "queueLengthVeh",
                    "sum",
                ),
                queueLengthMEst=(
                    "queueLengthMEst",
                    "max",
                ),
                densityIndex=(
                    "densityIndex",
                    "mean",
                ),
            )
            .reset_index()
        )

        return grouped

    # ========================================================
    # FORECAST
    # ========================================================

    def forecast(
        self,
        intersection_id: str,
        horizon_minutes: int,
    ) -> ForecastResult:

        rows = (
            self.repository
            .get_recent_traffic_states(
                intersection_id=intersection_id,
                minutes=90,
            )
        )

        df = self._prepare_minute_data(rows)

        if len(df) < SEQUENCE_LENGTH:
            raise ValueError(
                f"Data realtime tidak cukup. "
                f"Dibutuhkan minimal "
                f"{SEQUENCE_LENGTH} menit, "
                f"tersedia {len(df)} menit."
            )

        values = df[FEATURES].astype(float).values

        scaled = self.scaler.transform(values)

        sequence = scaled[
            -SEQUENCE_LENGTH:
        ].copy()

        predictions = []

        last_timestamp = df["minute"].iloc[-1]

        for step in range(
            1,
            horizon_minutes + 1,
        ):

            x = sequence.reshape(
                1,
                SEQUENCE_LENGTH,
                len(FEATURES),
            )

            prediction_scaled = (
                self.model.predict(
                    x,
                    verbose=0,
                )[0]
            )

            prediction_scaled = np.asarray(
                prediction_scaled
            ).reshape(1, -1)

            prediction = (
                self.scaler
                .inverse_transform(
                    prediction_scaled
                )[0]
            )

            vehicle_count = max(
                0.0,
                float(prediction[0]),
            )

            queue_length_veh = max(
                0.0,
                float(prediction[1]),
            )

            queue_length_m_est = max(
                0.0,
                float(prediction[2]),
            )

            density_index = min(
                1.0,
                max(
                    0.0,
                    float(prediction[3]),
                ),
            )

            predictions.append(
                ForecastPrediction(
                    timestamp=(
                        last_timestamp
                        + timedelta(
                            minutes=step
                        )
                    ),
                    predictedVehicleCount=vehicle_count,
                    predictedQueueLengthVeh=(
                        queue_length_veh
                    ),
                    predictedQueueLengthMEst=(
                        queue_length_m_est
                    ),
                    predictedDensityIndex=(
                        density_index
                    ),
                    predictedSpeedKmh=None,
                )
            )

            # autoregressive:
            # prediction sekarang menjadi input
            # untuk langkah berikutnya.
            sequence = np.concatenate(
                [
                    sequence[1:],
                    prediction_scaled,
                ],
                axis=0,
            )

        return ForecastResult(
            intersectionId=intersection_id,
            horizonMinutes=horizon_minutes,
            model="LSTM",
            predictions=predictions,
        )
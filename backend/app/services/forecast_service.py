from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from app.models.lstm_forecast import LSTMForecaster
from app.schemas.forecast import (
    ForecastPrediction,
    ForecastResult,
)
from app.schemas.traffic import TrafficState


# ============================================================
# PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

# Struktur project:
#
# smarttwin/
# ├── backend/
# │   └── app/
# │       └── services/
# │           └── forecast_service.py
# │
# └── forecasting/
#     └── outputs/
#         └── yolo/
#             ├── traffic_lstm.pt
#             ├── scaler.pkl
#             └── metadata.json
#
# parents[0] = services
# parents[1] = app
# parents[2] = backend
# parents[3] = smarttwin

PROJECT_ROOT = BASE_DIR.parent

FORECASTING_OUTPUT_DIR = (
    PROJECT_ROOT
    / "forecasting"
    / "outputs"
    / "yolo"
)

MODEL_PATH = (
    FORECASTING_OUTPUT_DIR
    / "traffic_lstm.pt"
)

SCALER_PATH = (
    FORECASTING_OUTPUT_DIR
    / "scaler.pkl"
)

METADATA_PATH = (
    FORECASTING_OUTPUT_DIR
    / "metadata.json"
)


# ============================================================
# LSTM CONTRACT
# ============================================================

FEATURE_NAMES = [
    "totalDiZona",
    "motorDiZona",
    "mobilDiZona",
    "trukDiZona",
    "busDiZona",
]

SEQUENCE_LENGTH = 12

INTERVAL_SECONDS = 5


# ============================================================
# FORECAST SERVICE
# ============================================================

class ForecastService:

    def __init__(
        self,
        forecaster: LSTMForecaster,
    ):
        self.forecaster = forecaster

        # History disimpan berdasarkan intersectionId.
        #
        # Contoh:
        #
        # {
        #     "intersection-001": [
        #         TrafficState(...),
        #         TrafficState(...),
        #         ...
        #     ]
        # }
        #
        self.history: dict[
            str,
            list[TrafficState],
        ] = {}

    # ========================================================
    # ADD TRAFFIC STATE
    # ========================================================

    def add_traffic_state(
        self,
        state: TrafficState,
    ) -> ForecastResult | None:

        intersection_id = state.intersectionId

        if intersection_id not in self.history:
            self.history[intersection_id] = []

        self.history[intersection_id].append(state)

        # Simpan sedikit history tambahan.
        max_history = (
            self.forecaster.sequence_length
            + 20
        )

        self.history[intersection_id] = (
            self.history[intersection_id][
                -max_history:
            ]
        )

        current_length = len(
            self.history[intersection_id]
        )

        required_length = (
            self.forecaster.sequence_length
        )

        # ====================================================
        # WARMING UP
        # ====================================================

        if current_length < required_length:

            print(
                "[FORECAST] History belum cukup: "
                f"{current_length}/{required_length}"
            )

            return None

        # ====================================================
        # RUN FORECAST
        # ====================================================

        return self._run_forecast(
            intersection_id
        )

    # ========================================================
    # CONVERT TRAFFIC STATE -> LSTM FEATURES
    # ========================================================

    def _state_to_features(
        self,
        state: TrafficState,
    ) -> dict:

        total_di_zona = 0.0
        motor_di_zona = 0.0
        mobil_di_zona = 0.0
        truk_di_zona = 0.0
        bus_di_zona = 0.0

        # TrafficState mempunyai beberapa approach.
        #
        # Setiap approach berasal dari hasil
        # TrafficStateBuilder.
        #
        # Kita agregasikan seluruh approach
        # menjadi satu timestep tingkat intersection.

        for approach in state.approaches:

            total_di_zona += float(
                approach.volume or 0
            )

            motor_di_zona += float(
                approach.motorcycleCount or 0
            )

            mobil_di_zona += float(
                approach.carCount or 0
            )

            truk_di_zona += float(
                approach.truckCount or 0
            )

            bus_di_zona += float(
                approach.busCount or 0
            )

        return {
            "totalDiZona": total_di_zona,
            "motorDiZona": motor_di_zona,
            "mobilDiZona": mobil_di_zona,
            "trukDiZona": truk_di_zona,
            "busDiZona": bus_di_zona,
        }

    # ========================================================
    # RUN LSTM FORECAST
    # ========================================================

    def _run_forecast(
        self,
        intersection_id: str,
    ) -> ForecastResult:

        states = self.history[
            intersection_id
        ]

        # ====================================================
        # BUILD HISTORY
        # ====================================================

        history_features = [
            self._state_to_features(state)
            for state in states
        ]

        # ====================================================
        # LSTM PREDICTION
        # ====================================================

        prediction = (
            self.forecaster.predict(
                history_features
            )
        )

        latest_state = states[-1]

        generated_at = (
            latest_state.windowEnd
        )

        # ====================================================
        # NORMALIZE OUTPUT SHAPE
        # ====================================================

        prediction_values = prediction

        #
        # Expected:
        #
        # [1, horizon, 5]
        #
        # menjadi:
        #
        # [horizon, 5]
        #

        if prediction_values.ndim == 3:
            prediction_values = (
                prediction_values[0]
            )

        #
        # Kalau:
        #
        # [5]
        #
        # menjadi:
        #
        # [[5]]
        #

        if prediction_values.ndim == 1:
            prediction_values = [
                prediction_values
            ]

        # ====================================================
        # BUILD FORECAST PREDICTIONS
        # ====================================================

        predictions = []

        for step_index, values in enumerate(
            prediction_values
        ):

            horizon_seconds = (
                INTERVAL_SECONDS
                * (step_index + 1)
            )

            prediction_time = (
                generated_at
                + timedelta(
                    seconds=horizon_seconds
                )
            )

            # Pastikan jumlah output sesuai
            # dengan lima feature LSTM.

            if len(values) < 5:
                raise ValueError(
                    "Output LSTM tidak memiliki "
                    "5 feature yang diperlukan. "
                    f"Output: {values}"
                )

            forecast = (
                ForecastPrediction(
                    predictionTime=(
                        prediction_time
                    ),
                    horizonSeconds=(
                        horizon_seconds
                    ),

                    totalDiZona=max(
                        0.0,
                        float(values[0]),
                    ),

                    motorDiZona=max(
                        0.0,
                        float(values[1]),
                    ),

                    mobilDiZona=max(
                        0.0,
                        float(values[2]),
                    ),

                    trukDiZona=max(
                        0.0,
                        float(values[3]),
                    ),

                    busDiZona=max(
                        0.0,
                        float(values[4]),
                    ),
                )
            )

            predictions.append(
                forecast
            )

        # ====================================================
        # RESULT
        # ====================================================

        result = ForecastResult(
            intersectionId=(
                intersection_id
            ),

            generatedAt=(
                generated_at
            ),

            sourceWindowStart=(
                latest_state.windowStart
            ),

            sourceWindowEnd=(
                latest_state.windowEnd
            ),

            modelName="LSTM",

            modelVersion="1.0",

            predictions=predictions,
        )

        # ====================================================
        # LOG
        # ====================================================

        print(
            "\n========== FORECAST =========="
        )

        print(
            result.model_dump_json(
                indent=2
            )
        )

        print(
            "==============================\n"
        )

        return result


# ============================================================
# CREATE LSTM FORECASTER
# ============================================================

print(
    "\n=========================================="
)

print(
    "[FORECAST] Initializing LSTM..."
)

print(
    "=========================================="
)

print(
    f"[FORECAST] Model   : {MODEL_PATH}"
)

print(
    f"[FORECAST] Scaler  : {SCALER_PATH}"
)

print(
    f"[FORECAST] Metadata: {METADATA_PATH}"
)

print(
    f"[FORECAST] Features: {FEATURE_NAMES}"
)

print(
    f"[FORECAST] Sequence: {SEQUENCE_LENGTH}"
)

print(
    "==========================================\n"
)


forecaster = LSTMForecaster(
    model_path=MODEL_PATH,
    scaler_path=SCALER_PATH,
    metadata_path=METADATA_PATH,
    feature_names=FEATURE_NAMES,
    sequence_length=SEQUENCE_LENGTH,
)


# ============================================================
# GLOBAL FORECAST SERVICE
# ============================================================

forecast_service = ForecastService(
    forecaster=forecaster
)
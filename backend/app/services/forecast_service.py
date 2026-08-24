from __future__ import annotations

from datetime import timedelta

from app.ml.lstm_forecaster import LSTMForecaster
from app.schemas.forecast import (
    ForecastApproach,
    ForecastPrediction,
    ForecastResult,
)
from app.schemas.traffic import (
    TrafficState,
)


class ForecastService:

    def __init__(
        self,
        forecaster: LSTMForecaster,
    ):
        self.forecaster = forecaster

        self.history: dict[
            str,
            list[TrafficState]
        ] = {}

    def add_traffic_state(
        self,
        state: TrafficState,
    ) -> ForecastResult | None:

        intersection_id = (
            state.intersectionId
        )

        if intersection_id not in self.history:
            self.history[
                intersection_id
            ] = []

        self.history[
            intersection_id
        ].append(state)

        max_history = (
            self.forecaster.sequence_length
            + 20
        )

        self.history[
            intersection_id
        ] = self.history[
            intersection_id
        ][-max_history:]

        if len(
            self.history[intersection_id]
        ) < self.forecaster.sequence_length:

            print(
                "[FORECAST] History belum cukup:"
                f" {len(self.history[intersection_id])}/"
                f"{self.forecaster.sequence_length}"
            )

            return None

        return self._run_forecast(
            intersection_id
        )

    def _state_to_features(
        self,
        state: TrafficState,
    ) -> dict:

        result = {}

        for approach in state.approaches:

            name = approach.approach.value

            result[name] = (
                approach.queueLengthVeh
                or 0
            )

        return result

    def _run_forecast(
        self,
        intersection_id: str,
    ) -> ForecastResult:

        states = self.history[
            intersection_id
        ]

        history_features = [
            self._state_to_features(state)
            for state in states
        ]

        prediction = (
            self.forecaster.predict(
                history_features
            )
        )

        latest_state = states[-1]

        generated_at = (
            latest_state.windowEnd
        )

        prediction_values = (
            prediction
        )

        if prediction_values.ndim == 3:

            prediction_values = (
                prediction_values[0]
            )

        if prediction_values.ndim == 1:

            prediction_values = [
                prediction_values
            ]

        predictions = []

        for step_index, values in enumerate(
            prediction_values
        ):

            prediction_time = (
                generated_at
                + timedelta(
                    seconds=5 * (
                        step_index + 1
                    )
                )
            )

            approaches = []

            for index, approach in enumerate(
                ["north", "south", "east", "west"]
            ):

                value = float(
                    values[index]
                )

                approaches.append(
                    ForecastApproach(
                        approach=approach,
                        queueLengthVeh=max(
                            0,
                            value,
                        ),
                    )
                )

            predictions.append(
                ForecastPrediction(
                    predictionTime=(
                        prediction_time
                    ),
                    horizonSeconds=(
                        5 * (step_index + 1)
                    ),
                    approaches=approaches,
                )
            )

        result = ForecastResult(
            intersectionId=(
                intersection_id
            ),
            generatedAt=generated_at,
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
    
FEATURE_NAMES = [
    "north",
    "south",
    "east",
    "west",
]


forecaster = LSTMForecaster(
    model_path="models/traffic_lstm.keras",
    feature_names=FEATURE_NAMES,
    sequence_length=15,
)


forecast_service = ForecastService(
    forecaster=forecaster,
)
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class ForecastOutput:
    values: np.ndarray


class LSTMForecaster:

    def __init__(
        self,
        model_path: str | Path,
        feature_names: list[str],
        sequence_length: int,
        scaler=None,
    ):
        self.model_path = Path(model_path)

        self.feature_names = feature_names

        self.sequence_length = sequence_length

        self.scaler = scaler

        self.model = None

        self._load_model()

    def _load_model(self):

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model tidak ditemukan: {self.model_path}"
            )

        from tensorflow.keras.models import load_model

        self.model = load_model(
            self.model_path
        )

        print(
            f"[LSTM] Loaded model: "
            f"{self.model_path}"
        )

    def prepare_sequence(
        self,
        history: list[dict],
    ) -> np.ndarray:

        if len(history) < self.sequence_length:
            raise ValueError(
                f"History membutuhkan "
                f"{self.sequence_length} timestep, "
                f"tetapi hanya tersedia "
                f"{len(history)}."
            )

        history = history[
            -self.sequence_length:
        ]

        values = []

        for row in history:

            timestep = []

            for feature in self.feature_names:

                value = row.get(
                    feature,
                    0,
                )

                if value is None:
                    value = 0

                timestep.append(
                    float(value)
                )

            values.append(timestep)

        array = np.asarray(
            values,
            dtype=np.float32,
        )

        if self.scaler is not None:

            original_shape = array.shape

            array = self.scaler.transform(
                array
            )

            array = array.reshape(
                original_shape
            )

        return np.expand_dims(
            array,
            axis=0,
        )

    def predict(
        self,
        history: list[dict],
    ) -> np.ndarray:

        sequence = self.prepare_sequence(
            history
        )

        prediction = self.model.predict(
            sequence,
            verbose=0,
        )

        prediction = np.asarray(
            prediction,
            dtype=np.float32,
        )

        if self.scaler is not None:

            prediction_shape = prediction.shape

            prediction = prediction.reshape(
                -1,
                len(self.feature_names),
            )

            prediction = self.scaler.inverse_transform(
                prediction
            )

            prediction = prediction.reshape(
                prediction_shape
            )

        return prediction
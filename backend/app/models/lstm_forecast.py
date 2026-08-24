from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class ForecastOutput:
    values: np.ndarray


class LSTMForecaster:

    def __init__(
        self,
        model_path: str | Path,
        scaler_path: str | Path,
        metadata_path: str | Path,
        feature_names: list[str],
        sequence_length: int,
    ):

        self.model_path = Path(
            model_path
        )

        self.scaler_path = Path(
            scaler_path
        )

        self.metadata_path = Path(
            metadata_path
        )

        self.feature_names = feature_names

        self.sequence_length = sequence_length

        self.model = None

        self.session = None

        self.scaler_min = None

        self.scaler_scale = None

        self._load_metadata()

        self._load_scaler()

        self._load_model()

    # ========================================================
    # METADATA
    # ========================================================

    def _load_metadata(self):

        if not self.metadata_path.exists():

            raise FileNotFoundError(
                f"Metadata tidak ditemukan: "
                f"{self.metadata_path}"
            )

        with open(
            self.metadata_path,
            "r",
            encoding="utf-8",
        ) as file:

            self.metadata = json.load(file)

        trained_features = (
            self.metadata.get(
                "features",
                []
            )
        )

        if trained_features != self.feature_names:

            raise ValueError(
                "\nKontrak feature LSTM tidak cocok.\n\n"
                f"Model : {trained_features}\n"
                f"Backend: {self.feature_names}\n"
            )

        trained_lookback = (
            self.metadata.get(
                "lookback"
            )
        )

        if trained_lookback != self.sequence_length:

            raise ValueError(
                "\nSequence length tidak cocok.\n\n"
                f"Model : {trained_lookback}\n"
                f"Backend: {self.sequence_length}\n"
            )

    # ========================================================
    # SCALER
    # ========================================================

    def _load_scaler(self):

        if not self.scaler_path.exists():

            raise FileNotFoundError(
                f"Scaler tidak ditemukan: "
                f"{self.scaler_path}"
            )

        with open(
            self.scaler_path,
            "r",
            encoding="utf-8",
        ) as file:

            scaler_data = json.load(file)

        self.scaler_min = np.asarray(
            scaler_data["min"],
            dtype=np.float32,
        )

        self.scaler_scale = np.asarray(
            scaler_data["scale"],
            dtype=np.float32,
        )

    # ========================================================
    # MODEL
    # ========================================================

    def _load_model(self):

        if not self.model_path.exists():

            raise FileNotFoundError(
                f"Model ONNX tidak ditemukan: "
                f"{self.model_path}"
            )

        try:

            import onnxruntime as ort

        except ImportError:

            raise RuntimeError(
                "onnxruntime belum tersedia "
                "untuk inference backend."
            )

        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=[
                "CPUExecutionProvider"
            ],
        )

        self.input_name = (
            self.session
            .get_inputs()[0]
            .name
        )

        self.output_name = (
            self.session
            .get_outputs()[0]
            .name
        )

        print(
            "[LSTM] ONNX model loaded:",
            self.model_path,
        )

    # ========================================================
    # SCALER TRANSFORM
    # ========================================================

    def _transform(
        self,
        values: np.ndarray,
    ):

        return (
            values * self.scaler_scale
            + self.scaler_min
        )

    # ========================================================
    # SCALER INVERSE
    # ========================================================

    def _inverse_transform(
        self,
        values: np.ndarray,
    ):

        return (
            values - self.scaler_min
        ) / self.scaler_scale

    # ========================================================
    # PREPARE SEQUENCE
    # ========================================================

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

            values.append(
                timestep
            )

        array = np.asarray(
            values,
            dtype=np.float32,
        )

        # [12, 5]
        array = self._transform(
            array
        )

        # [1, 12, 5]
        return np.expand_dims(
            array,
            axis=0,
        )

    # ========================================================
    # PREDICT
    # ========================================================

    def predict(
        self,
        history: list[dict],
    ) -> np.ndarray:

        sequence = self.prepare_sequence(
            history
        )

        prediction = self.session.run(
            [self.output_name],
            {
                self.input_name:
                    sequence
            },
        )[0]

        prediction = np.asarray(
            prediction,
            dtype=np.float32,
        )

        # Output:
        #
        # [1, 3, 5]

        original_shape = (
            prediction.shape
        )

        prediction = prediction.reshape(
            -1,
            len(self.feature_names),
        )

        prediction = self._inverse_transform(
            prediction
        )

        prediction = prediction.reshape(
            original_shape
        )

        # Traffic tidak boleh negatif.

        prediction = np.maximum(
            prediction,
            0,
        )

        return prediction
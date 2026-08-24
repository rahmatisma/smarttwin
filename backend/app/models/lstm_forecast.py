from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class ForecastOutput:
    values: np.ndarray


class LSTMForecaster:
    """
    ONNX inference wrapper untuk SmartTwin Traffic LSTM.

    Model contract:
        input  = [batch, lookback, features]
        output = [batch, horizon, features]

    Feature model:
        totalDiZona
        motorDiZona
        mobilDiZona
        trukDiZona
        busDiZona
    """

    def __init__(
        self,
        modelPath: str | Path,
        scalerPath: str | Path,
        metadataPath: str | Path,
        featureNames: list[str],
        sequenceLength: int,
    ):
        self.modelPath = Path(modelPath)
        self.scalerPath = Path(scalerPath)
        self.metadataPath = Path(metadataPath)

        self.featureNames = featureNames
        self.sequenceLength = sequenceLength

        self.session = None
        self.inputName = None
        self.outputName = None

        self.scalerMin = None
        self.scalerScale = None

        self.metadata = {}

        self._loadMetadata()
        self._loadScaler()
        self._loadModel()

    # =========================================================
    # METADATA
    # =========================================================

    def _loadMetadata(self) -> None:
        if not self.metadataPath.exists():
            raise FileNotFoundError(
                f"Metadata tidak ditemukan: {self.metadataPath}"
            )

        with open(
            self.metadataPath,
            "r",
            encoding="utf-8",
        ) as file:
            self.metadata = json.load(file)

        trainedFeatures = self.metadata.get(
            "features",
            [],
        )

        if trainedFeatures != self.featureNames:
            raise ValueError(
                "\nKontrak feature LSTM tidak cocok.\n\n"
                f"Model   : {trainedFeatures}\n"
                f"Backend : {self.featureNames}\n"
            )

        trainedLookback = self.metadata.get(
            "lookback"
        )

        if trainedLookback != self.sequenceLength:
            raise ValueError(
                "\nSequence length tidak cocok.\n\n"
                f"Model   : {trainedLookback}\n"
                f"Backend : {self.sequenceLength}\n"
            )

    # =========================================================
    # SCALER
    # =========================================================

    def _loadScaler(self) -> None:
        if not self.scalerPath.exists():
            raise FileNotFoundError(
                f"Scaler tidak ditemukan: {self.scalerPath}"
            )

        with open(
            self.scalerPath,
            "r",
            encoding="utf-8",
        ) as file:
            scalerData = json.load(file)

        self.scalerMin = np.asarray(
            scalerData["min"],
            dtype=np.float32,
        )

        self.scalerScale = np.asarray(
            scalerData["scale"],
            dtype=np.float32,
        )

        if len(self.scalerMin) != len(self.featureNames):
            raise ValueError(
                "Jumlah scaler feature tidak cocok dengan model."
            )

        if len(self.scalerScale) != len(self.featureNames):
            raise ValueError(
                "Jumlah scaler scale tidak cocok dengan model."
            )

    # =========================================================
    # MODEL
    # =========================================================

    def _loadModel(self) -> None:
        if not self.modelPath.exists():
            raise FileNotFoundError(
                f"Model ONNX tidak ditemukan: {self.modelPath}"
            )

        try:
            import onnxruntime as ort
        except ImportError:
            raise RuntimeError(
                "onnxruntime belum tersedia. "
                "Install dengan: pip install onnxruntime"
            ) from None

        self.session = ort.InferenceSession(
            str(self.modelPath),
            providers=[
                "CPUExecutionProvider"
            ],
        )

        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()

        if not inputs:
            raise RuntimeError(
                "ONNX model tidak memiliki input."
            )

        if not outputs:
            raise RuntimeError(
                "ONNX model tidak memiliki output."
            )

        self.inputName = inputs[0].name
        self.outputName = outputs[0].name

        print(
            "[LSTM] ONNX model loaded:",
            self.modelPath,
        )

        print(
            "[LSTM] Input:",
            self.inputName,
        )

        print(
            "[LSTM] Output:",
            self.outputName,
        )

    # =========================================================
    # SCALE
    # =========================================================

    def _transform(
        self,
        values: np.ndarray,
    ) -> np.ndarray:

        return (
            values * self.scalerScale
            + self.scalerMin
        )

    # =========================================================
    # INVERSE SCALE
    # =========================================================

    def _inverseTransform(
        self,
        values: np.ndarray,
    ) -> np.ndarray:

        return (
            values - self.scalerMin
        ) / self.scalerScale

    # =========================================================
    # PREPARE SEQUENCE
    # =========================================================

    def prepareSequence(
        self,
        history: list[dict],
    ) -> np.ndarray:

        if len(history) < self.sequenceLength:
            raise ValueError(
                "History belum cukup untuk LSTM. "
                f"Dibutuhkan {self.sequenceLength} timestep, "
                f"tersedia {len(history)}."
            )

        history = history[
            -self.sequenceLength:
        ]

        values = []

        for row in history:

            timestep = []

            for feature in self.featureNames:

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

        if array.shape != (
            self.sequenceLength,
            len(self.featureNames),
        ):
            raise ValueError(
                "Shape sequence LSTM tidak sesuai. "
                f"Shape: {array.shape}"
            )

        # MinMaxScaler:
        #
        # X_scaled = X * scale + min
        array = self._transform(
            array
        )

        # [lookback, features]
        #
        # menjadi
        #
        # [1, lookback, features]

        return np.expand_dims(
            array,
            axis=0,
        )

    # =========================================================
    # PREDICT
    # =========================================================

    def predict(
        self,
        history: list[dict],
    ) -> np.ndarray:

        sequence = self.prepareSequence(
            history
        )

        prediction = self.session.run(
            [self.outputName],
            {
                self.inputName: sequence
            },
        )[0]

        prediction = np.asarray(
            prediction,
            dtype=np.float32,
        )

        originalShape = prediction.shape

        prediction = prediction.reshape(
            -1,
            len(self.featureNames),
        )

        prediction = self._inverseTransform(
            prediction
        )

        prediction = prediction.reshape(
            originalShape
        )

        # Jumlah kendaraan tidak boleh negatif.
        prediction = np.maximum(
            prediction,
            0,
        )

        return prediction
from pathlib import Path

import numpy as np

from app.models.lstm_forecast import LSTMForecaster


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "forecasting"
    / "outputs"
    / "yolo"
)


FEATURE_NAMES = [
    "total_di_zona",
    "motor_di_zona",
    "mobil_di_zona",
    "truk_di_zona",
    "bus_di_zona",
]


def test_lstm_forecaster():

    forecaster = LSTMForecaster(
        modelPath=(
            OUTPUT_DIR
            / "traffic_lstm.onnx"
        ),
        scalerPath=(
            OUTPUT_DIR
            / "scaler.json"
        ),
        metadataPath=(
            OUTPUT_DIR
            / "metadata.json"
        ),
        featureNames=FEATURE_NAMES,
        sequenceLength=12,
    )

    history = []

    for index in range(12):

        history.append(
            {
                "total_di_zona": 20 + index,
                "motor_di_zona": 10 + index,
                "mobil_di_zona": 7,
                "truk_di_zona": 2,
                "bus_di_zona": 1,
            }
        )

    prediction = forecaster.predict(
        history
    )

    assert prediction is not None

    assert prediction.ndim == 3

    assert prediction.shape[0] == 1

    assert prediction.shape[2] == 5

    assert np.all(
        prediction >= 0
    )

    print(
        "\nPrediction shape:",
        prediction.shape,
    )

    print(
        "Prediction:",
        prediction,
    )
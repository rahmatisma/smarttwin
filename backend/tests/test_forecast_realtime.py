from __future__ import annotations

from pathlib import Path

from app.models.lstm_forecast import LSTMForecaster
from app.repositories.forecast_repository import (
    ForecastRepository,
)
from app.services.forecast_service import (
    ForecastService,
)


BASE_DIR = Path(
    __file__
).resolve().parents[1]

PROJECT_ROOT = BASE_DIR

FORECASTING_DIR = (
    PROJECT_ROOT
    / "forecasting"
    / "outputs"
    / "yolo"
)

MODEL_PATH = (
    FORECASTING_DIR
    / "traffic_lstm.onnx"
)

SCALER_PATH = (
    FORECASTING_DIR
    / "scaler.json"
)

METADATA_PATH = (
    FORECASTING_DIR
    / "metadata.json"
)


FEATURE_NAMES = [
    "totalDiZona",
    "motorDiZona",
    "mobilDiZona",
    "trukDiZona",
    "busDiZona",
]


def main():

    intersectionId = "intersection_01"

    print(
        "\n======================================"
    )

    print(
        "SMARTTWIN REALTIME FORECAST TEST"
    )

    print(
        "======================================"
    )

    print(
        "\nModel:",
        MODEL_PATH,
    )

    forecaster = LSTMForecaster(
        modelPath=MODEL_PATH,
        scalerPath=SCALER_PATH,
        metadataPath=METADATA_PATH,
        featureNames=FEATURE_NAMES,
        sequenceLength=12,
    )

    repository = ForecastRepository()

    service = ForecastService(
        forecaster=forecaster,
        repository=repository,
    )

    print(
        "\nMengambil data dari Supabase..."
    )

    result = service.forecast(
        intersectionId=intersectionId,
        horizonMinutes=1,
    )

    print(
        "\nFORECAST RESULT"
    )

    print(
        result.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()
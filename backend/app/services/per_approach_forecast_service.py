from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = PROJECT_ROOT / "forecasting" / "outputs" / "lstm" / "per_approach"
MODEL_PATH = ARTIFACT_DIR / "traffic_lstm_per_approach.pt"
SCALER_PATH = ARTIFACT_DIR / "scaler.json"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"

APPROACHES = ("west", "south", "east", "north")
ZONE_CAPACITY = 33.0
TRAFFIC_FEATURES = (
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
)


class SharedApproachLSTM(nn.Module):
    """Arsitektur serving yang sama dengan script training per-approach."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self.output_steps = int(config["outputSteps"])
        self.output_size = int(config["outputSize"])
        num_layers = int(config["numLayers"])
        self.lstm = nn.LSTM(
            input_size=int(config["inputSize"]),
            hidden_size=int(config["hiddenSize"]),
            num_layers=num_layers,
            batch_first=True,
            dropout=float(config.get("dropout", 0.0)) if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(
            int(config["hiddenSize"]),
            self.output_steps * self.output_size,
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        sequence, _ = self.lstm(values)
        prediction = self.fc(sequence[:, -1, :])
        return prediction.view(-1, self.output_steps, self.output_size)


class PerApproachForecastService:
    """Inferensi LSTM 12x5 detik untuk empat lengan simpang."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model: SharedApproachLSTM | None = None
        self._checkpoint: dict[str, Any] | None = None
        self._scaler: dict[str, Any] | None = None
        self._metadata: dict[str, Any] | None = None

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            missing = [path for path in (MODEL_PATH, SCALER_PATH, METADATA_PATH) if not path.exists()]
            if missing:
                raise FileNotFoundError(
                    "Artefak LSTM per-approach belum lengkap: "
                    + ", ".join(str(path) for path in missing)
                )
            checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
            model = SharedApproachLSTM(checkpoint["modelConfig"])
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()
            self._checkpoint = checkpoint
            self._scaler = json.loads(SCALER_PATH.read_text(encoding="utf-8"))
            self._metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
            self._model = model

    @staticmethod
    def _timestamp(record: dict[str, Any]) -> datetime:
        raw = record.get("timestamp")
        if raw is None:
            state = record.get("trafficState", {})
            raw = state.get("windowEnd") or state.get("windowStart")
        if isinstance(raw, datetime):
            return raw
        if not raw:
            raise ValueError("Record traffic tidak memiliki timestamp.")
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))

    @staticmethod
    def _approach_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
        rows = record.get("approaches")
        if not isinstance(rows, list):
            raise ValueError("Record traffic tidak memiliki approaches.")
        return rows

    def _history(self, records: list[dict[str, Any]]) -> list[tuple[datetime, dict[str, dict[str, Any]]]]:
        normalized: list[tuple[datetime, dict[str, dict[str, Any]]]] = []
        for record in records:
            by_approach = {
                str(row.get("approach", "")).lower(): row
                for row in self._approach_rows(record)
            }
            if all(approach in by_approach for approach in APPROACHES):
                normalized.append((self._timestamp(record), by_approach))
        normalized.sort(key=lambda item: item[0])

        # Ambil blok 12 data paling baru yang benar-benar berjarak 5 detik.
        for end in range(len(normalized), 11, -1):
            window = normalized[end - 12:end]
            if all(
                (window[index][0] - window[index - 1][0]).total_seconds() == 5
                for index in range(1, len(window))
            ):
                return window
        raise ValueError(
            "Forecast per-approach membutuhkan 12 TrafficState lengkap dan berurutan setiap 5 detik."
        )

    def predict_records(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        self._load()
        assert self._model is not None
        assert self._checkpoint is not None
        assert self._scaler is not None
        assert self._metadata is not None

        history = self._history(records)
        minimum = np.asarray(self._scaler["min"], dtype=np.float32)
        scale = np.asarray(self._scaler["scale"], dtype=np.float32)
        model_inputs: list[np.ndarray] = []

        for approach_index, approach in enumerate(APPROACHES):
            traffic = []
            for _, rows in history:
                row = rows[approach]
                density = float(row.get("densityIndex", 0) or 0)
                # TrafficState runtime menyimpan proxy jumlah kendaraan di
                # zona. Dataset training menormalkannya dengan kapasitas 33.
                # Request API manual sudah memakai kontrak 0..1, sedangkan
                # record Supabase dikenali dari field `volume`.
                if "volume" in row:
                    density /= ZONE_CAPACITY
                traffic.append([
                    float(row.get("vehicleCount", row.get("volume", 0)) or 0),
                    float(row.get("queueLengthVeh", 0) or 0),
                    float(row.get("queueLengthMEst", 0) or 0),
                    min(1.0, max(0.0, density)),
                ])
            scaled = np.asarray(traffic, dtype=np.float32) * scale + minimum
            one_hot = np.zeros((12, len(APPROACHES)), dtype=np.float32)
            one_hot[:, approach_index] = 1.0
            model_inputs.append(np.concatenate((scaled, one_hot), axis=1))

        tensor = torch.from_numpy(np.asarray(model_inputs, dtype=np.float32))
        with torch.inference_mode():
            predicted_scaled = self._model(tensor).cpu().numpy()
        predicted = (predicted_scaled - minimum) / scale
        predicted[:, :, :3] = np.maximum(predicted[:, :, :3], 0.0)
        predicted[:, :, 3] = np.clip(predicted[:, :, 3], 0.0, 1.0)

        last_timestamp = history[-1][0]
        forecasts = []
        for step in range(predicted.shape[1]):
            seconds_ahead = (step + 1) * 5
            forecasts.append({
                "timestamp": (last_timestamp + timedelta(seconds=seconds_ahead)).isoformat(),
                "secondsAhead": seconds_ahead,
                "approaches": [
                    {
                        "approach": approach,
                        **{
                            feature: round(float(predicted[index, step, feature_index]), 6)
                            for feature_index, feature in enumerate(TRAFFIC_FEATURES)
                        },
                    }
                    for index, approach in enumerate(APPROACHES)
                ],
            })

        return {
            "model": {
                "name": self._metadata.get("model", "SharedApproachLSTM"),
                "mode": "per-approach",
                "inputSteps": 12,
                "outputSteps": len(forecasts),
                "intervalSeconds": 5,
            },
            "input": {
                "recordsUsed": len(history),
                "from": history[0][0].isoformat(),
                "to": history[-1][0].isoformat(),
            },
            "approachForecasts": forecasts,
            "forecastSource": "lstm-per-approach",
            "fallbackUsed": False,
        }

    def health(self) -> dict[str, Any]:
        self._load()
        return {
            "status": "ready",
            "mode": "per-approach",
            "modelPath": str(MODEL_PATH),
            "approaches": list(APPROACHES),
        }


per_approach_forecast_service = PerApproachForecastService()

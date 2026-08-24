from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn


# ============================================================
# CONFIGURATION
# ============================================================

FEATURES = [
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
]

INPUT_TIMESTEPS = 12
OUTPUT_TIMESTEPS = 3
STEP_SECONDS = 5

DEFAULT_HIDDEN_SIZE = 64
DEFAULT_NUM_LAYERS = 2
DEFAULT_DROPOUT = 0.2


# ============================================================
# PATH
# ============================================================

# backend/app/services/forecast_service.py
#
# parents:
#   0 = services
#   1 = app
#   2 = backend
#
# Jadi:
#   backend_root = Path(__file__).resolve().parents[2]

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Project root:
# smarttwin/
PROJECT_ROOT = BACKEND_ROOT.parent

# forecasting/
FORECASTING_ROOT = PROJECT_ROOT / "forecasting"

MODEL_DIR = FORECASTING_ROOT / "outputs" / "lstm"

MODEL_PATH = MODEL_DIR / "traffic_lstm.pt"
SCALER_PATH = MODEL_DIR / "scaler.json"
METADATA_PATH = MODEL_DIR / "metadata.json"


# ============================================================
# LSTM MODEL
# ============================================================


class TrafficLSTM(nn.Module):
    """
    LSTM model yang harus sama dengan model saat training.

    Input:
        [batch, 12, 4]

    Output:
        [batch, 3, 4]
    """

    def __init__(
        self,
        input_size: int = len(FEATURES),
        hidden_size: int = DEFAULT_HIDDEN_SIZE,
        num_layers: int = DEFAULT_NUM_LAYERS,
        output_size: int = len(FEATURES),
        output_timesteps: int = OUTPUT_TIMESTEPS,
        dropout: float = DEFAULT_DROPOUT,
    ) -> None:
        super().__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_size = output_size
        self.output_timesteps = output_timesteps
        self.dropout = dropout

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        self.fc = nn.Linear(
            hidden_size,
            output_timesteps * output_size,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x:
            [batch, input_timesteps, features]

        return:
            [batch, output_timesteps, features]
        """

        output, _ = self.lstm(x)

        # Ambil hidden state timestep terakhir
        last_hidden = output[:, -1, :]

        prediction = self.fc(last_hidden)

        prediction = prediction.view(
            -1,
            self.output_timesteps,
            self.output_size,
        )

        return prediction


# ============================================================
# FORECAST SERVICE
# ============================================================


class ForecastService:
    """
    Service untuk menjalankan inference LSTM SmartTwin.

    Tugas utama:

    1. Load model .pt
    2. Load scaler
    3. Load metadata
    4. Validasi input
    5. Normalisasi input
    6. Jalankan LSTM
    7. Inverse transform
    8. Menghasilkan forecast 15 detik
    """

    def __init__(
        self,
        model_path: Path | str = MODEL_PATH,
        scaler_path: Path | str = SCALER_PATH,
        metadata_path: Path | str = METADATA_PATH,
    ) -> None:

        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)
        self.metadata_path = Path(metadata_path)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.model: TrafficLSTM | None = None

        self.scaler: dict[str, Any] | None = None

        self.metadata: dict[str, Any] = {}

        self.loaded = False

    # ========================================================
    # LOAD EVERYTHING
    # ========================================================

    def load(self) -> None:
        """
        Load model, scaler dan metadata.

        Dipanggil sekali saat service pertama kali digunakan.
        """

        if self.loaded:
            return

        # ----------------------------------------------------
        # Check files
        # ----------------------------------------------------

        missing_files: list[str] = []

        if not self.model_path.exists():
            missing_files.append(str(self.model_path))

        if not self.scaler_path.exists():
            missing_files.append(str(self.scaler_path))

        if not self.metadata_path.exists():
            missing_files.append(str(self.metadata_path))

        if missing_files:
            raise FileNotFoundError(
                "File forecasting tidak ditemukan:\n"
                + "\n".join(f"- {path}" for path in missing_files)
            )

        # ----------------------------------------------------
        # Load metadata
        # ----------------------------------------------------

        with self.metadata_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            metadata = json.load(file)

        self.metadata = metadata

        # ----------------------------------------------------
        # Determine model configuration
        # ----------------------------------------------------

        model_config = metadata.get("model", {})

        # Be defensive kalau struktur metadata berbeda
        if not isinstance(model_config, dict):
            model_config = {}

        hidden_size = int(
            model_config.get(
                "hidden_size",
                metadata.get("hidden_size", DEFAULT_HIDDEN_SIZE),
            )
        )

        num_layers = int(
            model_config.get(
                "num_layers",
                metadata.get("num_layers", DEFAULT_NUM_LAYERS),
            )
        )

        dropout = float(
            model_config.get(
                "dropout",
                metadata.get("dropout", DEFAULT_DROPOUT),
            )
        )

        # ----------------------------------------------------
        # Load scaler
        # ----------------------------------------------------

        with self.scaler_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            scaler = json.load(file)

        if not isinstance(scaler, dict):
            raise ValueError(
                "Format scaler.json tidak valid. "
                "Root JSON harus berupa object."
            )

        self.scaler = scaler

        # ----------------------------------------------------
        # Build model
        # ----------------------------------------------------

        self.model = TrafficLSTM(
            input_size=len(FEATURES),
            hidden_size=hidden_size,
            num_layers=num_layers,
            output_size=len(FEATURES),
            output_timesteps=OUTPUT_TIMESTEPS,
            dropout=dropout,
        )

        # ----------------------------------------------------
        # Load PyTorch checkpoint
        # ----------------------------------------------------

        checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
        )

        # ----------------------------------------------------
        # Support several checkpoint formats
        # ----------------------------------------------------

        if isinstance(checkpoint, dict):

            if "state_dict" in checkpoint:
                state_dict = checkpoint["state_dict"]

            elif "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]

            else:
                # Bisa jadi langsung state_dict
                state_dict = checkpoint

        else:
            raise ValueError(
                "Format traffic_lstm.pt tidak dikenali."
            )

        # ----------------------------------------------------
        # Remove DataParallel prefix jika ada
        # ----------------------------------------------------

        cleaned_state_dict = {}

        for key, value in state_dict.items():

            if key.startswith("module."):
                key = key[len("module.") :]

            cleaned_state_dict[key] = value

        self.model.load_state_dict(
            cleaned_state_dict,
            strict=True,
        )

        self.model.to(self.device)

        self.model.eval()

        self.loaded = True

        print("=" * 70)
        print("SMARTTWIN FORECAST SERVICE")
        print("=" * 70)
        print(f"Device      : {self.device}")
        print(f"Model       : {self.model_path}")
        print(f"Scaler      : {self.scaler_path}")
        print(f"Metadata    : {self.metadata_path}")
        print(f"Hidden size : {hidden_size}")
        print(f"Layers      : {num_layers}")
        print(f"Dropout     : {dropout}")
        print(f"Input       : {INPUT_TIMESTEPS} × {len(FEATURES)}")
        print(f"Output      : {OUTPUT_TIMESTEPS} × {len(FEATURES)}")
        print("=" * 70)

    # ========================================================
    # SCALER
    # ========================================================

    def _get_scaler_parameters(
        self,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Mengambil center/scale dari scaler.json.

        Mendukung format:
            mean / scale

        maupun:
            mean_ / scale_

        maupun:
            center / scale
        """

        if self.scaler is None:
            raise RuntimeError(
                "Scaler belum dimuat."
            )

        scaler = self.scaler

        # ----------------------------------------------------
        # Case 1:
        # {
        #   "mean": [...],
        #   "scale": [...]
        # }
        # ----------------------------------------------------

        if "mean" in scaler and "scale" in scaler:

            mean = np.asarray(
                scaler["mean"],
                dtype=np.float32,
            )

            scale = np.asarray(
                scaler["scale"],
                dtype=np.float32,
            )

            return mean, scale

        # ----------------------------------------------------
        # Case 2:
        # {
        #   "mean_": [...],
        #   "scale_": [...]
        # }
        # ----------------------------------------------------

        if "mean_" in scaler and "scale_" in scaler:

            mean = np.asarray(
                scaler["mean_"],
                dtype=np.float32,
            )

            scale = np.asarray(
                scaler["scale_"],
                dtype=np.float32,
            )

            return mean, scale

        # ----------------------------------------------------
        # Case 3:
        # {
        #   "center": [...],
        #   "scale": [...]
        # }
        # ----------------------------------------------------

        if "center" in scaler and "scale" in scaler:

            mean = np.asarray(
                scaler["center"],
                dtype=np.float32,
            )

            scale = np.asarray(
                scaler["scale"],
                dtype=np.float32,
            )

            return mean, scale

        raise ValueError(
            "Format scaler.json tidak dikenali. "
            "Dibutuhkan pasangan mean/scale."
        )

    # ========================================================
    # NORMALIZE
    # ========================================================

    def _transform(
        self,
        values: np.ndarray,
    ) -> np.ndarray:
        """
        Standardisasi:

            z = (x - mean) / scale
        """

        mean, scale = self._get_scaler_parameters()

        if mean.shape[0] != len(FEATURES):
            raise ValueError(
                f"Jumlah mean scaler ({mean.shape[0]}) "
                f"tidak sama dengan jumlah fitur ({len(FEATURES)})."
            )

        if scale.shape[0] != len(FEATURES):
            raise ValueError(
                f"Jumlah scale scaler ({scale.shape[0]}) "
                f"tidak sama dengan jumlah fitur ({len(FEATURES)})."
            )

        # Hindari division by zero
        scale = np.where(
            scale == 0,
            1.0,
            scale,
        )

        return (
            values - mean
        ) / scale

    # ========================================================
    # INVERSE NORMALIZE
    # ========================================================

    def _inverse_transform(
        self,
        values: np.ndarray,
    ) -> np.ndarray:
        """
        Mengembalikan data ke skala asli.
        """

        mean, scale = self._get_scaler_parameters()

        scale = np.where(
            scale == 0,
            1.0,
            scale,
        )

        return (
            values * scale
        ) + mean

    # ========================================================
    # VALIDATE DATAFRAME
    # ========================================================

    def validate_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Validasi dataframe input.

        Wajib memiliki:
            timestamp
            4 feature
        """

        if dataframe is None:
            raise ValueError(
                "Dataframe tidak boleh None."
            )

        dataframe = dataframe.copy()

        # ----------------------------------------------------
        # Check columns
        # ----------------------------------------------------

        required_columns = [
            "timestamp",
            *FEATURES,
        ]

        missing = [
            column
            for column in required_columns
            if column not in dataframe.columns
        ]

        if missing:
            raise ValueError(
                "Kolom input kurang:\n"
                + "\n".join(
                    f"- {column}"
                    for column in missing
                )
            )

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        dataframe["timestamp"] = pd.to_datetime(
            dataframe["timestamp"],
            errors="coerce",
        )

        if dataframe["timestamp"].isna().any():
            raise ValueError(
                "Terdapat timestamp yang tidak valid."
            )

        # ----------------------------------------------------
        # Numeric features
        # ----------------------------------------------------

        for feature in FEATURES:

            dataframe[feature] = pd.to_numeric(
                dataframe[feature],
                errors="coerce",
            )

        # ----------------------------------------------------
        # NaN
        # ----------------------------------------------------

        if dataframe[FEATURES].isna().any().any():

            nan_columns = (
                dataframe[FEATURES]
                .columns[
                    dataframe[FEATURES]
                    .isna()
                    .any()
                ]
                .tolist()
            )

            raise ValueError(
                "Terdapat nilai NaN pada fitur: "
                + ", ".join(nan_columns)
            )

        # ----------------------------------------------------
        # Sort timestamp
        # ----------------------------------------------------

        dataframe = dataframe.sort_values(
            "timestamp"
        ).reset_index(drop=True)

        return dataframe

    # ========================================================
    # GET LAST WINDOW
    # ========================================================

    def prepare_input(
        self,
        dataframe: pd.DataFrame,
    ) -> tuple[np.ndarray, pd.Timestamp]:
        """
        Ambil 12 timestep terakhir.

        Return:
            array [12, 4]
            last timestamp
        """

        dataframe = self.validate_dataframe(
            dataframe
        )

        if len(dataframe) < INPUT_TIMESTEPS:

            raise ValueError(
                f"Data tidak cukup untuk forecast. "
                f"Dibutuhkan minimal {INPUT_TIMESTEPS} timestep, "
                f"tetapi hanya tersedia {len(dataframe)}."
            )

        latest = dataframe.tail(
            INPUT_TIMESTEPS
        ).copy()

        values = latest[
            FEATURES
        ].to_numpy(
            dtype=np.float32
        )

        last_timestamp = latest[
            "timestamp"
        ].iloc[-1]

        return values, last_timestamp

    # ========================================================
    # PREDICT
    # ========================================================

    @torch.no_grad()
    def predict_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Jalankan forecasting dari dataframe.

        Input:
            minimal 12 timestep.

        Output:
            forecast 3 timestep / 15 detik.
        """

        self.load()

        if self.model is None:
            raise RuntimeError(
                "Model belum tersedia."
            )

        values, last_timestamp = self.prepare_input(
            dataframe
        )

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        scaled = self._transform(
            values
        )

        # ----------------------------------------------------
        # Tensor
        # ----------------------------------------------------

        tensor = torch.tensor(
            scaled,
            dtype=torch.float32,
            device=self.device,
        )

        tensor = tensor.unsqueeze(0)

        # Shape:
        # [1, 12, 4]

        # ----------------------------------------------------
        # Model inference
        # ----------------------------------------------------

        prediction = self.model(
            tensor
        )

        # [1, 3, 4]

        prediction = (
            prediction
            .detach()
            .cpu()
            .numpy()
        )

        prediction = prediction[0]

        # ----------------------------------------------------
        # Inverse transform
        # ----------------------------------------------------

        prediction_original = (
            self._inverse_transform(
                prediction
            )
        )

        # ----------------------------------------------------
        # Business safety
        # ----------------------------------------------------

        # vehicle count tidak boleh negatif
        prediction_original[:, 0] = np.maximum(
            prediction_original[:, 0],
            0.0,
        )

        # queue kendaraan tidak boleh negatif
        prediction_original[:, 1] = np.maximum(
            prediction_original[:, 1],
            0.0,
        )

        # queue meter tidak boleh negatif
        prediction_original[:, 2] = np.maximum(
            prediction_original[:, 2],
            0.0,
        )

        # density 0..1
        prediction_original[:, 3] = np.clip(
            prediction_original[:, 3],
            0.0,
            1.0,
        )

        # ----------------------------------------------------
        # Build forecast records
        # ----------------------------------------------------

        forecasts: list[dict[str, Any]] = []

        for index in range(
            OUTPUT_TIMESTEPS
        ):

            timestamp = (
                last_timestamp
                + timedelta(
                    seconds=STEP_SECONDS * (index + 1)
                )
            )

            row = {
                "timestamp": timestamp.isoformat(),
                "vehicleCount": round(
                    float(
                        prediction_original[index, 0]
                    ),
                    4,
                ),
                "queueLengthVeh": round(
                    float(
                        prediction_original[index, 1]
                    ),
                    4,
                ),
                "queueLengthMEst": round(
                    float(
                        prediction_original[index, 2]
                    ),
                    4,
                ),
                "densityIndex": round(
                    float(
                        prediction_original[index, 3]
                    ),
                    4,
                ),
                "secondsAhead": STEP_SECONDS * (index + 1),
            }

            forecasts.append(row)

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {
            "model": {
                "type": "LSTM",
                "inputTimesteps": INPUT_TIMESTEPS,
                "outputTimesteps": OUTPUT_TIMESTEPS,
                "stepSeconds": STEP_SECONDS,
                "forecastSeconds": (
                    OUTPUT_TIMESTEPS
                    * STEP_SECONDS
                ),
                "features": FEATURES,
            },
            "input": {
                "timestepsUsed": INPUT_TIMESTEPS,
                "lastTimestamp": last_timestamp.isoformat(),
                "latestValues": {
                    FEATURES[index]: float(
                        values[-1, index]
                    )
                    for index in range(
                        len(FEATURES)
                    )
                },
            },
            "forecast": forecasts,
        }

    # ========================================================
    # PREDICT FROM RECORDS
    # ========================================================

    def predict_records(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Forecast dari list JSON records.

        Cocok untuk request dari frontend/backend.
        """

        if not records:
            raise ValueError(
                "records tidak boleh kosong."
            )

        dataframe = pd.DataFrame(
            records
        )

        return self.predict_dataframe(
            dataframe
        )

    # ========================================================
    # PREDICT FROM LATEST VALUES
    # ========================================================

    def predict_from_values(
        self,
        timestamps: list[Any],
        vehicle_count: list[float],
        queue_length_veh: list[float],
        queue_length_m_est: list[float],
        density_index: list[float],
    ) -> dict[str, Any]:
        """
        Helper kalau nanti backend ingin langsung
        mengirim data hasil TrafficStateBuilder.

        Semua list harus memiliki minimal 12 item.
        """

        if not (
            len(timestamps)
            == len(vehicle_count)
            == len(queue_length_veh)
            == len(queue_length_m_est)
            == len(density_index)
        ):
            raise ValueError(
                "Semua array input harus memiliki "
                "jumlah elemen yang sama."
            )

        dataframe = pd.DataFrame(
            {
                "timestamp": timestamps,
                "vehicleCount": vehicle_count,
                "queueLengthVeh": queue_length_veh,
                "queueLengthMEst": queue_length_m_est,
                "densityIndex": density_index,
            }
        )

        return self.predict_dataframe(
            dataframe
        )

    # ========================================================
    # HEALTH
    # ========================================================

    def health(self) -> dict[str, Any]:
        """
        Status model forecasting.
        """

        model_exists = self.model_path.exists()
        scaler_exists = self.scaler_path.exists()
        metadata_exists = self.metadata_path.exists()

        return {
            "loaded": self.loaded,
            "device": str(self.device),
            "modelExists": model_exists,
            "scalerExists": scaler_exists,
            "metadataExists": metadata_exists,
            "modelPath": str(
                self.model_path
            ),
            "scalerPath": str(
                self.scaler_path
            ),
            "metadataPath": str(
                self.metadata_path
            ),
            "features": FEATURES,
            "inputTimesteps": INPUT_TIMESTEPS,
            "outputTimesteps": OUTPUT_TIMESTEPS,
            "forecastSeconds": (
                OUTPUT_TIMESTEPS
                * STEP_SECONDS
            ),
        }


# ============================================================
# SINGLETON SERVICE
# ============================================================

forecast_service = ForecastService()
from __future__ import annotations

import json
from datetime import timedelta
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
# 12, bukan 3 -- model traffic_lstm.pt hasil retrain 26 Agustus
# (commit 5d2e594) memprediksi 12 langkah (60 detik), sesuai
# metadata.json::outputSteps. Nilai lama (3) cocok buat model
# SEBELUM retrain 4-fitur, sekarang bikin size mismatch saat
# load_state_dict (fc.weight [48,64] vs [12,64]).
OUTPUT_TIMESTEPS = 12
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

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# smarttwin/
PROJECT_ROOT = BACKEND_ROOT.parent

# forecasting/
FORECASTING_ROOT = PROJECT_ROOT / "forecasting"

# forecasting/outputs/lstm/
MODEL_DIR = FORECASTING_ROOT / "outputs" / "lstm"

MODEL_PATH = MODEL_DIR / "traffic_lstm.pt"
SCALER_PATH = MODEL_DIR / "scaler.json"
METADATA_PATH = MODEL_DIR / "metadata.json"


# ============================================================
# LSTM MODEL
# ============================================================


class TrafficLSTM(nn.Module):
    """
    LSTM model SmartTwin.

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
        Input:
            [batch, input_timesteps, features]

        Output:
            [batch, output_timesteps, features]
        """

        output, _ = self.lstm(x)

        # Hidden state timestep terakhir
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
    Service inference LSTM SmartTwin.

    Pipeline:

        input dataframe
              ↓
        validation
              ↓
        ambil 12 timestep
              ↓
        MinMax scaling
              ↓
        PyTorch LSTM
              ↓
        inverse MinMax scaling
              ↓
        forecast 3 timestep
              ↓
        JSON response
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

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.model: TrafficLSTM | None = None

        self.scaler: dict[str, Any] | None = None

        self.metadata: dict[str, Any] = {}

        self.loaded = False

    # ========================================================
    # LOAD EVERYTHING
    # ========================================================

    def load(self) -> None:
        """
        Load model, scaler, dan metadata.
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
                + "\n".join(
                    f"- {path}"
                    for path in missing_files
                )
            )

        # ----------------------------------------------------
        # Load metadata
        # ----------------------------------------------------

        with self.metadata_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            metadata = json.load(file)

        if not isinstance(metadata, dict):
            raise ValueError(
                "Format metadata.json tidak valid."
            )

        self.metadata = metadata

        # ----------------------------------------------------
        # Determine model configuration
        # ----------------------------------------------------

        model_config = metadata.get("model", {})

        if not isinstance(model_config, dict):
            model_config = {}

        hidden_size = int(
            model_config.get(
                "hidden_size",
                metadata.get(
                    "hidden_size",
                    DEFAULT_HIDDEN_SIZE,
                ),
            )
        )

        num_layers = int(
            model_config.get(
                "num_layers",
                metadata.get(
                    "num_layers",
                    DEFAULT_NUM_LAYERS,
                ),
            )
        )

        dropout = float(
            model_config.get(
                "dropout",
                metadata.get(
                    "dropout",
                    DEFAULT_DROPOUT,
                ),
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
                "Format scaler.json tidak valid."
            )

        self.scaler = scaler

        # ----------------------------------------------------
        # Validate scaler
        # ----------------------------------------------------

        self._validate_scaler()

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
        # Support checkpoint formats
        # ----------------------------------------------------

        if isinstance(checkpoint, dict):

            if "state_dict" in checkpoint:

                state_dict = checkpoint["state_dict"]

            elif "model_state_dict" in checkpoint:

                state_dict = checkpoint["model_state_dict"]

            else:

                # kemungkinan langsung state_dict
                state_dict = checkpoint

        else:
            raise ValueError(
                "Format traffic_lstm.pt tidak dikenali."
            )

        # ----------------------------------------------------
        # Remove DataParallel prefix
        # ----------------------------------------------------

        cleaned_state_dict: dict[str, Any] = {}

        for key, value in state_dict.items():

            if key.startswith("module."):
                key = key[len("module."):]

            cleaned_state_dict[key] = value

        # ----------------------------------------------------
        # Load weights
        # ----------------------------------------------------

        try:

            self.model.load_state_dict(
                cleaned_state_dict,
                strict=True,
            )

        except RuntimeError as exc:

            raise RuntimeError(
                "Struktur model traffic_lstm.pt tidak cocok "
                "dengan TrafficLSTM pada backend.\n\n"
                f"Detail PyTorch:\n{exc}"
            ) from exc

        # ----------------------------------------------------
        # Device
        # ----------------------------------------------------

        self.model.to(self.device)

        self.model.eval()

        self.loaded = True

        # ----------------------------------------------------
        # Startup information
        # ----------------------------------------------------

        print("=" * 70)
        print("SMARTTWIN FORECAST SERVICE")
        print("=" * 70)

        print(f"Device       : {self.device}")
        print(f"Model        : {self.model_path}")
        print(f"Scaler       : {self.scaler_path}")
        print(f"Metadata     : {self.metadata_path}")

        print(f"Hidden size  : {hidden_size}")
        print(f"Layers       : {num_layers}")
        print(f"Dropout      : {dropout}")

        print(
            f"Input        : "
            f"{INPUT_TIMESTEPS} × {len(FEATURES)}"
        )

        print(
            f"Output       : "
            f"{OUTPUT_TIMESTEPS} × {len(FEATURES)}"
        )

        print("Scaler       : MinMaxScaler")

        print("=" * 70)

    # ========================================================
    # VALIDATE SCALER
    # ========================================================

    def _validate_scaler(self) -> None:
        """
        Validasi scaler.json.

        Format scaler yang digunakan training:

        {
            "features": [...],
            "min": [...],
            "scale": [...],
            "data_min": [...],
            "data_max": [...],
            "data_range": [...]
        }
        """

        if self.scaler is None:
            raise RuntimeError(
                "Scaler belum dimuat."
            )

        scaler = self.scaler

        required = [
            "min",
            "scale",
        ]

        missing = [
            key
            for key in required
            if key not in scaler
        ]

        if missing:
            raise ValueError(
                "scaler.json tidak memiliki field: "
                + ", ".join(missing)
            )

        scaler_features = scaler.get(
            "features"
        )

        if scaler_features is not None:

            if scaler_features != FEATURES:

                raise ValueError(
                    "Urutan fitur pada scaler.json berbeda "
                    "dengan model backend.\n"
                    f"Scaler : {scaler_features}\n"
                    f"Model  : {FEATURES}"
                )

        min_values = np.asarray(
            scaler["min"],
            dtype=np.float32,
        )

        scale_values = np.asarray(
            scaler["scale"],
            dtype=np.float32,
        )

        if len(min_values) != len(FEATURES):

            raise ValueError(
                "Jumlah nilai min scaler tidak sesuai "
                f"dengan fitur. "
                f"Diharapkan {len(FEATURES)}, "
                f"ditemukan {len(min_values)}."
            )

        if len(scale_values) != len(FEATURES):

            raise ValueError(
                "Jumlah nilai scale scaler tidak sesuai "
                f"dengan fitur. "
                f"Diharapkan {len(FEATURES)}, "
                f"ditemukan {len(scale_values)}."
            )

    # ========================================================
    # GET MINMAX PARAMETERS
    # ========================================================

    def _get_scaler_parameters(
        self,
    ) -> tuple[np.ndarray, np.ndarray]:

        if self.scaler is None:
            raise RuntimeError(
                "Scaler belum dimuat."
            )

        scaler = self.scaler

        min_values = np.asarray(
            scaler["min"],
            dtype=np.float32,
        )

        scale_values = np.asarray(
            scaler["scale"],
            dtype=np.float32,
        )

        return min_values, scale_values

    # ========================================================
    # NORMALIZE
    # ========================================================

    def _transform(
        self,
        values: np.ndarray,
    ) -> np.ndarray:
        """
        MinMax scaling.

        Sesuai dengan sklearn MinMaxScaler:

            X_scaled = X * scale + min
        """

        min_values, scale_values = (
            self._get_scaler_parameters()
        )

        values = np.asarray(
            values,
            dtype=np.float32,
        )

        return (
            values * scale_values
            + min_values
        )

    # ========================================================
    # INVERSE NORMALIZE
    # ========================================================

    def _inverse_transform(
        self,
        values: np.ndarray,
    ) -> np.ndarray:
        """
        Inverse MinMax scaling.

            X = (X_scaled - min) / scale
        """

        min_values, scale_values = (
            self._get_scaler_parameters()
        )

        values = np.asarray(
            values,
            dtype=np.float32,
        )

        # Hindari division by zero
        safe_scale = np.where(
            scale_values == 0,
            1.0,
            scale_values,
        )

        return (
            values - min_values
        ) / safe_scale

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
            vehicleCount
            queueLengthVeh
            queueLengthMEst
            densityIndex
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

        # IMPORTANT:
        #
        # Jangan langsung pd.to_datetime(errors="coerce")
        # tanpa mengetahui format input.
        #
        # Kita support:
        #
        # 2026-08-15 17:19:15
        # 2026-08-15T17:19:15
        # 2026-08-15T17:19:15+07:00
        # ISO timestamp.
        #
        # Tetapi placeholder seperti:
        #
        # "string"
        #
        # tetap akan ditolak.

        raw_timestamps = dataframe[
            "timestamp"
        ].copy()

        parsed_timestamps = []

        invalid_values = []

        for value in raw_timestamps:

            if value is None:
                invalid_values.append(value)
                parsed_timestamps.append(pd.NaT)
                continue

            if isinstance(
                value,
                float,
            ) and np.isnan(value):

                invalid_values.append(value)
                parsed_timestamps.append(pd.NaT)
                continue

            text = str(value).strip()

            if not text:

                invalid_values.append(value)
                parsed_timestamps.append(pd.NaT)
                continue

            # Explicitly reject common placeholder
            # values from Swagger/OpenAPI.

            if text.lower() in {
                "string",
                "null",
                "none",
                "nan",
                "nat",
            }:

                invalid_values.append(value)
                parsed_timestamps.append(pd.NaT)
                continue

            try:

                parsed = pd.to_datetime(
                    text,
                    errors="raise",
                )

                parsed_timestamps.append(parsed)

            except Exception:

                invalid_values.append(value)
                parsed_timestamps.append(pd.NaT)

        if invalid_values:

            examples = [
                repr(value)
                for value in invalid_values[:5]
            ]

            raise ValueError(
                "Terdapat timestamp yang tidak valid. "
                "Nilai bermasalah: "
                + ", ".join(examples)
            )

        dataframe["timestamp"] = pd.to_datetime(
            parsed_timestamps
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

        if dataframe[
            FEATURES
        ].isna().any().any():

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
        # Infinite
        # ----------------------------------------------------

        feature_values = dataframe[
            FEATURES
        ].to_numpy(
            dtype=np.float32
        )

        if not np.isfinite(
            feature_values
        ).all():

            raise ValueError(
                "Terdapat nilai infinite pada fitur."
            )

        # ----------------------------------------------------
        # Sort
        # ----------------------------------------------------

        dataframe = dataframe.sort_values(
            "timestamp"
        ).reset_index(
            drop=True
        )

        return dataframe

    # ========================================================
    # GET LAST WINDOW
    # ========================================================

    def prepare_input(
        self,
        dataframe: pd.DataFrame,
    ) -> tuple[
        np.ndarray,
        pd.Timestamp,
    ]:

        dataframe = self.validate_dataframe(
            dataframe
        )

        if len(dataframe) < INPUT_TIMESTEPS:

            raise ValueError(
                "Data tidak cukup untuk forecast. "
                f"Dibutuhkan minimal "
                f"{INPUT_TIMESTEPS} timestep, "
                f"tetapi hanya tersedia "
                f"{len(dataframe)}."
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

        return (
            values,
            last_timestamp,
        )

    # ========================================================
    # CHECK TIMESTEP
    # ========================================================

    def _validate_timestep_interval(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Validasi apakah data memiliki interval 5 detik.

        Tidak dibuat terlalu ketat supaya API tetap bisa
        menerima data realtime dari backend.

        Jika ada interval berbeda, hanya diberi warning.
        """

        if len(dataframe) < 2:
            return

        timestamps = dataframe[
            "timestamp"
        ].sort_values()

        differences = (
            timestamps
            .diff()
            .dropna()
            .dt.total_seconds()
        )

        if differences.empty:
            return

        invalid = differences[
            differences != STEP_SECONDS
        ]

        if not invalid.empty:

            print(
                "WARNING: Dataset memiliki interval "
                "timestamp selain 5 detik."
            )

            print(
                f"Interval unik: "
                f"{sorted(differences.unique())}"
            )

    # ========================================================
    # PREDICT
    # ========================================================

    @torch.no_grad()
    def predict_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> dict[str, Any]:

        """
        Forecast dari dataframe.

        Input:
            minimal 12 timestep.

        Output:
            3 timestep:
                +5
                +10
                +15 detik
        """

        # ----------------------------------------------------
        # Load model
        # ----------------------------------------------------

        self.load()

        if self.model is None:
            raise RuntimeError(
                "Model belum tersedia."
            )

        # ----------------------------------------------------
        # Prepare input
        # ----------------------------------------------------

        values, last_timestamp = (
            self.prepare_input(
                dataframe
            )
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

        # [12, 4] → [1, 12, 4]

        tensor = tensor.unsqueeze(0)

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

        # [3, 4]

        prediction = prediction[0]

        # ----------------------------------------------------
        # Inverse scaling
        # ----------------------------------------------------

        prediction_original = (
            self._inverse_transform(
                prediction
            )
        )

        # ----------------------------------------------------
        # Business safety
        # ----------------------------------------------------

        # vehicle count >= 0

        prediction_original[:, 0] = np.maximum(
            prediction_original[:, 0],
            0.0,
        )

        # queue vehicles >= 0

        prediction_original[:, 1] = np.maximum(
            prediction_original[:, 1],
            0.0,
        )

        # queue meters >= 0

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
        # Build forecast
        # ----------------------------------------------------

        forecasts: list[
            dict[str, Any]
        ] = []

        for index in range(
            OUTPUT_TIMESTEPS
        ):

            timestamp = (
                last_timestamp
                + timedelta(
                    seconds=(
                        STEP_SECONDS
                        * (index + 1)
                    )
                )
            )

            row = {
                "timestamp": timestamp.isoformat(),

                "vehicleCount": round(
                    float(
                        prediction_original[
                            index,
                            0,
                        ]
                    ),
                    4,
                ),

                "queueLengthVeh": round(
                    float(
                        prediction_original[
                            index,
                            1,
                        ]
                    ),
                    4,
                ),

                "queueLengthMEst": round(
                    float(
                        prediction_original[
                            index,
                            2,
                        ]
                    ),
                    4,
                ),

                "densityIndex": round(
                    float(
                        prediction_original[
                            index,
                            3,
                        ]
                    ),
                    4,
                ),

                "secondsAhead": (
                    STEP_SECONDS
                    * (index + 1)
                ),
            }

            forecasts.append(row)

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {
            "model": {
                "type": "LSTM",

                "inputTimesteps": (
                    INPUT_TIMESTEPS
                ),

                "outputTimesteps": (
                    OUTPUT_TIMESTEPS
                ),

                "stepSeconds": STEP_SECONDS,

                "forecastSeconds": (
                    OUTPUT_TIMESTEPS
                    * STEP_SECONDS
                ),

                "features": FEATURES,
            },

            "input": {
                "timestepsUsed": (
                    INPUT_TIMESTEPS
                ),

                "lastTimestamp": (
                    last_timestamp.isoformat()
                ),

                "latestValues": {
                    FEATURES[index]: float(
                        values[
                            -1,
                            index,
                        ]
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
        records: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:

        """
        Forecast dari list JSON records.
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
    # PREDICT FROM VALUES
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
        Helper untuk TrafficStateBuilder.

        Semua array harus memiliki jumlah elemen
        yang sama dan minimal 12 timestep.
        """

        lengths = {
            len(timestamps),
            len(vehicle_count),
            len(queue_length_veh),
            len(queue_length_m_est),
            len(density_index),
        }

        if len(lengths) != 1:

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

    def health(
        self,
    ) -> dict[str, Any]:

        """
        Status forecasting service.

        Health endpoint TIDAK memaksa model loading.
        """

        model_exists = (
            self.model_path.exists()
        )

        scaler_exists = (
            self.scaler_path.exists()
        )

        metadata_exists = (
            self.metadata_path.exists()
        )

        return {
            "loaded": self.loaded,

            "device": str(
                self.device
            ),

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

            "inputTimesteps": (
                INPUT_TIMESTEPS
            ),

            "outputTimesteps": (
                OUTPUT_TIMESTEPS
            ),

            "stepSeconds": (
                STEP_SECONDS
            ),

            "forecastSeconds": (
                OUTPUT_TIMESTEPS
                * STEP_SECONDS
            ),

            "scalerType": "MinMaxScaler",
        }

    # ========================================================
    # LOAD TEST
    # ========================================================

    def test_load(
        self,
    ) -> dict[str, Any]:

        """
        Memaksa load model.

        Berguna untuk endpoint:
            /api/forecast/health/load
        """

        self.load()

        return self.health()


# ============================================================
# SINGLETON
# ============================================================

forecast_service = ForecastService()
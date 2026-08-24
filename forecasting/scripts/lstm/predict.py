from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
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

HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "lstm"

MODEL_PATH = OUTPUT_DIR / "traffic_lstm.pt"
SCALER_PATH = OUTPUT_DIR / "scaler.json"
METADATA_PATH = OUTPUT_DIR / "metadata.json"

PREDICTION_OUTPUT = OUTPUT_DIR / "live_forecast.csv"


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Device: {DEVICE}")

if torch.cuda.is_available():
    print("CUDA tersedia. Menggunakan GPU.")
else:
    print("CUDA tidak tersedia. Menggunakan CPU.")


# ============================================================
# MODEL
# ============================================================

class TrafficLSTM(nn.Module):
    """
    SmartTwin Traffic Forecasting LSTM

    Input:
        [batch, 12, 4]

    Output:
        [batch, 3, 4]
    """

    def __init__(
        self,
        input_size: int = 4,
        hidden_size: int = 64,
        num_layers: int = 2,
        output_timesteps: int = 3,
        dropout: float = 0.2,
    ):
        super().__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_timesteps = output_timesteps

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        self.fc = nn.Linear(
            hidden_size,
            output_timesteps * input_size,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:

        output, _ = self.lstm(x)

        last_hidden = output[:, -1, :]

        prediction = self.fc(last_hidden)

        prediction = prediction.view(
            -1,
            self.output_timesteps,
            self.input_size,
        )

        return prediction


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description="SmartTwin LSTM Traffic Forecast"
    )

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path CSV dataset gabungan",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path output forecast CSV",
    )

    return parser.parse_args()


# ============================================================
# METADATA
# ============================================================

def load_metadata() -> dict[str, Any]:

    if not METADATA_PATH.exists():

        print(
            "WARNING: metadata.json tidak ditemukan."
        )

        return {
            "features": FEATURES,
            "input_timesteps": INPUT_TIMESTEPS,
            "output_timesteps": OUTPUT_TIMESTEPS,
            "hidden_size": HIDDEN_SIZE,
            "num_layers": NUM_LAYERS,
            "dropout": DROPOUT,
        }

    try:

        with open(
            METADATA_PATH,
            "r",
            encoding="utf-8",
        ) as file:

            metadata = json.load(file)

    except Exception as error:

        print(
            f"WARNING: gagal membaca metadata.json: {error}"
        )

        return {
            "features": FEATURES,
            "input_timesteps": INPUT_TIMESTEPS,
            "output_timesteps": OUTPUT_TIMESTEPS,
            "hidden_size": HIDDEN_SIZE,
            "num_layers": NUM_LAYERS,
            "dropout": DROPOUT,
        }

    if not isinstance(metadata, dict):

        print(
            "WARNING: metadata.json bukan object/dictionary."
        )

        return {
            "features": FEATURES,
            "input_timesteps": INPUT_TIMESTEPS,
            "output_timesteps": OUTPUT_TIMESTEPS,
            "hidden_size": HIDDEN_SIZE,
            "num_layers": NUM_LAYERS,
            "dropout": DROPOUT,
        }

    return metadata


# ============================================================
# SCALER
# ============================================================

class SimpleMinMaxScaler:
    """
    Scaler sederhana yang kompatibel dengan scaler.json
    """

    def __init__(
        self,
        data_min: np.ndarray,
        data_max: np.ndarray,
    ):

        self.data_min_ = np.asarray(
            data_min,
            dtype=np.float64,
        )

        self.data_max_ = np.asarray(
            data_max,
            dtype=np.float64,
        )

        self.scale_ = np.where(
            self.data_max_ - self.data_min_ == 0,
            1.0,
            self.data_max_ - self.data_min_,
        )

    def transform(
        self,
        data: np.ndarray,
    ) -> np.ndarray:

        return (
            data - self.data_min_
        ) / self.scale_

    def inverse_transform(
        self,
        data: np.ndarray,
    ) -> np.ndarray:

        return (
            data * self.scale_
        ) + self.data_min_


def load_scaler() -> SimpleMinMaxScaler:

    if not SCALER_PATH.exists():

        raise FileNotFoundError(
            f"""
Scaler tidak ditemukan:

{SCALER_PATH}

Jalankan training terlebih dahulu:

py scripts/lstm/train.py
"""
        )

    with open(
        SCALER_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        scaler_data = json.load(file)

    # --------------------------------------------------------
    # Format scaler dari train.py
    # --------------------------------------------------------

    if isinstance(scaler_data, dict):

        data_min = None
        data_max = None

        # format umum
        if "data_min" in scaler_data:
            data_min = scaler_data["data_min"]

        elif "data_min_" in scaler_data:
            data_min = scaler_data["data_min_"]

        if "data_max" in scaler_data:
            data_max = scaler_data["data_max"]

        elif "data_max_" in scaler_data:
            data_max = scaler_data["data_max_"]

        # format nested
        if data_min is None and "scaler" in scaler_data:

            nested = scaler_data["scaler"]

            if isinstance(nested, dict):

                data_min = nested.get(
                    "data_min",
                    nested.get("data_min_"),
                )

                data_max = nested.get(
                    "data_max",
                    nested.get("data_max_"),
                )

        if data_min is not None and data_max is not None:

            return SimpleMinMaxScaler(
                np.asarray(data_min),
                np.asarray(data_max),
            )

    raise ValueError(
        f"""
Format scaler.json tidak dikenali.

File:

{SCALER_PATH}
"""
    )


# ============================================================
# MODEL LOADING
# ============================================================

def load_model(
    metadata: dict[str, Any],
) -> TrafficLSTM:

    if not MODEL_PATH.exists():

        raise FileNotFoundError(
            f"""
Model tidak ditemukan:

{MODEL_PATH}

Jalankan:

py scripts/lstm/train.py
"""
        )

    # --------------------------------------------------------
    # Ambil konfigurasi dengan aman
    # --------------------------------------------------------

    hidden_size = metadata.get(
        "hidden_size",
        HIDDEN_SIZE,
    )

    num_layers = metadata.get(
        "num_layers",
        NUM_LAYERS,
    )

    dropout = metadata.get(
        "dropout",
        DROPOUT,
    )

    # Pastikan bukan string
    try:
        hidden_size = int(hidden_size)
    except Exception:
        hidden_size = HIDDEN_SIZE

    try:
        num_layers = int(num_layers)
    except Exception:
        num_layers = NUM_LAYERS

    try:
        dropout = float(dropout)
    except Exception:
        dropout = DROPOUT

    model = TrafficLSTM(
        input_size=len(FEATURES),
        hidden_size=hidden_size,
        num_layers=num_layers,
        output_timesteps=OUTPUT_TIMESTEPS,
        dropout=dropout,
    )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=DEVICE,
        weights_only=False,
    )

    # --------------------------------------------------------
    # Handle berbagai format checkpoint
    # --------------------------------------------------------

    if isinstance(checkpoint, dict):

        if "model_state_dict" in checkpoint:

            state_dict = checkpoint[
                "model_state_dict"
            ]

        elif "state_dict" in checkpoint:

            state_dict = checkpoint[
                "state_dict"
            ]

        else:

            # Bisa jadi checkpoint langsung state_dict
            state_dict = checkpoint

    else:

        state_dict = checkpoint

    model.load_state_dict(
        state_dict,
        strict=True,
    )

    model.to(DEVICE)

    model.eval()

    print()
    print("Model berhasil dimuat:")
    print(f"  Path       : {MODEL_PATH}")
    print(f"  Hidden     : {hidden_size}")
    print(f"  Layers     : {num_layers}")
    print(f"  Dropout    : {dropout}")

    return model


# ============================================================
# INPUT CSV
# ============================================================

def load_input_csv(
    input_path: str,
) -> pd.DataFrame:

    path = Path(input_path)

    if not path.is_absolute():

        path = PROJECT_ROOT / path

    path = path.resolve()

    if not path.exists():

        raise FileNotFoundError(
            f"""
File input tidak ditemukan:

{path}

Contoh penggunaan:

py scripts/lstm/predict.py --input "outputs/lstm/data_gabungan.csv"
"""
        )

    dataframe = pd.read_csv(path)

    print()
    print(f"Input file : {path}")
    print(f"Jumlah row : {len(dataframe)}")

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    if "timestamp" not in dataframe.columns:

        raise ValueError(
            "CSV wajib mempunyai kolom timestamp."
        )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=["timestamp"]
    )

    # --------------------------------------------------------
    # Features
    # --------------------------------------------------------

    missing_features = [
        feature
        for feature in FEATURES
        if feature not in dataframe.columns
    ]

    if missing_features:

        raise ValueError(
            "Feature berikut tidak ditemukan:\n"
            + "\n".join(
                f"  - {feature}"
                for feature in missing_features
            )
        )

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    for feature in FEATURES:

        dataframe[feature] = pd.to_numeric(
            dataframe[feature],
            errors="coerce",
        )

    dataframe = dataframe.dropna(
        subset=FEATURES
    )

    dataframe = dataframe.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    return dataframe


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_input(
    dataframe: pd.DataFrame,
) -> None:

    if len(dataframe) < INPUT_TIMESTEPS:

        raise ValueError(
            f"""
Data tidak cukup.

Dibutuhkan minimal:
{INPUT_TIMESTEPS} timestep

Tersedia:
{len(dataframe)} timestep
"""
        )

    print()
    print("Validasi input:")

    print(
        f"  timestamp : {dataframe['timestamp'].min()}"
    )

    print(
        f"  sampai    : {dataframe['timestamp'].max()}"
    )

    print(
        f"  timestep  : {len(dataframe)}"
    )

    print()

    print("Fitur terakhir:")

    print(
        dataframe[
            ["timestamp"] + FEATURES
        ].tail(INPUT_TIMESTEPS).to_string(
            index=False
        )
    )


# ============================================================
# PREPARE INPUT
# ============================================================

def prepare_input(
    dataframe: pd.DataFrame,
    scaler: SimpleMinMaxScaler,
) -> np.ndarray:

    # Ambil 12 timestep terakhir
    recent = dataframe[
        FEATURES
    ].tail(INPUT_TIMESTEPS)

    values = recent.to_numpy(
        dtype=np.float32
    )

    # Scaling
    scaled = scaler.transform(
        values
    )

    scaled = scaled.astype(
        np.float32
    )

    # [1, 12, 4]
    tensor = torch.tensor(
        scaled,
        dtype=torch.float32,
        device=DEVICE,
    ).unsqueeze(0)

    print()
    print("Input tensor:")
    print(f"  Shape: {tuple(tensor.shape)}")

    return tensor


# ============================================================
# PREDICTION
# ============================================================

def run_prediction(
    dataframe: pd.DataFrame,
    model: TrafficLSTM,
    scaler: SimpleMinMaxScaler,
) -> pd.DataFrame:

    input_tensor = prepare_input(
        dataframe,
        scaler,
    )

    with torch.no_grad():

        prediction_scaled = model(
            input_tensor
        )

    prediction_scaled = (
        prediction_scaled
        .squeeze(0)
        .cpu()
        .numpy()
    )

    # [3, 4]

    prediction = scaler.inverse_transform(
        prediction_scaled
    )

    # --------------------------------------------------------
    # Safety constraints
    # --------------------------------------------------------

    # vehicle count tidak boleh negatif
    prediction[:, 0] = np.maximum(
        prediction[:, 0],
        0,
    )

    # queue kendaraan tidak boleh negatif
    prediction[:, 1] = np.maximum(
        prediction[:, 1],
        0,
    )

    # queue meter tidak boleh negatif
    prediction[:, 2] = np.maximum(
        prediction[:, 2],
        0,
    )

    # density 0..1
    prediction[:, 3] = np.clip(
        prediction[:, 3],
        0,
        1,
    )

    # --------------------------------------------------------
    # Forecast timestamps
    # --------------------------------------------------------

    last_timestamp = dataframe[
        "timestamp"
    ].iloc[-1]

    timestamps = [
        last_timestamp
        + pd.Timedelta(
            seconds=5 * (index + 1)
        )
        for index in range(
            OUTPUT_TIMESTEPS
        )
    ]

    result = pd.DataFrame(
        prediction,
        columns=FEATURES,
    )

    result.insert(
        0,
        "timestamp",
        timestamps,
    )

    return result


# ============================================================
# PRINT RESULT
# ============================================================

def print_forecast(
    result: pd.DataFrame,
) -> None:

    print()
    print(
        "=" * 70
    )

    print(
        "FORECAST 15 DETIK KE DEPAN"
    )

    print(
        "=" * 70
    )

    print()

    print(
        result.to_string(
            index=False,
            float_format=lambda value: (
                f"{value:.4f}"
            ),
        )
    )

    print()

    print(
        "Forecast timestep:"
    )

    for index, row in result.iterrows():

        print(
            f"  +{(index + 1) * 5:02d} detik"
            f" | vehicle={row['vehicleCount']:.2f}"
            f" | queueVeh={row['queueLengthVeh']:.2f}"
            f" | queueM={row['queueLengthMEst']:.2f}"
            f" | density={row['densityIndex']:.4f}"
        )


# ============================================================
# SAVE RESULT
# ============================================================

def save_prediction(
    result: pd.DataFrame,
    output_path: str | None,
) -> Path:

    if output_path is None:

        path = PREDICTION_OUTPUT

    else:

        path = Path(output_path)

        if not path.is_absolute():

            path = PROJECT_ROOT / path

        path = path.resolve()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        path,
        index=False,
    )

    print()
    print(
        f"Prediction saved:"
    )

    print(
        path
    )

    return path


# ============================================================
# JSON RESULT
# ============================================================

def save_json_result(
    result: pd.DataFrame,
) -> Path:

    path = OUTPUT_DIR / "latest_forecast.json"

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "model": "traffic_lstm",
        "input_timesteps": INPUT_TIMESTEPS,
        "output_timesteps": OUTPUT_TIMESTEPS,
        "forecast_seconds": 15,
        "features": FEATURES,
        "predictions": [],
    }

    for _, row in result.iterrows():

        payload["predictions"].append(
            {
                "timestamp": row[
                    "timestamp"
                ].isoformat(),

                "vehicleCount": float(
                    row["vehicleCount"]
                ),

                "queueLengthVeh": float(
                    row["queueLengthVeh"]
                ),

                "queueLengthMEst": float(
                    row["queueLengthMEst"]
                ),

                "densityIndex": float(
                    row["densityIndex"]
                ),
            }
        )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            indent=2,
        )

    print(
        f"JSON forecast saved:"
    )

    print(
        path
    )

    return path


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_args()

    print()
    print(
        "=" * 70
    )

    print(
        "SMARTTWIN - LSTM TRAFFIC FORECAST"
    )

    print(
        "=" * 70
    )

    print()
    print("MODEL CONTRACT")
    print(
        "Input : "
        f"{INPUT_TIMESTEPS} timestep × "
        f"{len(FEATURES)} fitur"
    )

    print(
        "Output: "
        f"{OUTPUT_TIMESTEPS} timestep × "
        f"{len(FEATURES)} fitur"
    )

    print()
    print("Features:")

    for feature in FEATURES:

        print(
            f"  - {feature}"
        )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = load_metadata()

    # --------------------------------------------------------
    # Input
    # --------------------------------------------------------

    dataframe = load_input_csv(
        args.input
    )

    print()

    print(
        f"Jumlah timestep input: "
        f"{len(dataframe)}"
    )

    print(
        f"Menggunakan "
        f"{INPUT_TIMESTEPS} timestep terakhir."
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    validate_input(
        dataframe
    )

    # --------------------------------------------------------
    # Scaler
    # --------------------------------------------------------

    scaler = load_scaler()

    print()
    print(
        "Scaler berhasil dimuat:"
    )

    print(
        f"  {SCALER_PATH}"
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = load_model(
        metadata
    )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    print()
    print(
        "[1] Running prediction..."
    )

    result = run_prediction(
        dataframe=dataframe,
        model=model,
        scaler=scaler,
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print_forecast(
        result
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_prediction(
        result,
        args.output,
    )

    save_json_result(
        result
    )

    # --------------------------------------------------------
    # Finish
    # --------------------------------------------------------

    print()
    print(
        "=" * 70
    )

    print(
        "FORECAST SELESAI"
    )

    print(
        "=" * 70
    )

    print()
    print(
        "Output CSV:"
    )

    print(
        PREDICTION_OUTPUT
    )

    print()
    print(
        "Output JSON:"
    )

    print(
        OUTPUT_DIR / "latest_forecast.json"
    )

    print()


if __name__ == "__main__":
    main()
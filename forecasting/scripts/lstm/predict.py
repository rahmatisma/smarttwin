from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn


# ============================================================
# PATH
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
FORECASTING_ROOT = SCRIPT_DIR.parents[1]

OUTPUT_DIR = FORECASTING_ROOT / "outputs" / "lstm"

MODEL_PATH = OUTPUT_DIR / "traffic_lstm.pt"
SCALER_PATH = OUTPUT_DIR / "scaler.json"
METADATA_PATH = OUTPUT_DIR / "metadata.json"

FEATURES = [
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
]

INPUT_TIMESTEPS = 12
OUTPUT_TIMESTEPS = 3


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Device: {DEVICE}")

if torch.cuda.is_available():
    print(f"CUDA device: {torch.cuda.get_device_name(0)}")
else:
    print("CUDA tidak tersedia. Menggunakan CPU.")


# ============================================================
# MODEL
# ============================================================

class TrafficLSTM(nn.Module):
    """
    Model LSTM untuk forecasting traffic.

    Input:
        batch × 12 × 4

    Output:
        batch × 3 × 4
    """

    def __init__(
        self,
        input_size: int = 4,
        hidden_size: int = 64,
        num_layers: int = 2,
        output_timesteps: int = 3,
        dropout: float = 0.2,
    ) -> None:
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
# JSON UTILITIES
# ============================================================

def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"File tidak ditemukan:\n{path}"
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# LOAD MODEL
# ============================================================

def load_model() -> TrafficLSTM:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model tidak ditemukan:\n{MODEL_PATH}"
        )

    metadata = load_json(METADATA_PATH)

    model_config = metadata.get("model", {})

    hidden_size = int(
        model_config.get("hidden_size", 64)
    )

    num_layers = int(
        model_config.get("num_layers", 2)
    )

    dropout = float(
        model_config.get("dropout", 0.2)
    )

    input_size = len(FEATURES)

    model = TrafficLSTM(
        input_size=input_size,
        hidden_size=hidden_size,
        num_layers=num_layers,
        output_timesteps=OUTPUT_TIMESTEPS,
        dropout=dropout,
    )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=DEVICE,
    )

    # --------------------------------------------------------
    # Support beberapa format penyimpanan model
    # --------------------------------------------------------

    if isinstance(checkpoint, dict):

        if "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]

        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]

        else:
            state_dict = checkpoint

    else:
        state_dict = checkpoint

    model.load_state_dict(state_dict)

    model.to(DEVICE)
    model.eval()

    print()
    print("Model berhasil dimuat.")
    print(f"Model : {MODEL_PATH}")
    print(f"Device: {DEVICE}")

    return model


# ============================================================
# SCALER
# ============================================================

class FeatureScaler:
    """
    Scaler kompatibel dengan scaler.json hasil training.

    Mendukung:
    - StandardScaler-style
    - MinMaxScaler-style
    """

    def __init__(
        self,
        scaler_data: dict[str, Any],
    ) -> None:

        self.data = scaler_data

        self.scaler_type = (
            scaler_data.get("type")
            or scaler_data.get("scaler_type")
            or scaler_data.get("name")
            or "standard"
        ).lower()

        # ----------------------------------------------------
        # Format per-feature
        # ----------------------------------------------------

        self.feature_data = scaler_data.get(
            "features",
            {}
        )

        # ----------------------------------------------------
        # Format sklearn-like
        # ----------------------------------------------------

        self.mean = np.asarray(
            scaler_data.get("mean", []),
            dtype=np.float32,
        )

        self.scale = np.asarray(
            scaler_data.get("scale", []),
            dtype=np.float32,
        )

        self.min_value = np.asarray(
            scaler_data.get("min", []),
            dtype=np.float32,
        )

        self.data_min = np.asarray(
            scaler_data.get("data_min", []),
            dtype=np.float32,
        )

        self.data_max = np.asarray(
            scaler_data.get("data_max", []),
            dtype=np.float32,
        )

        self.feature_names = scaler_data.get(
            "feature_names",
            FEATURES,
        )

    def _feature_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Mengambil parameter scaler untuk setiap fitur.
        """

        # ====================================================
        # FORMAT:
        #
        # {
        #   "features": {
        #       "vehicleCount": {
        #           "mean": ...,
        #           "scale": ...
        #       }
        #   }
        # }
        # ====================================================

        if self.feature_data:

            first_feature = next(
                iter(self.feature_data.values())
            )

            if isinstance(first_feature, dict):

                if (
                    "mean" in first_feature
                    and "scale" in first_feature
                ):
                    means = []
                    scales = []

                    for feature in FEATURES:

                        info = self.feature_data[feature]

                        means.append(
                            float(info["mean"])
                        )

                        scales.append(
                            float(info["scale"])
                        )

                    return (
                        np.asarray(
                            means,
                            dtype=np.float32,
                        ),
                        np.asarray(
                            scales,
                            dtype=np.float32,
                        ),
                    )

                if (
                    "data_min" in first_feature
                    and "data_max" in first_feature
                ):
                    mins = []
                    maxs = []

                    for feature in FEATURES:

                        info = self.feature_data[feature]

                        mins.append(
                            float(info["data_min"])
                        )

                        maxs.append(
                            float(info["data_max"])
                        )

                    return (
                        np.asarray(
                            mins,
                            dtype=np.float32,
                        ),
                        np.asarray(
                            maxs,
                            dtype=np.float32,
                        ),
                    )

        # ====================================================
        # FORMAT SKLEARN STANDARD SCALER
        # ====================================================

        if (
            self.mean.size == len(FEATURES)
            and self.scale.size == len(FEATURES)
        ):
            return self.mean, self.scale

        # ====================================================
        # FORMAT SKLEARN MINMAX
        # ====================================================

        if (
            self.data_min.size == len(FEATURES)
            and self.data_max.size == len(FEATURES)
        ):
            return self.data_min, self.data_max

        raise ValueError(
            "Format scaler.json tidak dikenali.\n"
            f"Isi scaler.json:\n{self.data}"
        )

    def transform(
        self,
        values: np.ndarray,
    ) -> np.ndarray:

        values = np.asarray(
            values,
            dtype=np.float32,
        )

        if values.ndim == 1:
            values = values.reshape(1, -1)

        # ----------------------------------------------------
        # StandardScaler
        # ----------------------------------------------------

        if self.scaler_type in {
            "standard",
            "standardscaler",
        }:

            mean, scale = self._feature_arrays()

            return (values - mean) / scale

        # ----------------------------------------------------
        # MinMaxScaler
        # ----------------------------------------------------

        if self.scaler_type in {
            "minmax",
            "minmaxscaler",
        }:

            data_min, data_max = self._feature_arrays()

            denominator = data_max - data_min

            denominator = np.where(
                denominator == 0,
                1.0,
                denominator,
            )

            return (
                (values - data_min)
                / denominator
            )

        raise ValueError(
            f"Scaler type tidak didukung: "
            f"{self.scaler_type}"
        )

    def inverse_transform(
        self,
        values: np.ndarray,
    ) -> np.ndarray:

        values = np.asarray(
            values,
            dtype=np.float32,
        )

        original_shape = values.shape

        if values.ndim == 3:

            batch, timesteps, features = values.shape

            flat = values.reshape(
                -1,
                features,
            )

            restored = self._inverse_2d(flat)

            return restored.reshape(
                original_shape
            )

        if values.ndim == 2:

            return self._inverse_2d(values)

        if values.ndim == 1:

            return self._inverse_2d(
                values.reshape(1, -1)
            ).reshape(-1)

        raise ValueError(
            "Dimensi data tidak didukung."
        )

    def _inverse_2d(
        self,
        values: np.ndarray,
    ) -> np.ndarray:

        if self.scaler_type in {
            "standard",
            "standardscaler",
        }:

            mean, scale = self._feature_arrays()

            return (
                values * scale
                + mean
            )

        if self.scaler_type in {
            "minmax",
            "minmaxscaler",
        }:

            data_min, data_max = self._feature_arrays()

            return (
                values
                * (data_max - data_min)
                + data_min
            )

        raise ValueError(
            f"Scaler type tidak didukung: "
            f"{self.scaler_type}"
        )


# ============================================================
# LOAD SCALER
# ============================================================

def load_scaler() -> FeatureScaler:

    scaler_data = load_json(
        SCALER_PATH
    )

    scaler = FeatureScaler(
        scaler_data
    )

    print()
    print("Scaler berhasil dimuat.")
    print(f"Scaler: {SCALER_PATH}")

    return scaler


# ============================================================
# VALIDATE INPUT
# ============================================================

def validate_input(
    dataframe: pd.DataFrame,
) -> None:

    missing = [
        feature
        for feature in FEATURES
        if feature not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            "Feature input tidak lengkap.\n"
            f"Feature yang hilang: {missing}"
        )

    if len(dataframe) < INPUT_TIMESTEPS:
        raise ValueError(
            f"Data input hanya memiliki "
            f"{len(dataframe)} timestep.\n"
            f"Minimal diperlukan "
            f"{INPUT_TIMESTEPS} timestep."
        )


# ============================================================
# PREPARE INPUT
# ============================================================

def prepare_input(
    dataframe: pd.DataFrame,
    scaler: FeatureScaler,
) -> np.ndarray:

    validate_input(dataframe)

    latest = dataframe[
        FEATURES
    ].tail(INPUT_TIMESTEPS).copy()

    latest = latest.astype(
        np.float32
    )

    values = latest.values

    scaled = scaler.transform(
        values
    )

    x = scaled.reshape(
        1,
        INPUT_TIMESTEPS,
        len(FEATURES),
    )

    return x


# ============================================================
# FORECAST
# ============================================================

@torch.no_grad()
def forecast(
    model: TrafficLSTM,
    input_data: np.ndarray,
    scaler: FeatureScaler,
) -> np.ndarray:

    tensor = torch.tensor(
        input_data,
        dtype=torch.float32,
        device=DEVICE,
    )

    prediction_scaled = model(
        tensor
    )

    prediction_scaled = (
        prediction_scaled
        .detach()
        .cpu()
        .numpy()
    )

    prediction = (
        scaler.inverse_transform(
            prediction_scaled
        )
    )

    return prediction[0]


# ============================================================
# CLEAN PREDICTION
# ============================================================

def clean_predictions(
    predictions: np.ndarray,
) -> np.ndarray:

    predictions = np.asarray(
        predictions,
        dtype=np.float32,
    )

    # --------------------------------------------------------
    # Nilai tidak boleh negatif
    # --------------------------------------------------------

    predictions[:, 0] = np.maximum(
        predictions[:, 0],
        0,
    )

    predictions[:, 1] = np.maximum(
        predictions[:, 1],
        0,
    )

    predictions[:, 2] = np.maximum(
        predictions[:, 2],
        0,
    )

    predictions[:, 3] = np.clip(
        predictions[:, 3],
        0,
        1,
    )

    return predictions


# ============================================================
# FORMAT RESULT
# ============================================================

def create_prediction_dataframe(
    predictions: np.ndarray,
    last_timestamp: pd.Timestamp | None = None,
) -> pd.DataFrame:

    # --------------------------------------------------------
    # Horizon
    # --------------------------------------------------------

    horizons = [
        5,
        10,
        15,
    ]

    rows = []

    for index, horizon in enumerate(horizons):

        row = {
            "horizonSeconds": horizon,

            "vehicleCount": float(
                predictions[index, 0]
            ),

            "queueLengthVeh": float(
                predictions[index, 1]
            ),

            "queueLengthMEst": float(
                predictions[index, 2]
            ),

            "densityIndex": float(
                predictions[index, 3]
            ),
        }

        if last_timestamp is not None:

            row["forecastTimestamp"] = (
                last_timestamp
                + pd.Timedelta(
                    seconds=horizon
                )
            )

        rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# PRINT RESULT
# ============================================================

def print_predictions(
    dataframe: pd.DataFrame,
) -> None:

    print()
    print("=" * 70)
    print("HASIL FORECAST LSTM")
    print("=" * 70)

    for _, row in dataframe.iterrows():

        horizon = int(
            row["horizonSeconds"]
        )

        print()
        print(
            f"Prediksi +{horizon} detik"
        )

        if "forecastTimestamp" in row:

            print(
                "Timestamp : "
                f"{row['forecastTimestamp']}"
            )

        print(
            "vehicleCount      : "
            f"{row['vehicleCount']:.2f}"
        )

        print(
            "queueLengthVeh    : "
            f"{row['queueLengthVeh']:.2f}"
        )

        print(
            "queueLengthMEst   : "
            f"{row['queueLengthMEst']:.2f}"
        )

        print(
            "densityIndex      : "
            f"{row['densityIndex']:.4f}"
        )

    print()
    print("=" * 70)


# ============================================================
# SAVE RESULT
# ============================================================

def save_prediction(
    dataframe: pd.DataFrame,
    output_path: Path,
) -> None:

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Prediction disimpan ke:\n"
        f"{output_path}"
    )


# ============================================================
# LOAD INPUT CSV
# ============================================================

def load_input_csv(
    path: Path,
) -> pd.DataFrame:

    if not path.exists():

        raise FileNotFoundError(
            f"File input tidak ditemukan:\n"
            f"{path}"
        )

    dataframe = pd.read_csv(
        path
    )

    if "timestamp" in dataframe.columns:

        dataframe["timestamp"] = (
            pd.to_datetime(
                dataframe["timestamp"],
                errors="coerce",
            )
        )

        dataframe = dataframe.sort_values(
            "timestamp"
        )

    dataframe = dataframe.reset_index(
        drop=True
    )

    return dataframe


# ============================================================
# DEMO INPUT DARI PREDICTIONS / DATASET
# ============================================================

def create_demo_input_from_training_data() -> pd.DataFrame:
    """
    Fungsi demo.

    Membaca dataset gabungan jika tersedia.

    Prioritas:
        outputs/lstm/merged_training_data.csv

    Kalau file tersebut belum ada, fungsi mencoba
    beberapa lokasi dataset umum.
    """

    candidates = [

        FORECASTING_ROOT
        / "data"
        / "merged_training_data.csv",

        FORECASTING_ROOT
        / "data"
        / "traffic_training.csv",

        FORECASTING_ROOT
        / "datasets"
        / "merged_training_data.csv",

        FORECASTING_ROOT
        / "outputs"
        / "lstm"
        / "merged_training_data.csv",
    ]

    for path in candidates:

        if path.exists():

            print()
            print(
                "Input dataset ditemukan:"
            )
            print(path)

            return load_input_csv(
                path
            )

    raise FileNotFoundError(
        "\nTidak menemukan dataset input demo.\n\n"
        "Gunakan mode file CSV:\n"
        "python scripts/lstm/predict.py "
        "--input path/to/data.csv\n"
    )


# ============================================================
# MAIN PREDICTION
# ============================================================

def run_prediction(
    dataframe: pd.DataFrame,
    output_path: Path | None = None,
) -> pd.DataFrame:

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
    # Load model
    # --------------------------------------------------------

    model = load_model()

    # --------------------------------------------------------
    # Load scaler
    # --------------------------------------------------------

    scaler = load_scaler()

    # --------------------------------------------------------
    # Prepare input
    # --------------------------------------------------------

    input_data = prepare_input(
        dataframe,
        scaler,
    )

    print()
    print(
        "Shape input model:",
        input_data.shape,
    )

    # --------------------------------------------------------
    # Forecast
    # --------------------------------------------------------

    predictions = forecast(
        model=model,
        input_data=input_data,
        scaler=scaler,
    )

    # --------------------------------------------------------
    # Clean
    # --------------------------------------------------------

    predictions = clean_predictions(
        predictions
    )

    # --------------------------------------------------------
    # Timestamp terakhir
    # --------------------------------------------------------

    last_timestamp = None

    if "timestamp" in dataframe.columns:

        valid_timestamp = (
            dataframe["timestamp"]
            .dropna()
        )

        if not valid_timestamp.empty:

            last_timestamp = (
                valid_timestamp.iloc[-1]
            )

    # --------------------------------------------------------
    # Create result
    # --------------------------------------------------------

    result = create_prediction_dataframe(
        predictions=predictions,
        last_timestamp=last_timestamp,
    )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print_predictions(
        result
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    if output_path is not None:

        save_prediction(
            dataframe=result,
            output_path=output_path,
        )

    return result


# ============================================================
# CLI
# ============================================================

def parse_arguments() -> tuple[Path | None, Path | None]:

    input_path = None
    output_path = (
        OUTPUT_DIR
        / "latest_forecast.csv"
    )

    args = sys.argv[1:]

    index = 0

    while index < len(args):

        argument = args[index]

        if argument == "--input":

            if index + 1 >= len(args):

                raise ValueError(
                    "--input membutuhkan path CSV."
                )

            input_path = Path(
                args[index + 1]
            ).resolve()

            index += 2
            continue

        if argument == "--output":

            if index + 1 >= len(args):

                raise ValueError(
                    "--output membutuhkan path."
                )

            output_path = Path(
                args[index + 1]
            ).resolve()

            index += 2
            continue

        if argument in {
            "--help",
            "-h",
        }:

            print(
                """
SMARTTWIN LSTM PREDICTION

Penggunaan:

python scripts/lstm/predict.py --input data.csv

Atau:

python scripts/lstm/predict.py ^
    --input data.csv ^
    --output outputs/lstm/latest_forecast.csv

CSV harus memiliki kolom:

timestamp
vehicleCount
queueLengthVeh
queueLengthMEst
densityIndex

Minimal 12 timestep.
"""
            )

            raise SystemExit(0)

        raise ValueError(
            f"Argument tidak dikenal: {argument}"
        )

    return input_path, output_path


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 70)
    print("SMARTTWIN - LSTM TRAFFIC FORECAST")
    print("=" * 70)

    print()
    print("MODEL CONTRACT")
    print(
        f"Input : "
        f"{INPUT_TIMESTEPS} timestep × "
        f"{len(FEATURES)} fitur"
    )

    print(
        f"Output: "
        f"{OUTPUT_TIMESTEPS} timestep × "
        f"{len(FEATURES)} fitur"
    )

    print()
    print(
        "Features:"
    )

    for feature in FEATURES:

        print(
            f"  - {feature}"
        )

    # --------------------------------------------------------
    # Parse CLI
    # --------------------------------------------------------

    input_path, output_path = (
        parse_arguments()
    )

    # --------------------------------------------------------
    # Input
    # --------------------------------------------------------

    if input_path is not None:

        dataframe = load_input_csv(
            input_path
        )

    else:

        dataframe = (
            create_demo_input_from_training_data()
        )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    result = run_prediction(
        dataframe=dataframe,
        output_path=output_path,
    )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PREDICTION SELESAI")
    print("=" * 70)

    print()
    print(
        f"Output:\n{output_path}"
    )

    print()
    print(
        "Forecast horizon:"
    )

    print(
        "  +5 detik"
    )

    print(
        "  +10 detik"
    )

    print(
        "  +15 detik"
    )


if __name__ == "__main__":
    main()
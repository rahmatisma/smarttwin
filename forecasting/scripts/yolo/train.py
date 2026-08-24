from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler

from torch.optim import Adam
from torch.utils.data import Dataset, DataLoader


# ============================================================
# PATH
# ============================================================

# smarttwin/
#
# forecasting/
# ├── data/
# │   └── percobaan_logic_simpang.csv
# │
# ├── scripts/
# │   └── yolo/
# │       └── train.py
# │
# └── outputs/
#     └── yolo/
#
# backend/
# └── app/

baseDir = Path(__file__).resolve().parents[2]

dataDir = baseDir / "data"

outputDir = baseDir / "outputs" / "yolo"

plotDir = outputDir / "plots"

dataFile = (
    dataDir
    / "percobaan_logic_simpang.csv"
)

modelFile = (
    outputDir
    / "traffic_lstm.pt"
)

onnxModelFile = (
    outputDir
    / "traffic_lstm.onnx"
)

scalerFile = (
    outputDir
    / "scaler.json"
)

metadataFile = (
    outputDir
    / "metadata.json"
)

historyFile = (
    outputDir
    / "training_history.json"
)

predictionsFile = (
    outputDir
    / "predictions.csv"
)

plotLossFile = (
    plotDir
    / "training_validation_loss.png"
)

plotPredictionFile = (
    plotDir
    / "test_predictions.png"
)

outputDir.mkdir(
    parents=True,
    exist_ok=True,
)

plotDir.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# CONFIGURATION
# ============================================================

RANDOM_SEED = 42

INTERVAL_SECONDS = 5

LOOKBACK = 12

HORIZON = 3

TRAIN_RATIO = 0.70

VAL_RATIO = 0.15

TEST_RATIO = 0.15

BATCH_SIZE = 16

EPOCHS = 150

LEARNING_RATE = 0.001

PATIENCE = 20

HIDDEN_SIZE = 64

NUM_LAYERS = 2

DROPOUT = 0.20

GRADIENT_CLIP = 1.0


# ============================================================
# APPROACH CONTRACT
# ============================================================

# IMPORTANT:
#
# Dataset FINAL harus mempunyai empat approach:
#
# north
# south
# east
# west
#
# "simpang_tengah" BUKAN approach.
#
# Kalau data north tidak ada, training dihentikan.
# Kita tidak akan mengarang data north.

APPROACHES = [
    "north",
    "south",
    "east",
    "west",
]


# ============================================================
# APPROACH ALIASES
# ============================================================

APPROACH_ALIASES = {

    "north": {
        "north",
        "utara",
    },

    "south": {
        "south",
        "selatan",
    },

    "east": {
        "east",
        "timur",
    },

    "west": {
        "west",
        "barat",
    },
}


# ============================================================
# CSV FEATURES
# ============================================================

CSV_FEATURES = [
    "total_di_zona",
    "motor_di_zona",
    "mobil_di_zona",
    "truk_di_zona",
    "bus_di_zona",
]


# ============================================================
# CONTRACT MAPPING
# ============================================================

CONTRACT_FEATURE_MAPPING = {

    "total_di_zona":
        "volume",

    "motor_di_zona":
        "motorcycleCount",

    "mobil_di_zona":
        "carCount",

    "truk_di_zona":
        "truckCount",

    "bus_di_zona":
        "busCount",
}


# ============================================================
# CONGESTION CONFIGURATION
# ============================================================

# CSV TIDAK mempunyai kolom congestion aktual.
#
# Maka model TIDAK dilatih langsung terhadap congestion label.
#
# Kita prediksi volume kendaraan terlebih dahulu.
#
# Setelah itu:
#
# congestionIndex =
# predictedVolume / APPROACH_CAPACITY
#
# Nilai dibatasi 0..1.
#
# Interpretasi:
#
# 0.00 - 0.29 = Lancar
# 0.30 - 0.59 = Ramai
# 0.60 - 0.79 = Padat
# 0.80 - 1.00 = Macet
#
# CAPACITY harus dikalibrasi lagi berdasarkan simpang nyata.
#
# Ini hanya proxy congestion, bukan ground truth.

APPROACH_CAPACITY = {

    "north": 15.0,

    "south": 15.0,

    "east": 15.0,

    "west": 15.0,
}


# ============================================================
# RANDOM SEED
# ============================================================

def setSeed(
    seed: int = RANDOM_SEED,
) -> None:

    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():

        torch.cuda.manual_seed_all(
            seed
        )

    torch.backends.cudnn.deterministic = True

    torch.backends.cudnn.benchmark = False


# ============================================================
# DEVICE
# ============================================================

def getDevice():

    if torch.cuda.is_available():

        device = torch.device(
            "cuda"
        )

        print(
            "CUDA tersedia:",
            torch.cuda.get_device_name(0),
        )

        return device

    print(
        "CUDA tidak tersedia. "
        "Menggunakan CPU."
    )

    return torch.device("cpu")


# ============================================================
# DATASET
# ============================================================

class TrafficDataset(Dataset):

    def __init__(
        self,
        inputData: np.ndarray,
        targetData: np.ndarray,
    ):

        self.inputData = torch.tensor(
            inputData,
            dtype=torch.float32,
        )

        self.targetData = torch.tensor(
            targetData,
            dtype=torch.float32,
        )

    def __len__(self):

        return len(
            self.inputData
        )

    def __getitem__(
        self,
        index,
    ):

        return (
            self.inputData[index],
            self.targetData[index],
        )


# ============================================================
# LSTM MODEL
# ============================================================

class TrafficLSTM(
    nn.Module
):

    def __init__(
        self,
        inputSize: int,
        hiddenSize: int,
        numLayers: int,
        horizon: int,
        outputSize: int,
        dropout: float,
    ):

        super().__init__()

        self.horizon = horizon

        self.outputSize = outputSize

        self.lstm = nn.LSTM(

            input_size=inputSize,

            hidden_size=hiddenSize,

            num_layers=numLayers,

            batch_first=True,

            dropout=(
                dropout
                if numLayers > 1
                else 0.0
            ),
        )

        self.fc = nn.Sequential(

            nn.Linear(
                hiddenSize,
                hiddenSize,
            ),

            nn.ReLU(),

            nn.Dropout(
                dropout
            ),

            nn.Linear(
                hiddenSize,
                horizon * outputSize,
            ),
        )

    def forward(
        self,
        inputData,
    ):

        output, _ = self.lstm(
            inputData
        )

        lastOutput = (
            output[:, -1, :]
        )

        prediction = self.fc(
            lastOutput
        )

        prediction = prediction.view(
            -1,
            self.horizon,
            self.outputSize,
        )

        return prediction


# ============================================================
# NORMALIZE APPROACH
# ============================================================

def normalizeApproach(
    value: str,
) -> str:

    value = (
        str(value)
        .strip()
        .lower()
    )

    for canonical, aliases in (
        APPROACH_ALIASES.items()
    ):

        if value in aliases:

            return canonical

    return value


# ============================================================
# LOAD DATA
# ============================================================

def loadData():

    print()
    print(
        "=" * 70
    )
    print(
        "[1] LOADING DATASET"
    )
    print(
        "=" * 70
    )

    if not dataFile.exists():

        raise FileNotFoundError(
            "Dataset tidak ditemukan:\n"
            f"{dataFile}"
        )

    dataFrame = pd.read_csv(
        dataFile
    )

    print(
        "Dataset:",
        dataFile
    )

    print(
        "Raw rows:",
        len(dataFrame)
    )

    requiredColumns = [

        "timestamp",

        "kamera",

        "lengan",

        *CSV_FEATURES,
    ]

    missingColumns = [

        column

        for column in requiredColumns

        if column not in dataFrame.columns
    ]

    if missingColumns:

        raise ValueError(
            "Kolom CSV yang diperlukan "
            "tidak ditemukan:\n"
            + "\n".join(
                f"- {column}"
                for column in missingColumns
            )
        )

    # --------------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------------

    dataFrame["timestamp"] = pd.to_datetime(
        dataFrame["timestamp"],
        errors="coerce",
    )

    dataFrame = dataFrame.dropna(
        subset=[
            "timestamp"
        ]
    )

    # --------------------------------------------------------
    # APPROACH
    # --------------------------------------------------------

    dataFrame["approach"] = (
        dataFrame["lengan"]
        .apply(
            normalizeApproach
        )
    )

    # --------------------------------------------------------
    # FEATURES NUMERIC
    # --------------------------------------------------------

    for column in CSV_FEATURES:

        dataFrame[column] = pd.to_numeric(
            dataFrame[column],
            errors="coerce",
        )

    dataFrame[CSV_FEATURES] = (
        dataFrame[
            CSV_FEATURES
        ]
        .fillna(0.0)
        .clip(lower=0.0)
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    dataFrame = (
        dataFrame
        .sort_values(
            [
                "timestamp",
                "approach",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # REPORT APPROACH
    # --------------------------------------------------------

    print()
    print(
        "Approach ditemukan:"
    )

    for approach in sorted(
        dataFrame["approach"]
        .unique()
    ):

        count = int(
            (
                dataFrame["approach"]
                == approach
            ).sum()
        )

        print(
            f"  {approach:<20} "
            f"{count} rows"
        )

    # --------------------------------------------------------
    # REMOVE NON APPROACH
    # --------------------------------------------------------

    validApproaches = set(
        APPROACHES
    )

    beforeRows = len(
        dataFrame
    )

    dataFrame = dataFrame[
        dataFrame["approach"]
        .isin(
            validApproaches
        )
    ].copy()

    removedRows = (
        beforeRows
        - len(dataFrame)
    )

    print()
    print(
        "Rows non-approach dibuang:",
        removedRows
    )

    # --------------------------------------------------------
    # REQUIRED APPROACH CHECK
    # --------------------------------------------------------

    foundApproaches = set(
        dataFrame["approach"]
        .unique()
    )

    missingApproaches = [
        approach

        for approach in APPROACHES

        if approach not in foundApproaches
    ]

    if missingApproaches:

        raise ValueError(

            "\nDATASET TIDAK VALID "
            "UNTUK MODEL 4 APPROACH.\n\n"

            "Approach yang diwajibkan:\n"

            + "\n".join(
                f"  - {a}"
                for a in APPROACHES
            )

            + "\n\n"
            "Approach yang belum tersedia:\n"

            + "\n".join(
                f"  - {a}"
                for a in missingApproaches
            )

            + "\n\n"
            "JANGAN menganggap "
            "'simpang_tengah' sebagai north.\n"
            "Tambahkan data north/utara "
            "yang sebenarnya ke CSV."
        )

    return dataFrame


# ============================================================
# BUILD COMPLETE TIMESTEPS
# ============================================================

def buildApproachTimeSeries(
    dataFrame: pd.DataFrame,
):

    print()
    print(
        "=" * 70
    )
    print(
        "[2] BUILDING 4-APPROACH TIME SERIES"
    )
    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # DUPLICATE APPROACH / TIMESTAMP
    # --------------------------------------------------------

    duplicateMask = (
        dataFrame
        .duplicated(
            subset=[
                "timestamp",
                "approach",
            ],
            keep=False,
        )
    )

    duplicateRows = dataFrame[
        duplicateMask
    ]

    if len(duplicateRows) > 0:

        print(
            "WARNING:"
        )

        print(
            "Ditemukan duplicate "
            "timestamp + approach:"
        )

        print(
            duplicateRows[
                [
                    "timestamp",
                    "approach",
                ]
            ]
            .head(20)
            .to_string(
                index=False
            )
        )

        # ----------------------------------------------------
        # Aggregate duplicate rows
        # ----------------------------------------------------

        dataFrame = (
            dataFrame
            .groupby(
                [
                    "timestamp",
                    "approach",
                ],
                as_index=False,
            )[CSV_FEATURES]
            .sum()
        )

    # --------------------------------------------------------
    # PIVOT
    # --------------------------------------------------------

    rows = []

    grouped = dataFrame.groupby(
        "timestamp"
    )

    incompleteTimestamps = 0

    for timestamp, group in grouped:

        row = {
            "timestamp": timestamp
        }

        approachesPresent = set(
            group["approach"]
        )

        if not all(
            approach in approachesPresent
            for approach in APPROACHES
        ):

            incompleteTimestamps += 1

            continue

        for approach in APPROACHES:

            approachData = group[
                group["approach"]
                == approach
            ]

            values = (
                approachData[
                    CSV_FEATURES
                ]
                .iloc[0]
                .to_dict()
            )

            for feature in CSV_FEATURES:

                key = (
                    f"{approach}__"
                    f"{feature}"
                )

                row[key] = float(
                    values[feature]
                )

        rows.append(
            row
        )

    timeSeriesData = pd.DataFrame(
        rows
    )

    if timeSeriesData.empty:

        raise ValueError(
            "Tidak ada timestamp lengkap "
            "yang memiliki keempat approach."
        )

    timeSeriesData = (
        timeSeriesData
        .sort_values(
            "timestamp"
        )
        .reset_index(
            drop=True
        )
    )

    print(
        "Timestamp lengkap:",
        len(timeSeriesData)
    )

    print(
        "Timestamp tidak lengkap:",
        incompleteTimestamps
    )

    # --------------------------------------------------------
    # CHECK INTERVAL
    # --------------------------------------------------------

    intervals = (
        timeSeriesData[
            "timestamp"
        ]
        .diff()
        .dt.total_seconds()
        .dropna()
    )

    if len(intervals) > 0:

        print()
        print(
            "Interval median:",
            intervals.median(),
            "seconds"
        )

        print(
            "Interval minimum:",
            intervals.min(),
            "seconds"
        )

        print(
            "Interval maximum:",
            intervals.max(),
            "seconds"
        )

        wrongIntervals = (
            intervals
            != INTERVAL_SECONDS
        ).sum()

        print(
            "Interval bukan 5 detik:",
            int(wrongIntervals)
        )

    # --------------------------------------------------------
    # FEATURE ORDER
    # --------------------------------------------------------

    featureNames = []

    for approach in APPROACHES:

        for feature in CSV_FEATURES:

            featureNames.append(
                f"{approach}__{feature}"
            )

    return (
        timeSeriesData,
        featureNames,
    )


# ============================================================
# CREATE SEQUENCES
# ============================================================

def createSequences(
    values: np.ndarray,
    lookbackValue: int,
    horizonValue: int,
):

    inputSequences = []

    targetSequences = []

    totalLength = len(
        values
    )

    maxStart = (
        totalLength
        - lookbackValue
        - horizonValue
        + 1
    )

    for start in range(
        maxStart
    ):

        end = (
            start
            + lookbackValue
        )

        targetEnd = (
            end
            + horizonValue
        )

        inputSequences.append(
            values[
                start:end
            ]
        )

        targetSequences.append(
            values[
                end:targetEnd
            ]
        )

    return (

        np.asarray(
            inputSequences,
            dtype=np.float32,
        ),

        np.asarray(
            targetSequences,
            dtype=np.float32,
        ),
    )


# ============================================================
# SAVE SCALER
# ============================================================

def saveScaler(
    scaler: MinMaxScaler,
    featureNames: List[str],
) -> None:

    scalerData = {

        "featureNames":
            featureNames,

        "min":
            scaler.min_.tolist(),

        "scale":
            scaler.scale_.tolist(),

        "dataMin":
            scaler.data_min_.tolist(),

        "dataMax":
            scaler.data_max_.tolist(),

        "dataRange":
            scaler.data_range_.tolist(),
    }

    with open(
        scalerFile,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            scalerData,
            file,
            indent=4,
        )

    print(
        "Scaler saved:",
        scalerFile
    )


# ============================================================
# CONGESTION CALCULATION
# ============================================================

def calculateCongestion(
    approach: str,
    volume: float,
) -> Tuple[float, str]:

    capacity = (
        APPROACH_CAPACITY[
            approach
        ]
    )

    if capacity <= 0:

        return (
            0.0,
            "unknown"
        )

    congestionIndex = (
        volume
        / capacity
    )

    congestionIndex = float(
        np.clip(
            congestionIndex,
            0.0,
            1.0,
        )
    )

    if congestionIndex < 0.30:

        level = "lancar"

    elif congestionIndex < 0.60:

        level = "ramai"

    elif congestionIndex < 0.80:

        level = "padat"

    else:

        level = "macet"

    return (
        congestionIndex,
        level,
    )


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def savePredictions(
    timestamps,
    actualValues,
    predictedValues,
    featureNames,
):

    rows = []

    for sampleIndex in range(
        len(timestamps)
    ):

        timestamp = timestamps[
            sampleIndex
        ]

        for horizonIndex in range(
            HORIZON
        ):

            forecastTimestamp = (
                pd.Timestamp(timestamp)
                + pd.Timedelta(
                    seconds=(
                        (
                            horizonIndex
                            + 1
                        )
                        * INTERVAL_SECONDS
                    )
                )
            )

            row = {

                "timestamp":
                    timestamp,

                "forecast_timestamp":
                    forecastTimestamp,

                "horizon_step":
                    horizonIndex + 1,
            }

            for approachIndex, approach in enumerate(
                APPROACHES
            ):

                baseIndex = (
                    approachIndex
                    * len(
                        CSV_FEATURES
                    )
                )

                actualVolume = float(
                    actualValues[
                        sampleIndex,
                        horizonIndex,
                        baseIndex,
                    ]
                )

                predictedVolume = float(
                    predictedValues[
                        sampleIndex,
                        horizonIndex,
                        baseIndex,
                    ]
                )

                predictedVolume = max(
                    0.0,
                    predictedVolume,
                )

                congestionIndex, congestionLevel = (
                    calculateCongestion(
                        approach,
                        predictedVolume,
                    )
                )

                row[
                    f"{approach}_actual_volume"
                ] = actualVolume

                row[
                    f"{approach}_predicted_volume"
                ] = predictedVolume

                row[
                    f"{approach}_congestion_index"
                ] = congestionIndex

                row[
                    f"{approach}_congestion_level"
                ] = congestionLevel

                for featureIndex, featureName in enumerate(
                    CSV_FEATURES
                ):

                    absoluteIndex = (
                        baseIndex
                        + featureIndex
                    )

                    row[
                        f"{approach}_actual_{featureName}"
                    ] = float(
                        actualValues[
                            sampleIndex,
                            horizonIndex,
                            absoluteIndex,
                        ]
                    )

                    row[
                        f"{approach}_predicted_{featureName}"
                    ] = max(
                        0.0,
                        float(
                            predictedValues[
                                sampleIndex,
                                horizonIndex,
                                absoluteIndex,
                            ]
                        ),
                    )

            rows.append(
                row
            )

    predictionsDataFrame = pd.DataFrame(
        rows
    )

    predictionsDataFrame.to_csv(
        predictionsFile,
        index=False,
    )

    print(
        "Predictions saved:",
        predictionsFile
    )


# ============================================================
# PLOT LOSS
# ============================================================

def plotTrainingValidationLoss(
    history,
):

    plt.figure(
        figsize=(10, 6)
    )

    epochsRange = range(
        1,
        len(
            history["trainLoss"]
        ) + 1,
    )

    plt.plot(
        epochsRange,
        history["trainLoss"],
        label="Training Loss",
        linewidth=2,
    )

    plt.plot(
        epochsRange,
        history["valLoss"],
        label="Validation Loss",
        linewidth=2,
    )

    plt.title(
        "SmartTwin LSTM - Training vs Validation"
    )

    plt.xlabel(
        "Epoch"
    )

    plt.ylabel(
        "MSE Loss"
    )

    plt.legend()

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.tight_layout()

    plt.savefig(
        plotLossFile,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    print(
        "Loss plot saved:",
        plotLossFile
    )


# ============================================================
# PLOT TEST PREDICTIONS
# ============================================================

def plotTestPredictions(
    actualValues,
    predictedValues,
):

    plt.figure(
        figsize=(14, 7)
    )

    maxSamples = min(
        30,
        len(actualValues)
    )

    # South volume sebagai contoh visual.
    # Ini bukan berarti model hanya memprediksi south.

    southVolumeIndex = (
        APPROACHES.index("south")
        * len(CSV_FEATURES)
    )

    actual = (
        actualValues[
            :maxSamples,
            0,
            southVolumeIndex,
        ]
    )

    predicted = (
        predictedValues[
            :maxSamples,
            0,
            southVolumeIndex,
        ]
    )

    plt.plot(
        range(maxSamples),
        actual,
        label="Actual South Volume",
        linewidth=2,
    )

    plt.plot(
        range(maxSamples),
        predicted,
        label="Predicted South Volume",
        linewidth=2,
    )

    plt.title(
        "SmartTwin LSTM - South Approach Volume"
    )

    plt.xlabel(
        "Test Sample"
    )

    plt.ylabel(
        "Vehicle Count"
    )

    plt.legend()

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.tight_layout()

    plt.savefig(
        plotPredictionFile,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    print(
        "Prediction plot saved:",
        plotPredictionFile
    )


# ============================================================
# EXPORT ONNX
# ============================================================

def exportOnnx(
    model,
    device,
    inputSize,
):

    print()
    print(
        "=" * 70
    )
    print(
        "[11] EXPORTING ONNX"
    )
    print(
        "=" * 70
    )

    model.eval()

    dummyInput = torch.zeros(
        (
            1,
            LOOKBACK,
            inputSize,
        ),
        dtype=torch.float32,
        device=device,
    )

    try:

        torch.onnx.export(

            model,

            dummyInput,

            onnxModelFile,

            export_params=True,

            opset_version=17,

            do_constant_folding=True,

            input_names=[
                "input"
            ],

            output_names=[
                "prediction"
            ],

            dynamic_axes={

                "input": {
                    0: "batch"
                },

                "prediction": {
                    0: "batch"
                },
            },

            dynamo=False,
        )

    except Exception as error:

        print(
            "ONNX export gagal:"
        )

        print(
            error
        )

        raise RuntimeError(
            "Training selesai tetapi "
            "ONNX export gagal."
        ) from error

    if not onnxModelFile.exists():

        raise RuntimeError(
            "File ONNX tidak dibuat."
        )

    fileSize = (
        onnxModelFile
        .stat()
        .st_size
    )

    if fileSize <= 0:

        raise RuntimeError(
            "File ONNX kosong."
        )

    print(
        "ONNX saved:",
        onnxModelFile
    )

    print(
        "ONNX size:",
        f"{fileSize / 1024:.2f} KB"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    setSeed()

    device = getDevice()

    print()
    print(
        "=" * 70
    )
    print(
        "SMARTTWIN - MULTI-APPROACH TRAFFIC LSTM TRAINING"
    )
    print(
        "=" * 70
    )

    # ========================================================
    # MODEL CONTRACT
    # ========================================================

    inputSize = (
        len(APPROACHES)
        * len(CSV_FEATURES)
    )

    outputSize = inputSize

    print()
    print(
        "MODEL CONTRACT"
    )

    print(
        "Approaches:",
        APPROACHES
    )

    print(
        "Features:",
        CSV_FEATURES
    )

    print(
        "Input:",
        f"{LOOKBACK} timestep × "
        f"{inputSize} features"
    )

    print(
        "History:",
        f"{LOOKBACK * INTERVAL_SECONDS}s"
    )

    print(
        "Output:",
        f"{HORIZON} timestep × "
        f"{outputSize} features"
    )

    print(
        "Forecast:",
        f"{HORIZON * INTERVAL_SECONDS}s"
    )

    print()
    print(
        "Per timestep:"
    )

    for approach in APPROACHES:

        print(
            f"  {approach:<6} → "
            f"{len(CSV_FEATURES)} features"
        )

    print()
    print(
        "TOTAL INPUT FEATURES:",
        inputSize
    )

    # ========================================================
    # LOAD
    # ========================================================

    rawDataFrame = loadData()

    # ========================================================
    # BUILD TIME SERIES
    # ========================================================

    (
        timeSeriesData,
        featureNames,
    ) = buildApproachTimeSeries(
        rawDataFrame
    )

    # ========================================================
    # CHECK DATA
    # ========================================================

    minimumRequired = (
        LOOKBACK
        + HORIZON
        + 20
    )

    if len(
        timeSeriesData
    ) < minimumRequired:

        raise ValueError(

            "Data terlalu sedikit "
            "untuk training multi-approach.\n\n"

            f"Timestep lengkap: "
            f"{len(timeSeriesData)}\n"

            f"Minimal: "
            f"{minimumRequired}\n\n"

            "Butuh lebih banyak data "
            "4 approach dengan interval "
            "5 detik."
        )

    # ========================================================
    # CHRONOLOGICAL SPLIT
    # ========================================================

    print()
    print(
        "=" * 70
    )
    print(
        "[3] CHRONOLOGICAL SPLIT"
    )
    print(
        "=" * 70
    )

    totalRows = len(
        timeSeriesData
    )

    trainEnd = int(
        totalRows
        * TRAIN_RATIO
    )

    valEnd = int(
        totalRows
        * (
            TRAIN_RATIO
            + VAL_RATIO
        )
    )

    trainDataFrame = (
        timeSeriesData
        .iloc[:trainEnd]
        .copy()
    )

    valDataFrame = (
        timeSeriesData
        .iloc[
            trainEnd:valEnd
        ]
        .copy()
    )

    testDataFrame = (
        timeSeriesData
        .iloc[valEnd:]
        .copy()
    )

    print(
        "Train:",
        len(trainDataFrame)
    )

    print(
        "Validation:",
        len(valDataFrame)
    )

    print(
        "Test:",
        len(testDataFrame)
    )

    # ========================================================
    # SCALER
    # ========================================================

    print()
    print(
        "=" * 70
    )
    print(
        "[4] FITTING SCALER"
    )
    print(
        "=" * 70
    )

    scaler = MinMaxScaler()

    scaler.fit(
        trainDataFrame[
            featureNames
        ]
    )

    trainValues = scaler.transform(
        trainDataFrame[
            featureNames
        ]
    )

    valValues = scaler.transform(
        valDataFrame[
            featureNames
        ]
    )

    testValues = scaler.transform(
        testDataFrame[
            featureNames
        ]
    )

    # ========================================================
    # SEQUENCES
    # ========================================================

    print()
    print(
        "=" * 70
    )
    print(
        "[5] CREATING SEQUENCES"
    )
    print(
        "=" * 70
    )

    (
        xTrain,
        yTrain,
    ) = createSequences(
        trainValues,
        LOOKBACK,
        HORIZON,
    )

    (
        xVal,
        yVal,
    ) = createSequences(
        valValues,
        LOOKBACK,
        HORIZON,
    )

    (
        xTest,
        yTest,
    ) = createSequences(
        testValues,
        LOOKBACK,
        HORIZON,
    )

    print(
        "xTrain:",
        xTrain.shape
    )

    print(
        "yTrain:",
        yTrain.shape
    )

    print(
        "xVal:",
        xVal.shape
    )

    print(
        "yVal:",
        yVal.shape
    )

    print(
        "xTest:",
        xTest.shape
    )

    print(
        "yTest:",
        yTest.shape
    )

    if len(xTrain) == 0:

        raise ValueError(
            "Training sequence kosong."
        )

    if len(xVal) == 0:

        raise ValueError(
            "Validation sequence kosong."
        )

    if len(xTest) == 0:

        raise ValueError(
            "Test sequence kosong."
        )

    # ========================================================
    # DATASET
    # ========================================================

    trainDataset = TrafficDataset(
        xTrain,
        yTrain,
    )

    valDataset = TrafficDataset(
        xVal,
        yVal,
    )

    testDataset = TrafficDataset(
        xTest,
        yTest,
    )

    trainLoader = DataLoader(
        trainDataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    valLoader = DataLoader(
        valDataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    testLoader = DataLoader(
        testDataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    # ========================================================
    # MODEL
    # ========================================================

    model = TrafficLSTM(

        inputSize=inputSize,

        hiddenSize=HIDDEN_SIZE,

        numLayers=NUM_LAYERS,

        horizon=HORIZON,

        outputSize=outputSize,

        dropout=DROPOUT,
    )

    model = model.to(
        device
    )

    print()
    print(
        "=" * 70
    )
    print(
        "[6] MODEL"
    )
    print(
        "=" * 70
    )

    print(
        model
    )

    # ========================================================
    # OPTIMIZER
    # ========================================================

    criterion = nn.MSELoss()

    optimizer = Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )

    # ========================================================
    # TRAINING
    # ========================================================

    print()
    print(
        "=" * 70
    )
    print(
        "[7] TRAINING"
    )
    print(
        "=" * 70
    )

    bestValLoss = float(
        "inf"
    )

    patienceCounter = 0

    history = {

        "trainLoss": [],

        "valLoss": [],
    }

    for epoch in range(
        1,
        EPOCHS + 1,
    ):

        # ----------------------------------------------------
        # TRAIN
        # ----------------------------------------------------

        model.train()

        trainLosses = []

        for (
            inputBatch,
            targetBatch,
        ) in trainLoader:

            inputBatch = (
                inputBatch.to(
                    device
                )
            )

            targetBatch = (
                targetBatch.to(
                    device
                )
            )

            optimizer.zero_grad()

            prediction = model(
                inputBatch
            )

            loss = criterion(
                prediction,
                targetBatch,
            )

            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=GRADIENT_CLIP,
            )

            optimizer.step()

            trainLosses.append(
                loss.item()
            )

        trainLoss = float(
            np.mean(
                trainLosses
            )
        )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        model.eval()

        valLosses = []

        with torch.no_grad():

            for (
                inputBatch,
                targetBatch,
            ) in valLoader:

                inputBatch = (
                    inputBatch.to(
                        device
                    )
                )

                targetBatch = (
                    targetBatch.to(
                        device
                    )
                )

                prediction = model(
                    inputBatch
                )

                loss = criterion(
                    prediction,
                    targetBatch,
                )

                valLosses.append(
                    loss.item()
                )

        valLoss = float(
            np.mean(
                valLosses
            )
        )

        history[
            "trainLoss"
        ].append(
            trainLoss
        )

        history[
            "valLoss"
        ].append(
            valLoss
        )

        print(
            f"Epoch {epoch:03d}/{EPOCHS} | "
            f"Train={trainLoss:.6f} | "
            f"Val={valLoss:.6f}"
        )

        # ----------------------------------------------------
        # BEST MODEL
        # ----------------------------------------------------

        if valLoss < bestValLoss:

            bestValLoss = valLoss

            patienceCounter = 0

            torch.save(
                {

                    "modelStateDict":
                        model.state_dict(),

                    "inputSize":
                        inputSize,

                    "hiddenSize":
                        HIDDEN_SIZE,

                    "numLayers":
                        NUM_LAYERS,

                    "horizon":
                        HORIZON,

                    "outputSize":
                        outputSize,

                    "dropout":
                        DROPOUT,

                    "featureNames":
                        featureNames,

                    "approaches":
                        APPROACHES,

                    "csvFeatureNames":
                        CSV_FEATURES,

                    "lookback":
                        LOOKBACK,

                    "intervalSeconds":
                        INTERVAL_SECONDS,

                    "horizonSeconds":
                        HORIZON
                        * INTERVAL_SECONDS,
                },
                modelFile,
            )

        else:

            patienceCounter += 1

        if (
            patienceCounter
            >= PATIENCE
        ):

            print()
            print(
                "Early stopping."
            )

            break

    # ========================================================
    # SAVE HISTORY
    # ========================================================

    with open(
        historyFile,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            history,
            file,
            indent=4,
        )

    plotTrainingValidationLoss(
        history
    )

    # ========================================================
    # LOAD BEST MODEL
    # ========================================================

    checkpoint = torch.load(
        modelFile,
        map_location=device,
    )

    model.load_state_dict(
        checkpoint[
            "modelStateDict"
        ]
    )

    model.eval()

    # ========================================================
    # TEST
    # ========================================================

    predictions = []

    actuals = []

    with torch.no_grad():

        for (
            inputBatch,
            targetBatch,
        ) in testLoader:

            inputBatch = (
                inputBatch.to(
                    device
                )
            )

            prediction = model(
                inputBatch
            )

            predictions.append(
                prediction
                .cpu()
                .numpy()
            )

            actuals.append(
                targetBatch
                .numpy()
            )

    predictions = np.concatenate(
        predictions,
        axis=0,
    )

    actuals = np.concatenate(
        actuals,
        axis=0,
    )

    # ========================================================
    # INVERSE SCALE
    # ========================================================

    predictionsFlat = (
        predictions
        .reshape(
            -1,
            inputSize,
        )
    )

    actualsFlat = (
        actuals
        .reshape(
            -1,
            inputSize,
        )
    )

    predictionsOriginal = (
        scaler.inverse_transform(
            predictionsFlat
        )
    )

    actualsOriginal = (
        scaler.inverse_transform(
            actualsFlat
        )
    )

    predictionsOriginal = (
        predictionsOriginal
        .reshape(
            predictions.shape
        )
    )

    actualsOriginal = (
        actualsOriginal
        .reshape(
            actuals.shape
        )
    )

    # ========================================================
    # VEHICLES CANNOT BE NEGATIVE
    # ========================================================

    predictionsOriginal = np.maximum(
        predictionsOriginal,
        0.0,
    )

    # ========================================================
    # METRICS GLOBAL
    # ========================================================

    globalActual = (
        actualsOriginal
        .reshape(
            -1,
            inputSize,
        )
    )

    globalPredicted = (
        predictionsOriginal
        .reshape(
            -1,
            inputSize,
        )
    )

    mae = mean_absolute_error(
        globalActual,
        globalPredicted,
    )

    mse = mean_squared_error(
        globalActual,
        globalPredicted,
    )

    rmse = np.sqrt(
        mse
    )

    print()
    print(
        "=" * 70
    )
    print(
        "[8] GLOBAL TEST METRICS"
    )
    print(
        "=" * 70
    )

    print(
        "MAE :",
        f"{mae:.4f}"
    )

    print(
        "MSE :",
        f"{mse:.4f}"
    )

    print(
        "RMSE:",
        f"{rmse:.4f}"
    )

    # ========================================================
    # APPROACH METRICS
    # ========================================================

    approachMetrics = {}

    featureMetrics = {}

    for approachIndex, approach in enumerate(
        APPROACHES
    ):

        startIndex = (
            approachIndex
            * len(CSV_FEATURES)
        )

        endIndex = (
            startIndex
            + len(CSV_FEATURES)
        )

        approachActual = (
            actualsOriginal[
                :,
                :,
                startIndex:endIndex,
            ]
            .reshape(
                -1,
                len(CSV_FEATURES),
            )
        )

        approachPredicted = (
            predictionsOriginal[
                :,
                :,
                startIndex:endIndex,
            ]
            .reshape(
                -1,
                len(CSV_FEATURES),
            )
        )

        approachMae = mean_absolute_error(
            approachActual,
            approachPredicted,
        )

        approachMse = mean_squared_error(
            approachActual,
            approachPredicted,
        )

        approachRmse = np.sqrt(
            approachMse
        )

        volumeActual = (
            approachActual[
                :,
                0
            ]
        )

        volumePredicted = (
            approachPredicted[
                :,
                0
            ]
        )

        volumeMae = mean_absolute_error(
            volumeActual,
            volumePredicted,
        )

        volumeRmse = np.sqrt(
            mean_squared_error(
                volumeActual,
                volumePredicted,
            )
        )

        approachMetrics[
            approach
        ] = {

            "mae":
                float(
                    approachMae
                ),

            "rmse":
                float(
                    approachRmse
                ),

            "volumeMae":
                float(
                    volumeMae
                ),

            "volumeRmse":
                float(
                    volumeRmse
                ),
        }

        featureMetrics[
            approach
        ] = {}

        for featureIndex, featureName in enumerate(
            CSV_FEATURES
        ):

            actualFeature = (
                approachActual[
                    :,
                    featureIndex
                ]
            )

            predictedFeature = (
                approachPredicted[
                    :,
                    featureIndex
                ]
            )

            featureMae = mean_absolute_error(
                actualFeature,
                predictedFeature,
            )

            featureRmse = np.sqrt(
                mean_squared_error(
                    actualFeature,
                    predictedFeature,
                )
            )

            featureMetrics[
                approach
            ][
                featureName
            ] = {

                "mae":
                    float(
                        featureMae
                    ),

                "rmse":
                    float(
                        featureRmse
                    ),
            }

    print()
    print(
        "=" * 70
    )
    print(
        "[9] APPROACH METRICS"
    )
    print(
        "=" * 70
    )

    for approach in APPROACHES:

        metrics = (
            approachMetrics[
                approach
            ]
        )

        print(
            f"{approach.upper():<8} "
            f"MAE={metrics['mae']:.4f} "
            f"RMSE={metrics['rmse']:.4f} "
            f"Volume MAE={metrics['volumeMae']:.4f}"
        )

    # ========================================================
    # TEST TIMESTAMPS
    # ========================================================

    testTimestamps = (
        testDataFrame[
            "timestamp"
        ]
        .iloc[
            LOOKBACK:
            LOOKBACK
            + len(
                actualsOriginal
            )
        ]
        .reset_index(
            drop=True
        )
    )

    # ========================================================
    # SAVE PREDICTIONS
    # ========================================================

    savePredictions(

        testTimestamps,

        actualsOriginal,

        predictionsOriginal,

        featureNames,
    )

    # ========================================================
    # PLOT
    # ========================================================

    plotTestPredictions(
        actualsOriginal,
        predictionsOriginal,
    )

    # ========================================================
    # SAVE SCALER
    # ========================================================

    saveScaler(
        scaler,
        featureNames,
    )

    # ========================================================
    # METADATA
    # ========================================================

    metadata = {

        "modelName":
            "SmartTwin Multi-Approach Traffic LSTM",

        "framework":
            "PyTorch",

        "exportFormat":
            "ONNX",

        "modelVersion":
            "2.0",

        "approaches":
            APPROACHES,

        "csvFeatureNames":
            CSV_FEATURES,

        "contractFeatureMapping":
            CONTRACT_FEATURE_MAPPING,

        "inputSize":
            inputSize,

        "inputShape": [
            LOOKBACK,
            inputSize,
        ],

        "outputShape": [
            HORIZON,
            inputSize,
        ],

        "lookback":
            LOOKBACK,

        "lookbackSeconds":
            LOOKBACK
            * INTERVAL_SECONDS,

        "horizon":
            HORIZON,

        "horizonSeconds":
            HORIZON
            * INTERVAL_SECONDS,

        "intervalSeconds":
            INTERVAL_SECONDS,

        "hiddenSize":
            HIDDEN_SIZE,

        "numLayers":
            NUM_LAYERS,

        "dropout":
            DROPOUT,

        "bestValLoss":
            float(
                bestValLoss
            ),

        "testMae":
            float(
                mae
            ),

        "testMse":
            float(
                mse
            ),

        "testRmse":
            float(
                rmse
            ),

        "approachMetrics":
            approachMetrics,

        "featureMetrics":
            featureMetrics,

        "congestionMethod":
            "derived_from_predicted_volume",

        "congestionFormula":
            "predicted_volume / approach_capacity",

        "congestionLevels": {

            "lancar":
                "0.00-0.29",

            "ramai":
                "0.30-0.59",

            "padat":
                "0.60-0.79",

            "macet":
                "0.80-1.00",
        },

        "approachCapacity":
            APPROACH_CAPACITY,

        "numRawRows":
            int(
                len(
                    rawDataFrame
                )
            ),

        "numCompleteTimesteps":
            int(
                len(
                    timeSeriesData
                )
            ),

        "numTrainSequences":
            int(
                len(
                    xTrain
                )
            ),

        "numValidationSequences":
            int(
                len(
                    xVal
                )
            ),

        "numTestSequences":
            int(
                len(
                    xTest
                )
            ),
    }

    with open(
        metadataFile,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4,
        )

    print()
    print(
        "Metadata saved:",
        metadataFile
    )

    # ========================================================
    # EXPORT ONNX
    # ========================================================

    exportOnnx(
        model,
        device,
        inputSize,
    )

    # ========================================================
    # FINAL
    # ========================================================

    print()
    print(
        "=" * 70
    )
    print(
        "TRAINING SELESAI"
    )
    print(
        "=" * 70
    )

    print()
    print(
        "MODEL:"
    )

    print(
        modelFile
    )

    print()
    print(
        "ONNX:"
    )

    print(
        onnxModelFile
    )

    print()
    print(
        "SCALER:"
    )

    print(
        scalerFile
    )

    print()
    print(
        "METADATA:"
    )

    print(
        metadataFile
    )

    print()
    print(
        "PREDICTIONS:"
    )

    print(
        predictionsFile
    )

    print()
    print(
        "TRAINING HISTORY:"
    )

    print(
        historyFile
    )

    print()
    print(
        "PLOTS:"
    )

    print(
        plotDir
    )

    print()
    print(
        "=" * 70
    )

    print(
        "SMARTTWIN FORECASTING READY"
    )

    print(
        "=" * 70
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
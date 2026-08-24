from __future__ import annotations

import json
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset


# ============================================================
# PATH
# ============================================================
#
# smarttwin/
#
# ├── forecasting/
# │   ├── data/
# │   │   └── percobaan_logic_simpang.csv
# │   │
# │   ├── scripts/
# │   │   └── yolo/
# │   │       └── train.py
# │   │
# │   └── outputs/
# │       └── yolo/
# │
# └── backend/
#     └── app/
#

baseDir = Path(__file__).resolve().parents[2]

dataDir = baseDir / "data"
outputDir = baseDir / "outputs" / "yolo"
plotDir = outputDir / "plots"

dataFile = dataDir / "percobaan_logic_simpang.csv"

modelFile = outputDir / "traffic_lstm.pt"
onnxModelFile = outputDir / "traffic_lstm.onnx"
scalerFile = outputDir / "scaler.json"
metadataFile = outputDir / "metadata.json"
historyFile = outputDir / "training_history.json"
predictionsFile = outputDir / "predictions.csv"

outputDir.mkdir(parents=True, exist_ok=True)
plotDir.mkdir(parents=True, exist_ok=True)


# ============================================================
# CONFIGURATION
# ============================================================

randomSeed = 42

# Data CSV berasal dari YOLO dengan interval target 5 detik.
intervalSeconds = 5

# 12 timestep x 5 detik = 60 detik history
lookback = 12

# 3 timestep x 5 detik = 15 detik forecast
horizon = 3

trainRatio = 0.70
valRatio = 0.15
testRatio = 0.15

batchSize = 32
epochs = 100
learningRate = 0.001
patience = 15

hiddenSize = 64
numLayers = 2
dropout = 0.2


# ============================================================
# CSV FEATURES
# ============================================================
#
# Nama di bawah adalah NAMA ASLI KOLOM CSV.
#
# Jangan mengubah nama ini kalau kolom CSV memang seperti ini.
#

csvFeatureColumns = [
    "total_di_zona",
    "motor_di_zona",
    "mobil_di_zona",
    "truk_di_zona",
    "bus_di_zona",
]


# ============================================================
# DATA CONTRACT MAPPING
# ============================================================

contractFeatureMapping = {
    "total_di_zona": "volume",
    "motor_di_zona": "motorcycleCount",
    "mobil_di_zona": "carCount",
    "truk_di_zona": "truckCount",
    "bus_di_zona": "busCount",
}


# ============================================================
# RANDOM SEED
# ============================================================

def setSeed(seed: int = randomSeed) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# DEVICE
# ============================================================

def getDevice():
    if torch.cuda.is_available():
        device = torch.device("cuda")

        print(
            "CUDA tersedia:",
            torch.cuda.get_device_name(0),
        )

        return device

    print("CUDA tidak tersedia. Menggunakan CPU.")

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
        return len(self.inputData)

    def __getitem__(self, index):
        return (
            self.inputData[index],
            self.targetData[index],
        )


# ============================================================
# LSTM MODEL
# ============================================================

class TrafficLSTM(nn.Module):

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

        self.fc = nn.Linear(
            hiddenSize,
            horizon * outputSize,
        )

    def forward(self, inputData):

        # Input:
        #
        # [batch, 12, 5]
        #
        # 12 = lookback
        # 5  = features

        output, _ = self.lstm(inputData)

        lastOutput = output[:, -1, :]

        prediction = self.fc(lastOutput)

        # Output:
        #
        # [batch, 3, 5]

        prediction = prediction.view(
            -1,
            self.horizon,
            self.outputSize,
        )

        return prediction


# ============================================================
# LOAD DATA
# ============================================================

def loadData():

    print("\n[1] Loading dataset...")

    if not dataFile.exists():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n{dataFile}"
        )

    dataFrame = pd.read_csv(dataFile)

    requiredColumns = [
        "timestamp",
        "kamera",
        "lengan",
        *csvFeatureColumns,
    ]

    missingColumns = [
        column
        for column in requiredColumns
        if column not in dataFrame.columns
    ]

    if missingColumns:
        raise ValueError(
            "Kolom berikut tidak ditemukan:\n"
            + "\n".join(
                f"- {column}"
                for column in missingColumns
            )
        )

    dataFrame["timestamp"] = pd.to_datetime(
        dataFrame["timestamp"],
        errors="coerce",
    )

    dataFrame = dataFrame.dropna(
        subset=["timestamp"]
    )

    for column in csvFeatureColumns:

        dataFrame[column] = pd.to_numeric(
            dataFrame[column],
            errors="coerce",
        )

    dataFrame[csvFeatureColumns] = (
        dataFrame[csvFeatureColumns]
        .fillna(0)
    )

    dataFrame = (
        dataFrame
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    print(
        "Raw rows:",
        len(dataFrame),
    )

    print(
        "Time:",
        dataFrame["timestamp"].min(),
        "->",
        dataFrame["timestamp"].max(),
    )

    return dataFrame


# ============================================================
# PREPARE TIME SERIES
# ============================================================

def prepareTimeSeries(
    dataFrame: pd.DataFrame,
):

    print("\n[2] Preparing time series...")

    print(
        "Menggabungkan seluruh kamera/lengan "
        "pada timestamp yang sama."
    )

    timeSeriesData = (
        dataFrame
        .groupby("timestamp")[csvFeatureColumns]
        .sum()
        .reset_index()
    )

    timeSeriesData = (
        timeSeriesData
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    print(
        "\nJumlah timestep:",
        len(timeSeriesData),
    )

    print(
        "\nContoh hasil agregasi:"
    )

    print(
        timeSeriesData
        .head(10)
        .to_string(index=False)
    )

    intervals = (
        timeSeriesData["timestamp"]
        .diff()
        .dt.total_seconds()
        .dropna()
    )

    if len(intervals) > 0:

        print(
            "\nInterval median:",
            intervals.median(),
            "detik",
        )

        print(
            "Interval minimum:",
            intervals.min(),
            "detik",
        )

        print(
            "Interval maksimum:",
            intervals.max(),
            "detik",
        )

    return timeSeriesData


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

    totalLength = len(values)

    maxStart = (
        totalLength
        - lookbackValue
        - horizonValue
        + 1
    )

    for start in range(maxStart):

        end = start + lookbackValue

        targetEnd = (
            end
            + horizonValue
        )

        inputSequences.append(
            values[start:end]
        )

        targetSequences.append(
            values[end:targetEnd]
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
) -> None:

    scalerData = {
        "featureNames": csvFeatureColumns,

        "min": scaler.min_.tolist(),

        "scale": scaler.scale_.tolist(),

        "dataMin": scaler.data_min_.tolist(),

        "dataMax": scaler.data_max_.tolist(),

        "dataRange": scaler.data_range_.tolist(),
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
        scalerFile,
    )


# ============================================================
# EXPORT ONNX
# ============================================================

def exportOnnx(
    model,
    device,
):

    print("\n[12] Exporting ONNX model...")

    model.eval()

    dummyInput = torch.zeros(
        (
            1,
            lookback,
            len(csvFeatureColumns),
        ),
        dtype=torch.float32,
        device=device,
    )

    try:

        # ====================================================
        # IMPORTANT
        # ====================================================
        #
        # PyTorch versi baru dapat menggunakan ONNX exporter
        # berbasis dynamo secara default.
        #
        # Exporter tersebut membutuhkan package onnxscript.
        #
        # Kita TIDAK menggunakan TensorFlow.
        #
        # Dengan dynamo=False kita menggunakan legacy exporter
        # PyTorch sehingga onnxscript tidak diperlukan.
        #
        # ====================================================

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
                    0: "batch",
                },

                "prediction": {
                    0: "batch",
                },
            },

            dynamo=False,
        )

        print(
            "ONNX model saved:",
            onnxModelFile,
        )

    except Exception as error:

        print(
            "\nERROR saat export ONNX:"
        )

        print(error)

        raise RuntimeError(
            "Export ONNX gagal. "
            "Training dan evaluasi model sudah selesai, "
            "tetapi file ONNX belum berhasil dibuat."
        ) from error

    # ========================================================
    # VERIFY FILE
    # ========================================================

    if not onnxModelFile.exists():

        raise RuntimeError(
            "Exporter tidak menghasilkan file ONNX."
        )

    fileSize = onnxModelFile.stat().st_size

    print(
        "ONNX file size:",
        f"{fileSize / 1024:.2f} KB",
    )

    if fileSize <= 0:

        raise RuntimeError(
            "File ONNX kosong."
        )

    print(
        "ONNX export berhasil."
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
        "SmartTwin LSTM Training vs Validation Loss"
    )

    plt.xlabel("Epoch")

    plt.ylabel("MSE Loss")

    plt.legend()

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.tight_layout()

    outputFile = (
        plotDir
        / "training_validation_loss.png"
    )

    plt.savefig(
        outputFile,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    print(
        "Training plot saved:",
        outputFile,
    )


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def savePredictions(
    timestamps,
    actualValues,
    predictedValues,
):

    rows = []

    for index in range(
        len(timestamps)
    ):

        row = {
            "timestamp": timestamps[index],
        }

        for featureIndex, featureName in enumerate(
            csvFeatureColumns
        ):

            row[
                f"actual_{featureName}"
            ] = float(
                actualValues[
                    index,
                    0,
                    featureIndex,
                ]
            )

            row[
                f"predicted_{featureName}"
            ] = float(
                predictedValues[
                    index,
                    0,
                    featureIndex,
                ]
            )

        rows.append(row)

    predictionsDataFrame = pd.DataFrame(
        rows
    )

    predictionsDataFrame.to_csv(
        predictionsFile,
        index=False,
    )

    print(
        "Predictions saved:",
        predictionsFile,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # SETUP
    # ========================================================

    setSeed()

    device = getDevice()

    print(
        "\n"
        + "=" * 70
    )

    print(
        "SMARTTWIN - TRAFFIC LSTM TRAINING"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # MODEL CONTRACT
    # ========================================================

    print(
        "\nMODEL CONTRACT"
    )

    print(
        "CSV Features:",
        csvFeatureColumns,
    )

    print(
        "Input:",
        f"{lookback} timestep × "
        f"{len(csvFeatureColumns)} features",
    )

    print(
        "History:",
        f"{lookback * intervalSeconds} seconds",
    )

    print(
        "Output:",
        f"{horizon} timestep × "
        f"{len(csvFeatureColumns)} features",
    )

    print(
        "Forecast:",
        f"{horizon * intervalSeconds} seconds",
    )

    print(
        "\nCSV → Data Contract mapping:"
    )

    for (
        csvName,
        contractName,
    ) in contractFeatureMapping.items():

        print(
            f"  {csvName} → {contractName}"
        )

    # ========================================================
    # LOAD
    # ========================================================

    rawDataFrame = loadData()

    # ========================================================
    # AGGREGATE
    # ========================================================

    timeSeriesData = prepareTimeSeries(
        rawDataFrame
    )

    # ========================================================
    # CHECK DATA
    # ========================================================

    minimumRequired = (
        lookback
        + horizon
        + 10
    )

    if len(timeSeriesData) < minimumRequired:

        raise ValueError(
            f"Data terlalu sedikit.\n"
            f"Jumlah timestep: "
            f"{len(timeSeriesData)}\n"
            f"Minimal: {minimumRequired}"
        )

    # ========================================================
    # CHRONOLOGICAL SPLIT
    # ========================================================

    print(
        "\n[3] Chronological split..."
    )

    totalRows = len(
        timeSeriesData
    )

    trainEnd = int(
        totalRows
        * trainRatio
    )

    valEnd = int(
        totalRows
        * (
            trainRatio
            + valRatio
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

    print(
        "\n[4] Fitting scaler..."
    )

    scaler = MinMaxScaler()

    scaler.fit(
        trainDataFrame[
            csvFeatureColumns
        ]
    )

    trainValues = scaler.transform(
        trainDataFrame[
            csvFeatureColumns
        ]
    )

    valValues = scaler.transform(
        valDataFrame[
            csvFeatureColumns
        ]
    )

    testValues = scaler.transform(
        testDataFrame[
            csvFeatureColumns
        ]
    )

    # ========================================================
    # CREATE SEQUENCES
    # ========================================================

    print(
        "\n[5] Creating sequences..."
    )

    xTrain, yTrain = createSequences(
        trainValues,
        lookback,
        horizon,
    )

    xVal, yVal = createSequences(
        valValues,
        lookback,
        horizon,
    )

    xTest, yTest = createSequences(
        testValues,
        lookback,
        horizon,
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
        batch_size=batchSize,
        shuffle=True,
    )

    valLoader = DataLoader(
        valDataset,
        batch_size=batchSize,
        shuffle=False,
    )

    testLoader = DataLoader(
        testDataset,
        batch_size=batchSize,
        shuffle=False,
    )

    # ========================================================
    # MODEL
    # ========================================================

    inputSize = len(
        csvFeatureColumns
    )

    model = TrafficLSTM(
        inputSize=inputSize,
        hiddenSize=hiddenSize,
        numLayers=numLayers,
        horizon=horizon,
        outputSize=inputSize,
        dropout=dropout,
    )

    model = model.to(device)

    print(
        "\n[6] Model:"
    )

    print(model)

    # ========================================================
    # OPTIMIZER
    # ========================================================

    criterion = nn.MSELoss()

    optimizer = Adam(
        model.parameters(),
        lr=learningRate,
    )

    # ========================================================
    # TRAINING
    # ========================================================

    print(
        "\n[7] Training..."
    )

    bestValLoss = float("inf")

    patienceCounter = 0

    history = {
        "trainLoss": [],
        "valLoss": [],
    }

    for epoch in range(
        1,
        epochs + 1,
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

            inputBatch = inputBatch.to(
                device
            )

            targetBatch = targetBatch.to(
                device
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
                max_norm=1.0,
            )

            optimizer.step()

            trainLosses.append(
                loss.item()
            )

        trainLoss = float(
            np.mean(trainLosses)
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

                inputBatch = inputBatch.to(
                    device
                )

                targetBatch = targetBatch.to(
                    device
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
            np.mean(valLosses)
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
            f"Epoch {epoch:03d}/{epochs} | "
            f"Train Loss: {trainLoss:.6f} | "
            f"Val Loss: {valLoss:.6f}"
        )

        # ----------------------------------------------------
        # SAVE BEST MODEL
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
                        hiddenSize,

                    "numLayers":
                        numLayers,

                    "horizon":
                        horizon,

                    "outputSize":
                        inputSize,

                    "dropout":
                        dropout,

                    "featureNames":
                        csvFeatureColumns,

                    "lookback":
                        lookback,

                    "intervalSeconds":
                        intervalSeconds,
                },
                modelFile,
            )

        else:

            patienceCounter += 1

        if patienceCounter >= patience:

            print(
                "\nEarly stopping."
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

            inputBatch = inputBatch.to(
                device
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
                targetBatch.numpy()
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
    # INVERSE TRANSFORM
    # ========================================================

    predictionsFlat = predictions.reshape(
        -1,
        inputSize,
    )

    actualsFlat = actuals.reshape(
        -1,
        inputSize,
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
        predictionsOriginal.reshape(
            predictions.shape
        )
    )

    actualsOriginal = (
        actualsOriginal.reshape(
            actuals.shape
        )
    )

    # ========================================================
    # VEHICLE COUNT TIDAK BOLEH NEGATIF
    # ========================================================

    predictionsOriginal = np.maximum(
        predictionsOriginal,
        0,
    )

    # ========================================================
    # METRICS
    # ========================================================

    mae = mean_absolute_error(
        actualsOriginal.reshape(
            -1,
            inputSize,
        ),
        predictionsOriginal.reshape(
            -1,
            inputSize,
        ),
    )

    mse = mean_squared_error(
        actualsOriginal.reshape(
            -1,
            inputSize,
        ),
        predictionsOriginal.reshape(
            -1,
            inputSize,
        ),
    )

    rmse = np.sqrt(mse)

    print(
        "\nTest MAE:",
        f"{mae:.4f}",
    )

    print(
        "Test MSE:",
        f"{mse:.4f}",
    )

    print(
        "Test RMSE:",
        f"{rmse:.4f}",
    )

    # ========================================================
    # FEATURE METRICS
    # ========================================================

    featureMetrics = {}

    for (
        featureIndex,
        featureName,
    ) in enumerate(
        csvFeatureColumns
    ):

        featureActual = (
            actualsOriginal[
                :,
                :,
                featureIndex,
            ]
            .reshape(-1)
        )

        featurePredicted = (
            predictionsOriginal[
                :,
                :,
                featureIndex,
            ]
            .reshape(-1)
        )

        featureMae = mean_absolute_error(
            featureActual,
            featurePredicted,
        )

        featureRmse = np.sqrt(
            mean_squared_error(
                featureActual,
                featurePredicted,
            )
        )

        featureMetrics[
            featureName
        ] = {
            "mae": float(
                featureMae
            ),

            "rmse": float(
                featureRmse
            ),
        }

    # ========================================================
    # TEST TIMESTAMPS
    # ========================================================

    testTimestamps = (
        testDataFrame[
            "timestamp"
        ]
        .iloc[
            lookback:
            lookback
            + len(actualsOriginal)
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
    )

    # ========================================================
    # SAVE SCALER
    # ========================================================

    saveScaler(
        scaler
    )

    # ========================================================
    # METADATA
    # ========================================================

    metadata = {

        "modelName":
            "SmartTwin Traffic LSTM",

        "framework":
            "PyTorch",

        "exportFormat":
            "ONNX",

        "csvFeatureNames":
            csvFeatureColumns,

        "contractFeatureMapping":
            contractFeatureMapping,

        "inputSize":
            inputSize,

        "lookback":
            lookback,

        "lookbackSeconds":
            lookback
            * intervalSeconds,

        "horizon":
            horizon,

        "horizonSeconds":
            horizon
            * intervalSeconds,

        "intervalSeconds":
            intervalSeconds,

        "hiddenSize":
            hiddenSize,

        "numLayers":
            numLayers,

        "dropout":
            dropout,

        "bestValLoss":
            float(bestValLoss),

        "testMae":
            float(mae),

        "testMse":
            float(mse),

        "testRmse":
            float(rmse),

        "featureMetrics":
            featureMetrics,

        "numRawRows":
            int(
                len(rawDataFrame)
            ),

        "numTimesteps":
            int(
                len(timeSeriesData)
            ),

        "numTrainSequences":
            int(
                len(xTrain)
            ),

        "numValidationSequences":
            int(
                len(xVal)
            ),

        "numTestSequences":
            int(
                len(xTest)
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

    print(
        "\nMetadata saved:",
        metadataFile,
    )

    # ========================================================
    # EXPORT ONNX
    # ========================================================

    exportOnnx(
        model,
        device,
    )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "TRAINING SELESAI"
    )

    print(
        "=" * 70
    )

    print(
        "\nModel PyTorch:"
    )

    print(
        modelFile
    )

    print(
        "\nModel ONNX:"
    )

    print(
        onnxModelFile
    )

    print(
        "\nScaler:"
    )

    print(
        scalerFile
    )

    print(
        "\nMetadata:"
    )

    print(
        metadataFile
    )

    print(
        "\nPredictions:"
    )

    print(
        predictionsFile
    )

    print(
        "\nTraining history:"
    )

    print(
        historyFile
    )

    print(
        "\nTraining plot:"
    )

    print(
        plotDir
        / "training_validation_loss.png"
    )

    print(
        "\n"
        + "=" * 70
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
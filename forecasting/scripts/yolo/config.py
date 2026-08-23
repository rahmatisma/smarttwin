from pathlib import Path


# ============================================================
# BASE DIRECTORY
# ============================================================

# config.py:
# forecasting/scripts/yolo/config.py
#
# parents[0] = yolo
# parents[1] = scripts
# parents[2] = forecasting

FORECASTING_DIR = Path(__file__).resolve().parents[2]


# ============================================================
# DATA
# ============================================================

DATA_DIR = FORECASTING_DIR / "data"

DATA_FILE = DATA_DIR / "percobaan_logic_simpang.csv"


# ============================================================
# OUTPUT
# ============================================================

OUTPUT_DIR = FORECASTING_DIR / "outputs" / "yolo"

MODEL_DIR = OUTPUT_DIR

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# OUTPUT FILES
# ============================================================

MODEL_FILE = MODEL_DIR / "traffic_lstm.pt"

SCALER_FILE = MODEL_DIR / "scaler.pkl"

METADATA_FILE = MODEL_DIR / "metadata.json"

HISTORY_FILE = MODEL_DIR / "training_history.json"


# ============================================================
# FORECASTING CONFIG
# ============================================================

LOOKBACK = 12

HORIZON = 3

TRAIN_RATIO = 0.70

VAL_RATIO = 0.15

BATCH_SIZE = 32

EPOCHS = 100

LEARNING_RATE = 0.001

PATIENCE = 15

HIDDEN_SIZE = 128

NUM_LAYERS = 2

DROPOUT = 0.2

RANDOM_SEED = 42


# ============================================================
# DEBUG
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("SMARTTWIN YOLO FORECASTING CONFIG")
    print("=" * 70)

    print("Forecasting dir:")
    print(FORECASTING_DIR)

    print()

    print("Data:")
    print(DATA_FILE)

    print()

    print("Output:")
    print(OUTPUT_DIR)

    print()

    print("Model:")
    print(MODEL_FILE)

    print("Scaler:")
    print(SCALER_FILE)

    print("Metadata:")
    print(METADATA_FILE)

    print("History:")
    print(HISTORY_FILE)

    print("=" * 70)
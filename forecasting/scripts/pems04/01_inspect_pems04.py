from pathlib import Path
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[2]

DATA_PATH = BASE_DIR / "data" / "PEMS04.npz"


def main():

    print("=" * 70)
    print("PEMS04 DATASET INSPECTION")
    print("=" * 70)

    print(f"[INFO] Dataset:")
    print(f"       {DATA_PATH}")

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n{DATA_PATH}"
        )

    data = np.load(DATA_PATH)

    print("\n[INFO] NPZ CONTENTS")
    print("-" * 70)

    print(data.files)

    for key in data.files:

        array = data[key]

        print(
            f"\n[INFO] Array: {key}"
        )

        print(
            f"       Shape : {array.shape}"
        )

        print(
            f"       Dtype : {array.dtype}"
        )

        print(
            f"       Min   : {np.nanmin(array)}"
        )

        print(
            f"       Max   : {np.nanmax(array)}"
        )

        print(
            f"       Mean  : {np.nanmean(array)}"
        )

    print("\n" + "=" * 70)
    print("INSPECTION COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()
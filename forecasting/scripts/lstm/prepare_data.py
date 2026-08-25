from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

FEATURE_COLUMNS = [
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
]

OUTPUT_COLUMNS = [
    "timestamp",
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
]

RESAMPLE_SECONDS = 5

# Kapasitas zona yang digunakan saat training.
# Pada dataset kamu, densityIndex sebelumnya dihitung:
#
# total_di_zona / 33
#
# sehingga nilai maksimal teoritis = 1.0
ZONE_CAPACITY = 33.0


# ============================================================
# PATH
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
FORECASTING_ROOT = SCRIPT_DIR.parent.parent

DEFAULT_CROSSING = (
    FORECASTING_ROOT / "data" / "crossing_simpang.csv"
)

DEFAULT_SNAPSHOT = (
    FORECASTING_ROOT / "data" / "snapshot_zona.csv"
)

OUTPUT_DIR = FORECASTING_ROOT / "outputs" / "lstm"

DEFAULT_OUTPUT = OUTPUT_DIR / "data_gabungan.csv"


# ============================================================
# LOGGING
# ============================================================

def print_section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# VALIDATION
# ============================================================

def validate_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    filename: str,
) -> None:

    missing = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            f"\nKolom berikut tidak ditemukan pada {filename}:\n"
            f"{missing}\n\n"
            f"Kolom tersedia:\n"
            f"{list(dataframe.columns)}"
        )


# ============================================================
# LOAD CROSSING
# ============================================================

def load_crossing(path: Path) -> pd.DataFrame:

    print_section("[1] Loading crossing dataset")

    if not path.exists():
        raise FileNotFoundError(
            f"File crossing tidak ditemukan:\n{path}"
        )

    dataframe = pd.read_csv(path)

    validate_columns(
        dataframe,
        [
            "timestamp",
            "jumlah_crossing",
        ],
        path.name,
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
    )

    dataframe["jumlah_crossing"] = pd.to_numeric(
        dataframe["jumlah_crossing"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "timestamp",
            "jumlah_crossing",
        ]
    )

    # ========================================================
    # Agregasi seluruh kamera + garis pada timestamp yang sama
    # ========================================================

    dataframe = (
        dataframe
        .groupby("timestamp", as_index=False)
        ["jumlah_crossing"]
        .sum()
    )

    dataframe = dataframe.rename(
        columns={
            "jumlah_crossing": "vehicleCount"
        }
    )

    dataframe = dataframe.sort_values("timestamp")

    print(f"File             : {path}")
    print(f"Jumlah timestamp : {len(dataframe)}")

    print()
    print(dataframe.head(10).to_string(index=False))

    return dataframe


# ============================================================
# LOAD SNAPSHOT ZONA
# ============================================================

def load_snapshot(path: Path) -> pd.DataFrame:

    print_section("[2] Loading snapshot zona dataset")

    if not path.exists():
        raise FileNotFoundError(
            f"File snapshot zona tidak ditemukan:\n{path}"
        )

    dataframe = pd.read_csv(path)

    validate_columns(
        dataframe,
        [
            "timestamp",
            "total_di_zona",
        ],
        path.name,
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
    )

    dataframe["total_di_zona"] = pd.to_numeric(
        dataframe["total_di_zona"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "timestamp",
            "total_di_zona",
        ]
    )

    # ========================================================
    # Agregasi per timestamp
    #
    # Penting:
    # total_di_zona berasal dari beberapa kamera/lengan.
    #
    # Kita menggunakan rata-rata antar kamera/lengan supaya
    # tidak menghitung kendaraan yang sama berkali-kali.
    #
    # ANTREAN (ditambahkan 25 Agustus 2026, begitu CV mulai
    # benar-benar menghitung antrean -- sebelumnya kedua kolom
    # ini di-hardcode 0.0 di merge_datasets()):
    #
    # queue_length_veh pakai SUM, bukan mean seperti
    # total_di_zona. Alasan "jangan hitung kendaraan yang sama
    # dua kali" TIDAK berlaku di sini -- kendaraan yang antre di
    # lengan selatan bukan kendaraan yang sama dengan yang antre
    # di lengan barat, jadi menjumlahkannya benar secara fisik:
    # "berapa total kendaraan sedang mengantre di simpang ini".
    #
    # queue_length_m_est pakai MAX, bukan sum: menjumlahkan
    # METER antar-lengan tidak bermakna (itu bukan satu antrean
    # panjang, tapi empat antrean terpisah). MAX = "lengan
    # terparah", satuannya tetap meter dan tetap bisa dibaca.
    #
    # Pola sum/max ini mengikuti preseden yang sudah ada di
    # backend/app/services/realtime_forecast_service.py saat ia
    # meruntuhkan seluruh approach jadi satu deret.
    # ========================================================

    agregasi = {"total_di_zona": "mean"}

    if "queue_length_veh" in dataframe.columns:
        agregasi["queue_length_veh"] = "sum"

    if "queue_length_m_est" in dataframe.columns:
        agregasi["queue_length_m_est"] = "max"

    dataframe = (
        dataframe
        .groupby("timestamp", as_index=False)
        .agg(agregasi)
    )

    # ========================================================
    # Density Index
    #
    # densityIndex = total kendaraan / kapasitas zona
    #
    # Dibatasi 0..1 agar sesuai kontrak model.
    # ========================================================

    dataframe["densityIndex"] = (
        dataframe["total_di_zona"]
        / ZONE_CAPACITY
    )

    dataframe["densityIndex"] = (
        dataframe["densityIndex"]
        .clip(lower=0.0, upper=1.0)
    )

    dataframe = dataframe.sort_values("timestamp")

    print(f"File             : {path}")
    print(f"Jumlah timestamp : {len(dataframe)}")

    print()
    print(
        dataframe[
            [
                "timestamp",
                "total_di_zona",
                "densityIndex",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    return dataframe


# ============================================================
# RESAMPLE CROSSING
# ============================================================

def resample_crossing(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    print_section("[3A] Resampling crossing → 5 detik")

    dataframe = dataframe.copy()

    dataframe = dataframe.set_index("timestamp")

    # Crossing merupakan jumlah kendaraan yang lewat.
    #
    # Untuk data crossing:
    # gunakan SUM ketika terdapat beberapa record
    # di dalam interval 5 detik.
    dataframe = (
        dataframe[
            ["vehicleCount"]
        ]
        .resample(f"{RESAMPLE_SECONDS}s")
        .sum()
    )

    dataframe = dataframe.reset_index()

    dataframe["vehicleCount"] = (
        dataframe["vehicleCount"]
        .fillna(0.0)
    )

    print(
        f"Jumlah timestamp setelah resample : "
        f"{len(dataframe)}"
    )

    return dataframe


# ============================================================
# RESAMPLE SNAPSHOT
# ============================================================

def resample_snapshot(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    print_section("[3B] Resampling snapshot zona → 5 detik")

    dataframe = dataframe.copy()

    dataframe = dataframe.set_index("timestamp")

    # Snapshot zona adalah kondisi sesaat.
    #
    # Untuk snapshot:
    # gunakan MEAN dalam interval 5 detik.
    #
    # Kolom antrean ikut MEAN juga, dan di sini itu memang yang
    # benar -- beda dari agregasi LINTAS-LENGAN di load_snapshot()
    # yang pakai sum/max. Yang ini agregasi LINTAS-WAKTU (beberapa
    # detik di dalam satu jendela 5 detik), dan antrean itu
    # besaran KEHADIRAN: menjumlahkannya antar-detik akan
    # menghitung kendaraan diam yang sama berkali-kali -- persis
    # kesalahan yang dicatat di cv/vehicle_counter_pingit.py soal
    # jendela 5 detik.
    kolom_dipakai = ["densityIndex"]

    for kolom in ("queue_length_veh", "queue_length_m_est"):
        if kolom in dataframe.columns:
            kolom_dipakai.append(kolom)

    dataframe = (
        dataframe[
            kolom_dipakai
        ]
        .resample(f"{RESAMPLE_SECONDS}s")
        .mean()
    )

    dataframe = dataframe.reset_index()

    print(
        f"Jumlah timestamp setelah resample : "
        f"{len(dataframe)}"
    )

    return dataframe


# ============================================================
# MERGE DATASETS
# ============================================================

def merge_datasets(
    crossing: pd.DataFrame,
    snapshot: pd.DataFrame,
) -> pd.DataFrame:

    print_section("[4] Menggabungkan dataset")

    crossing_resampled = resample_crossing(crossing)

    snapshot_resampled = resample_snapshot(snapshot)

    print()
    print(
        f"Crossing setelah resample : "
        f"{len(crossing_resampled)}"
    )

    print(
        f"Snapshot setelah resample : "
        f"{len(snapshot_resampled)}"
    )

    # ========================================================
    # INNER JOIN
    #
    # Hanya timestamp yang mempunyai kedua sumber data
    # yang dipakai.
    # ========================================================

    merged = pd.merge(
        crossing_resampled,
        snapshot_resampled,
        on="timestamp",
        how="inner",
    )

    # ========================================================
    # Queue
    #
    # Sampai 25 Agustus 2026 dua kolom ini di-hardcode 0.0 di
    # sini karena CV memang belum menghitung antrean. Sejak
    # cv/vehicle_counter_pingit.py punya hitung_antrean(),
    # snapshot_zona.csv sudah membawa queue_length_veh dan
    # queue_length_m_est yang benar-benar berisi, jadi keduanya
    # dipakai apa adanya lewat load_snapshot()/resample_snapshot().
    #
    # Fallback 0.0 DIPERTAHANKAN untuk CSV lama yang belum punya
    # kolom itu -- supaya skrip ini tidak mendadak gagal keras
    # kalau dijalankan ke rekaman hasil run sebelum perubahan CV.
    # Kalau angkanya nol semua, cek dulu apakah CSV sumbernya
    # memang CSV lama, sebelum menyalahkan modelnya.
    # ========================================================

    if "queue_length_veh" in merged.columns:
        merged["queueLengthVeh"] = (
            merged["queue_length_veh"].fillna(0.0)
        )
    else:
        merged["queueLengthVeh"] = 0.0

    if "queue_length_m_est" in merged.columns:
        merged["queueLengthMEst"] = (
            merged["queue_length_m_est"].fillna(0.0)
        )
    else:
        merged["queueLengthMEst"] = 0.0

    # ========================================================
    # Susun kolom sesuai MODEL CONTRACT
    # ========================================================

    merged = merged[
        OUTPUT_COLUMNS
    ]

    merged = merged.sort_values(
        "timestamp"
    )

    merged = merged.dropna(
        subset=FEATURE_COLUMNS
    )

    merged = merged.reset_index(
        drop=True
    )

    print()
    print(
        f"Timeline valid : {len(merged)}"
    )

    print()
    print("Contoh hasil gabungan:")

    print(
        merged.head(20).to_string(
            index=False
        )
    )

    return merged


# ============================================================
# VALIDATE OUTPUT
# ============================================================

def validate_output(
    dataframe: pd.DataFrame,
) -> None:

    print_section("[5] Validasi dataset")

    # --------------------------------------------------------
    # Validasi kolom
    # --------------------------------------------------------

    missing_columns = [
        column
        for column in OUTPUT_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom output hilang: "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Validasi timestamp
    # --------------------------------------------------------

    if not dataframe["timestamp"].is_monotonic_increasing:
        raise ValueError(
            "Timestamp tidak berurutan."
        )

    # --------------------------------------------------------
    # Validasi NaN
    # --------------------------------------------------------

    nan_counts = dataframe[
        FEATURE_COLUMNS
    ].isna().sum()

    if nan_counts.any():

        print("PERINGATAN: ditemukan NaN")

        print(
            nan_counts[
                nan_counts > 0
            ]
        )

    # --------------------------------------------------------
    # Validasi queue
    # --------------------------------------------------------

    queue_vehicle_unique = (
        dataframe["queueLengthVeh"]
        .unique()
    )

    queue_meter_unique = (
        dataframe["queueLengthMEst"]
        .unique()
    )

    print()
    print("Distribusi fitur:")

    print(
        dataframe[
            FEATURE_COLUMNS
        ].describe().to_string()
    )

    print()
    print(
        "Nilai queueLengthVeh :",
        queue_vehicle_unique,
    )

    print(
        "Nilai queueLengthMEst:",
        queue_meter_unique,
    )

    # --------------------------------------------------------
    # Interval timestamp
    # --------------------------------------------------------

    if len(dataframe) >= 2:

        intervals = (
            dataframe["timestamp"]
            .diff()
            .dropna()
            .dt.total_seconds()
        )

        print()
        print("Interval dataset:")

        print(
            f"Median : {intervals.median():.1f} detik"
        )

        print(
            f"Minimum: {intervals.min():.1f} detik"
        )

        print(
            f"Maksimum: {intervals.max():.1f} detik"
        )


# ============================================================
# SAVE DATASET
# ============================================================

def save_dataset(
    dataframe: pd.DataFrame,
    output_path: Path,
) -> None:

    print_section("[6] Menyimpan dataset")

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Dataset berhasil disimpan:"
    )

    print(output_path)

    print()
    print(
        f"Jumlah baris : {len(dataframe)}"
    )

    print(
        f"Jumlah kolom : {len(dataframe.columns)}"
    )


# ============================================================
# ARGUMENT PARSER
# ============================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Menyiapkan dataset gabungan "
            "crossing + snapshot zona "
            "untuk SmartTwin LSTM."
        )
    )

    parser.add_argument(
        "--crossing",
        type=Path,
        default=DEFAULT_CROSSING,
        help=(
            "Path ke crossing_simpang.csv"
        ),
    )

    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT,
        help=(
            "Path ke snapshot_zona.csv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Path output data_gabungan.csv"
        ),
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_arguments()

    print()
    print("=" * 70)
    print("SMARTTWIN - PREPARE LSTM DATASET")
    print("=" * 70)

    print()
    print("MODEL CONTRACT")

    print(
        "Features:",
        FEATURE_COLUMNS,
    )

    print(
        f"Resampling: "
        f"{RESAMPLE_SECONDS} detik"
    )

    print(
        f"Zone capacity: "
        f"{ZONE_CAPACITY}"
    )

    print()
    print("INPUT")

    print(
        "Crossing :",
        args.crossing,
    )

    print(
        "Snapshot :",
        args.snapshot,
    )

    print()
    print("OUTPUT")

    print(
        "Output   :",
        args.output,
    )

    # ========================================================
    # LOAD
    # ========================================================

    crossing = load_crossing(
        args.crossing
    )

    snapshot = load_snapshot(
        args.snapshot
    )

    # ========================================================
    # MERGE
    # ========================================================

    merged = merge_datasets(
        crossing,
        snapshot,
    )

    # ========================================================
    # VALIDATE
    # ========================================================

    validate_output(
        merged
    )

    # ========================================================
    # SAVE
    # ========================================================

    save_dataset(
        merged,
        args.output,
    )

    # ========================================================
    # FINAL
    # ========================================================

    print()
    print("=" * 70)
    print("DATASET SIAP")
    print("=" * 70)

    print()
    print(
        "File:",
        args.output,
    )

    print()
    print(
        "Kolom:"
    )

    for column in merged.columns:
        print(
            f"  - {column}"
        )

    print()
    print(
        "Sekarang jalankan:"
    )

    print()
    print(
        f'py scripts/lstm/predict.py '
        f'--input "{args.output}"'
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
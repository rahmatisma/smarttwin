"""
Jembatan CSV vehicle_counter_copy.py -> trafficLaneMetrics (Supabase).

Kenapa file ini ada, bukan langsung pakai TrafficStateBuilder:
    TrafficStateBuilder (lihat traffic_state_builder.py) sekarang murni
    Supabase-native -- dia baca trafficLaneMetrics dan mengagregasi ke
    trafficApproachStates, tidak tahu apa-apa soal CSV. Yang menulis
    trafficLaneMetrics itu tanggung jawab modul terpisah -- ini dia,
    khusus untuk output vehicle_counter_copy.py (crossing_simpang.csv +
    percobaan_logic_simpang.csv).

Kenapa BUKAN pakai TrafficMetricsWriter.write_cv_window() langsung:
    write_cv_window() -> get_lane() mencari lane cuma dari kolom laneId
    ("lane_1"/"lane_2"), TANPA disaring approach. Karena keempat lengan
    simpang ini SAMA-SAMA punya lane bernama "lane_1", get_lane() akan
    selalu balikin baris lane_1 milik lengan yang PERTAMA ketemu di query
    (bukan lengan yang dimaksud) -- kalau dipakai apa adanya, data 4
    lengan bakal numpuk ke satu lane yang sama. Jadi resolusi lane di
    sini dilakukan manual (_resolve_lane_ids), lalu insert langsung lewat
    TrafficMetricsWriter.insert_lane_metrics() (bagian itu sudah benar,
    tidak ada masalah serupa). Perlu disampaikan ke pemilik
    traffic_metrics_writer.py -- ini bug asli di sana, bukan sesuatu yang
    diperbaiki diam-diam di sini.

Kenapa createdAt di-set manual (bukan lewat TrafficMetricsWriter.create_traffic_state()):
    create_traffic_state() tidak mengirim createdAt eksplisit, jadi tiap
    baris dapat waktu INSERT-nya sendiri-sendiri (beda tipis per baris).
    Frontend (frontend/src/lib/supabaseData.ts::fetchTrafficState)
    mengelompokkan "satu batch ingest" lewat createdAt yang PERSIS sama
    di semua baris -- kalau tiap baris beda, pengelompokan itu cuma
    dapat sebagian baris. Makanya di sini insert trafficStates dilakukan
    manual dengan satu createdAt yang dibagi ke seluruh window dalam satu
    kali run.

CV belum bisa membedakan lajur (lane_1 vs lane_2) -- semua data approach
ditulis ke lane_1 lengan itu (satu-satunya lajur yang selalu ada di
keempat lengan). lane_2 sengaja dibiarkan kosong. Ini pendekatan
approksimasi, bukan pengukuran per-lajur yang akurat.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from postgrest.exceptions import APIError

from app.pipeline.traffic_state_builder import TrafficStateBuilder
from app.services.traffic_metrics_writer import TrafficMetricsWriter

INTERSECTION_ID = "simpang4-pingit"
WINDOW_SECONDS = 5

# Lihat catatan yang sama di traffic_state_builder.py versi CSV (commit
# 473134b) -- CCTV_2 framenya memotret badan simpang dan punya DUA garis
# crossing sekaligus (MAGELANG untuk utara, DIPONEGORO untuk timur).
CROSS_LABEL_MAP: dict[str, str] = {
    "selatan": "south",
    "MAGELANG": "north",
    "DIPONEGORO": "east",
    "barat": "west",
}

# CCTV_2 zonanya "simpang_tengah" (badan simpang, campuran arah) --
# dipakai sebagai PROXY density utara, bukan pengukuran murni lengan
# utara. CCTV_4 (timur) sudah punya zona sendiri yang murni.
DENSITY_LENGAN_MAP: dict[str, str] = {
    "selatan": "south",
    "barat": "west",
    "timur": "east",
    "simpang_tengah": "north",  # proxy
}


def get_default_cross_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "cv" / "output" / "crossing_simpang.csv"


def get_default_density_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "cv" / "output" / "percobaan_logic_simpang.csv"


def _load_merged(cross_path: Path, density_path: Path) -> pd.DataFrame:
    """Satu baris per (windowStart, approach), sudah gabungan crossing+density.

    vehicleCount/carCount/motorcycleCount/busCount/truckCount diambil
    dari CROSSING (ALIRAN -- kendaraan yang melintas jendela itu).
    densityIndex diambil dari DENSITY (KEHADIRAN -- rata-rata kendaraan
    di zona selama jendela itu). Ini dua populasi berbeda -- lihat
    catatan besar di vehicle_counter.py soal ALIRAN vs KEHADIRAN.
    """

    df_cross = pd.read_csv(cross_path)
    df_density = pd.read_csv(density_path)

    df_cross["timestamp"] = pd.to_datetime(df_cross["timestamp"], errors="coerce")
    df_density["timestamp"] = pd.to_datetime(df_density["timestamp"], errors="coerce")

    df_cross["approach"] = df_cross["label_garis"].map(CROSS_LABEL_MAP)
    df_density["approach"] = df_density["lengan"].map(DENSITY_LENGAN_MAP)

    df_cross = df_cross.dropna(subset=["approach", "timestamp"])
    df_density = df_density.dropna(subset=["approach", "timestamp"])

    cross_agg = df_cross.groupby(["timestamp", "approach"], as_index=False).agg(
        vehicleCount=("jumlah_crossing", "sum"),
        carCount=("mobil_crossing", "sum"),
        motorcycleCount=("motor_crossing", "sum"),
        busCount=("bus_crossing", "sum"),
        truckCount=("truk_crossing", "sum"),
    )

    density_agg = df_density.groupby(["timestamp", "approach"], as_index=False).agg(
        densityIndex=("total_di_zona", "mean"),
    )

    merged = pd.merge(cross_agg, density_agg, on=["timestamp", "approach"], how="outer")

    for col in ("vehicleCount", "carCount", "motorcycleCount", "busCount", "truckCount"):
        merged[col] = merged[col].fillna(0).round().astype(int)
    merged["densityIndex"] = merged["densityIndex"].fillna(0.0).astype(float)

    merged["windowStart"] = merged["timestamp"]
    merged["windowEnd"] = merged["timestamp"] + pd.Timedelta(seconds=WINDOW_SECONDS)

    return merged.sort_values(["windowStart", "approach"]).reset_index(drop=True)


def _resolve_lane_ids(writer: TrafficMetricsWriter, intersection_row_id: int) -> dict[str, int]:
    """approach name -> id baris lane_1 milik approach itu.

    Tidak lewat writer.get_lane() -- lihat catatan panjang di docstring
    modul ini soal kenapa get_lane() tidak bisa dipakai generik di sini.
    """

    approaches = (
        writer.supabase.table("approaches")
        .select("id, approach")
        .eq("intersectionId", intersection_row_id)
        .execute()
        .data
        or []
    )
    approach_id_by_name = {row["approach"]: int(row["id"]) for row in approaches}

    lanes = (
        writer.supabase.table("lanes")
        .select("id, approachId")
        .eq("laneId", "lane_1")
        .execute()
        .data
        or []
    )
    lane_row_by_approach_id = {int(row["approachId"]): int(row["id"]) for row in lanes}

    return {
        name: lane_row_by_approach_id[approach_id]
        for name, approach_id in approach_id_by_name.items()
        if approach_id in lane_row_by_approach_id
    }


def _insert_traffic_state(
    writer: TrafficMetricsWriter,
    intersection_row_id: int,
    window_start: datetime,
    window_end: datetime,
    created_at: str,
    source: str,
) -> int:
    """Sama seperti TrafficMetricsWriter.create_traffic_state(), plus
    createdAt eksplisit -- lihat docstring modul ini kenapa perlu.

    Kalau window ini sudah pernah di-ingest sebelumnya (mis. run
    kepotong di tengah lalu diulang), baris trafficStates lama untuk
    window yang sama persis DIHAPUS dulu (bersama trafficLaneMetrics-
    nya, lewat FK cascade manual) sebelum insert ulang -- supaya
    idempotent walau tabel punya UNIQUE(intersectionId,windowStart,
    windowEnd) dan writer ini sendiri cuma bisa INSERT (tidak ada
    upsert bawaan di TrafficMetricsWriter)."""

    payload = {
        "intersectionId": intersection_row_id,
        "windowStart": window_start.isoformat(),
        "windowEnd": window_end.isoformat(),
        "source": source,
        "processingJobId": None,
        "createdAt": created_at,
    }

    try:
        result = writer.supabase.table("trafficStates").insert(payload).execute()
    except APIError as exc:
        if exc.code != "23505":
            raise

        existing = (
            writer.supabase.table("trafficStates")
            .select("id")
            .eq("intersectionId", intersection_row_id)
            .eq("windowStart", window_start.isoformat())
            .eq("windowEnd", window_end.isoformat())
            .execute()
            .data
            or []
        )

        for row in existing:
            existing_id = int(row["id"])
            writer.supabase.table("trafficLaneMetrics").delete().eq(
                "trafficStateId", existing_id
            ).execute()
            writer.supabase.table("trafficApproachStates").delete().eq(
                "trafficStateId", existing_id
            ).execute()
            writer.supabase.table("trafficStates").delete().eq(
                "id", existing_id
            ).execute()

        result = writer.supabase.table("trafficStates").insert(payload).execute()

    rows = result.data or []

    if not rows:
        raise RuntimeError("Gagal membuat trafficStates.")

    return int(rows[0]["id"])


def ingest(
    cross_path: str | Path | None = None,
    density_path: str | Path | None = None,
    *,
    source: str = "cv",
) -> dict[str, Any]:
    """CSV -> trafficLaneMetrics -> (lewat TrafficStateBuilder) trafficApproachStates."""

    cross_path = Path(cross_path) if cross_path else get_default_cross_path()
    density_path = Path(density_path) if density_path else get_default_density_path()

    if not cross_path.exists() or not density_path.exists():
        raise FileNotFoundError("Satu atau lebih CSV CV output tidak ditemukan.")

    merged = _load_merged(cross_path, density_path)

    if merged.empty:
        return {"windowsWritten": 0, "statesBuilt": 0}

    writer = TrafficMetricsWriter()
    intersection = writer.get_intersection(INTERSECTION_ID)
    intersection_row_id = int(intersection["id"])
    lane_id_by_approach = _resolve_lane_ids(writer, intersection_row_id)

    batch_created_at = datetime.now(timezone.utc).isoformat()

    windows_written = 0

    for (window_start, window_end), group in merged.groupby(["windowStart", "windowEnd"]):

        metrics: list[dict[str, Any]] = []

        for _, row in group.iterrows():

            lane_row_id = lane_id_by_approach.get(row["approach"])

            if lane_row_id is None:
                continue

            metrics.append(
                {
                    "laneId": lane_row_id,
                    "timestamp": window_end.to_pydatetime(),
                    "vehicleCount": int(row["vehicleCount"]),
                    "carCount": int(row["carCount"]),
                    "motorcycleCount": int(row["motorcycleCount"]),
                    "busCount": int(row["busCount"]),
                    "truckCount": int(row["truckCount"]),
                    "queueLengthVeh": 0,
                    "queueLengthMEst": 0.0,
                    "densityIndex": float(row["densityIndex"]),
                }
            )

        if not metrics:
            continue

        traffic_state_id = _insert_traffic_state(
            writer,
            intersection_row_id,
            window_start.to_pydatetime(),
            window_end.to_pydatetime(),
            batch_created_at,
            source,
        )

        writer.insert_lane_metrics(traffic_state_id, metrics)
        windows_written += 1

    # Agregasi trafficLaneMetrics -> trafficApproachStates, lewat builder
    # resmi (bukan ditulis ulang di sini) -- limit digenerosir karena
    # get_latest_traffic_states() ambil N baris ter-windowStart-terbaru
    # dari SELURUH tabel (bukan cuma punya run ini), dan tabel sudah
    # punya histori campuran dari beberapa hari.
    builder = TrafficStateBuilder()
    built_states = builder.run_once(limit=max(windows_written * 2, 200), save=True)

    return {
        "windowsWritten": windows_written,
        "statesBuilt": len(built_states),
    }

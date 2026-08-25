"""
Jembatan CSV vehicle_counter_pingit.py -> trafficLaneMetrics (Supabase).

Kenapa file ini ada, bukan langsung pakai TrafficStateBuilder:
    TrafficStateBuilder (lihat traffic_state_builder.py) sekarang murni
    Supabase-native -- dia baca trafficLaneMetrics dan mengagregasi ke
    trafficApproachStates, tidak tahu apa-apa soal CSV. Yang menulis
    trafficLaneMetrics itu tanggung jawab modul terpisah -- ini dia,
    khusus untuk output vehicle_counter_pingit.py (crossing_simpang.csv +
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
    # snapshot_zona.csv, BUKAN percobaan_logic_simpang.csv -- keduanya
    # skema kolomnya identik (ditulis oleh vehicle_counter_pingit.py yang
    # sama), tapi beda tujuan. percobaan_logic_simpang.csv sudah
    # dirata-rata per window 5 detik OLEH SCRIPT CV ITU SENDIRI --
    # cukup halus tapi bisa meleset lumayan dari apa yang kelihatan di
    # video pada satu detik tertentu (terverifikasi 25 Agustus: jam
    # 16:31:20 percobaan_logic bilang total~9.8, padahal overlay CV
    # asli di detik itu jelas menunjukkan 11 -- match persis dengan
    # snapshot_zona.csv, bukan percobaan_logic). snapshot_zona.csv
    # sengaja dibuat CV per DETIK, TIDAK dirata-rata, buat kasus
    # "tampilan hidup" persis ini -- diagregasi ke window 5 detik di
    # bawah (_load_merged) supaya tetap sinkron sama crossing CSV.
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "cv" / "output" / "snapshot_zona.csv"


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

    # density_path (snapshot_zona.csv) dicatat per DETIK, sedangkan
    # cross_path (crossing_simpang.csv) per 5 DETIK -- floor ke jendela
    # 5 detik yang sama supaya baris bisa digabung nanti (kalau tidak,
    # cuma 1 dari 5 baris snapshot yang match timestamp persis, 4
    # sisanya jadi baris density-only yang tidak pernah ketemu crossing-nya).
    df_density["timestamp"] = df_density["timestamp"].dt.floor("5s")

    df_cross["approach"] = df_cross["label_garis"].map(CROSS_LABEL_MAP)
    df_density["approach"] = df_density["lengan"].map(DENSITY_LENGAN_MAP)

    df_cross = df_cross.dropna(subset=["approach", "timestamp"])
    df_density = df_density.dropna(subset=["approach", "timestamp"])

    # vehicleCount (volume) TETAP dari crossing -- itu representasi arus
    # (berapa lewat garis), dipertahankan apa adanya karena mungkin
    # dipakai bagian lain yang memang butuh arus, bukan kehadiran.
    cross_agg = df_cross.groupby(["timestamp", "approach"], as_index=False).agg(
        vehicleCount=("jumlah_crossing", "sum"),
    )

    # carCount/motorcycleCount/busCount/truckCount SENGAJA dari ZONA
    # (snapshot_zona.csv), BUKAN crossing lagi -- disepakati 25 Agustus
    # 2026 supaya breakdown per-kelas di dashboard ("Vehicle Detection")
    # konsisten dengan Total Vehicles/Density Index yang juga sudah zona,
    # bukan campur dua populasi beda dalam satu panel yang sama.
    #
    # mean dari 5 bacaan per-detik dalam window itu -- masih rata-rata,
    # tapi rata-rata dari sample MENTAH per detik (bukan pra-rata-rata
    # internal CV), dan tiap sample individualnya presisi ke video.
    #
    # queue_length_veh/queue_length_m_est BARU ada di snapshot_zona.csv
    # sejak vehicle_counter_pingit.py ditambah hitung_antrean() (25
    # Agustus 2026) -- CSV lama (hasil run sebelum itu) belum punya
    # kolom ini. Dicek eksplisit (bukan diasumsikan selalu ada) supaya
    # bridge ini tidak crash kalau dijalankan ke CSV lama, dan tetap
    # jujur queueLengthVeh/queueLengthMEst = 0 (bukan error) kalau
    # datanya memang belum pernah diproses ulang dengan kode baru.
    ada_kolom_antrean = (
        "queue_length_veh" in df_density.columns
        and "queue_length_m_est" in df_density.columns
    )

    agregasi = {
        "densityIndex": ("total_di_zona", "mean"),
        "carCount": ("mobil_di_zona", "mean"),
        "motorcycleCount": ("motor_di_zona", "mean"),
        "busCount": ("bus_di_zona", "mean"),
        "truckCount": ("truk_di_zona", "mean"),
    }

    if ada_kolom_antrean:
        agregasi["queueLengthVeh"] = ("queue_length_veh", "mean")
        agregasi["queueLengthMEst"] = ("queue_length_m_est", "mean")

    density_agg = df_density.groupby(["timestamp", "approach"], as_index=False).agg(
        **agregasi
    )

    merged = pd.merge(cross_agg, density_agg, on=["timestamp", "approach"], how="outer")

    merged["vehicleCount"] = merged["vehicleCount"].fillna(0).round().astype(int)
    for col in ("carCount", "motorcycleCount", "busCount", "truckCount"):
        merged[col] = merged[col].fillna(0).round().astype(int)
    merged["densityIndex"] = merged["densityIndex"].fillna(0.0).astype(float)

    if ada_kolom_antrean:
        merged["queueLengthVeh"] = merged["queueLengthVeh"].fillna(0).round().astype(int)
        merged["queueLengthMEst"] = merged["queueLengthMEst"].fillna(0.0).astype(float)
    else:
        merged["queueLengthVeh"] = 0
        merged["queueLengthMEst"] = 0.0

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
    written_states: list[dict[str, Any]] = []

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
                    "queueLengthVeh": int(row["queueLengthVeh"]),
                    "queueLengthMEst": float(row["queueLengthMEst"]),
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

        written_states.append(
            {
                "id": traffic_state_id,
                "intersectionId": intersection_row_id,
                "windowStart": window_start.to_pydatetime().isoformat(),
                "windowEnd": window_end.to_pydatetime().isoformat(),
                "source": source,
            }
        )

    # Agregasi trafficLaneMetrics -> trafficApproachStates, lewat method
    # resmi builder (build_state/save_approach_states), TAPI ditarget
    # persis ke trafficStateId yang baru saja ditulis di sini -- BUKAN
    # lewat builder.run_once()/build_latest_states(), yang mengambil "N
    # baris ter-windowStart-terbaru dari SELURUH tabel trafficStates".
    # Tabel itu sudah punya histori campuran dari banyak hari/sumber
    # (termasuk baris windowStart di masa jauh lebih "baru" daripada
    # jam rekaman video kita, mis. baris source=cv_test) -- dicoba
    # dengan run_once() dan yang ke-build cuma baris cv_test itu,
    # bukan punya kita, walau limit sudah digenerosir 2x jumlah window.
    builder = TrafficStateBuilder()
    traffic_state_ids = [state["id"] for state in written_states]
    lane_metrics = builder.get_lane_metrics(traffic_state_ids)

    metrics_by_state: dict[int, list[dict[str, Any]]] = {}
    for metric in lane_metrics:
        metrics_by_state.setdefault(int(metric["trafficStateId"]), []).append(metric)

    intersection_map, approach_map, lane_map = builder.build_relation_maps()

    states_built = 0
    for state in written_states:
        state_metrics = metrics_by_state.get(state["id"], [])
        if not state_metrics:
            continue
        built_state = builder.build_state(
            traffic_state=state,
            lane_metrics=state_metrics,
            intersection_map=intersection_map,
            approach_map=approach_map,
            lane_map=lane_map,
        )
        if built_state is None:
            continue
        builder.save_approach_states(
            traffic_state_id=state["id"],
            built_state=built_state,
        )
        states_built += 1

    return {
        "windowsWritten": windows_written,
        "statesBuilt": states_built,
    }

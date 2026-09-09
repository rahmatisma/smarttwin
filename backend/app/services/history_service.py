"""Riwayat keputusan sistem — sumber data halaman Riwayat.

Beda peran dari `liveScenarioCache` (1 baris, ditimpa tiap siklus, untuk
menjawab "apa rekomendasi SEKARANG"): modul ini menjawab "sistem pernah
memutuskan apa saja, kapan, dan kondisi lalu lintasnya seperti apa".

Bentuk datanya bertingkat, sesuai cara halaman Riwayat menampilkannya:

    satu siklus (satu timestamp)
      ├── 4 baris `recommendations`      -> durasi hijau per lengan
      ├── n baris `simulations`          -> kandidat yang diuji + pemenangnya
      │     └── `simulationMetrics`      -> delay / antrean / throughput
      └── `trafficApproachStates`        -> kondisi lalu lintas PEMICU
            (disambungkan lewat simulations.trafficStateId, tidak diduplikasi)

Penanda "berubah" sengaja TIDAK dihitung di sini melainkan di frontend,
dengan membandingkan baris berurutan — supaya ambangnya bisa diubah kapan
saja tanpa menyentuh data yang sudah tersimpan.
"""

from __future__ import annotations

import math
from typing import Any

from app.services.supabase_client import get_supabase

# Satu siklus worker selalu menulis satu baris rekomendasi per lengan.
# Dipakai untuk menerjemahkan paginasi "per siklus" (yang diminta UI)
# menjadi paginasi "per baris" (yang dimengerti PostgREST).
PHASES_PER_CYCLE = 4

# LOS murni turunan dari delay, jadi tidak ikut disimpan di database —
# dihitung ulang di sini supaya tidak ada angka kembar yang bisa berbeda.
_LOS_THRESHOLDS = (
    (10.0, "A"),
    (20.0, "B"),
    (35.0, "C"),
    (55.0, "D"),
    (80.0, "E"),
)


def _calculate_los(avg_delay_seconds: float | None) -> str | None:
    if avg_delay_seconds is None:
        return None
    for threshold, label in _LOS_THRESHOLDS:
        if avg_delay_seconds <= threshold:
            return label
    return "F"


# Metrik yang dibandingkan Before/After, dan arah "membaik"-nya. Baseline =
# pengaturan lampu apa adanya (tanpa Scenario Generator); winner = yang
# benar-benar direkomendasikan sistem. KEDUANYA disimulasikan sungguhan di
# SUMO, bukan diperkirakan -- jadi selisihnya angka yang bisa
# dipertanggungjawabkan, bukan estimasi.
_BEFORE_AFTER_METRICS = (
    # (field, label, satuan, turun_berarti_membaik)
    ("avgDelaySeconds", "Waktu Tunggu", "s", True),
    ("avgQueueLengthM", "Antrean", "m", True),
    ("throughputVeh", "Throughput", "kendaraan", False),
)

# Versi per lengan dari tabel di atas. Ada dua metrik antrean per lengan
# dengan satuan beda (kendaraan vs meter, keduanya diturunkan dari sumber
# yang sama -- lihat scenario_generator.py::queue_length_m_by_approach())
# -- label dibedakan eksplisit ("Antrean (kendaraan)"/"Antrean (meter)")
# supaya tidak tertukar dengan kolom "Antrean" agregat di tabel utama.
_BEFORE_AFTER_APPROACH_FIELDS = (
    # (field per-lengan, label, satuan, turun_berarti_membaik)
    ("delayByApproachSeconds", "Waktu Tunggu", "s", True),
    ("queueLengthVehByApproach", "Antrean (kendaraan)", "kendaraan", True),
    ("avgQueueLengthMByApproach", "Antrean (meter)", "m", True),
    ("throughputVehByApproach", "Throughput", "kendaraan", False),
)

_APPROACHES = ("north", "south", "east", "west")

BASELINE_CANDIDATE_ID = "baseline"
# Acuan "sebelum" = lampu fixed-time yang BENAR-BENAR TERPASANG sekarang
# (disimulasikan dengan demand yang sama). Pertanyaan yang dijawab:
# "seberapa lebih baik rekomendasi dibanding lampu yang jalan sekarang",
# bukan "kandidat mana yang terbaik". Siklus lama tanpa baris `realtime`
# jatuh ke kandidat `baseline` (perilaku sebelumnya).
REFERENCE_CANDIDATE_ID = "realtime"


def _metric_row(
    field: str, label: str, unit: str, lower_is_better: bool,
    before: float | None, after: float | None,
) -> dict[str, Any] | None:
    """Satu baris Before/After. Arah "membaik" ditentukan dari perbandingan
    NILAI, bukan dari persen yang sudah dibulatkan -- lampu terpasang (fixed
    50/4) hampir tidak pernah persis sama dengan rekomendasi, jadi selisih
    kecil (mis. -0,3%) tetap arah yang jelas, bukan "setara"."""
    if before is None or after is None:
        return None
    change_percent = round((after - before) / before * 100, 2) if before != 0 else None
    if after == before or before == 0:
        improved = None
    else:
        improved = (after < before) == lower_is_better
    return {
        "metric": field,
        "label": label,
        "unit": unit,
        "before": before,
        "after": after,
        "changePercent": change_percent,
        "improved": improved,
    }


def _compute_before_after(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Bandingkan lampu terpasang (`realtime`, before) vs pemenang (after).

    None kalau datanya tidak lengkap untuk dibandingkan -- mis. siklus lama
    dari sebelum fitur Scenario Generator tersambung ke riwayat, yang tidak
    punya baris `simulations` sama sekali.
    """
    baseline = next(
        (c for c in candidates if c["candidateId"] == REFERENCE_CANDIDATE_ID), None
    ) or next(
        (c for c in candidates if c["candidateId"] == BASELINE_CANDIDATE_ID), None
    )
    winner = next((c for c in candidates if c["isWinner"]), None)
    if baseline is None or winner is None:
        return None

    metrics = []
    for field, label, unit, lower_is_better in _BEFORE_AFTER_METRICS:
        row = _metric_row(
            field, label, unit, lower_is_better,
            baseline.get(field), winner.get(field),
        )
        if row is not None:
            metrics.append(row)

    # Sama seperti di atas, tapi dipecah per lengan -- cuma terisi untuk
    # siklus BARU (setelah delay/antrean/throughput per lengan mulai
    # disimpan). Siklus lama: by_approach jadi {} (bukan error).
    by_approach: dict[str, list[dict[str, Any]]] = {}
    for approach in _APPROACHES:
        approach_metrics = []
        for field, label, unit, lower_is_better in _BEFORE_AFTER_APPROACH_FIELDS:
            row = _metric_row(
                field, label, unit, lower_is_better,
                (baseline.get(field) or {}).get(approach),
                (winner.get(field) or {}).get(approach),
            )
            if row is not None:
                approach_metrics.append(row)
        if approach_metrics:
            by_approach[approach] = approach_metrics

    # True kalau rekomendasi benar-benar menurunkan delay dibanding lampu
    # terpasang. False = lampu terpasang sudah sama baik / lebih baik untuk
    # kondisi ini -- itu keputusan yang SAH, bukan sistem gagal berpikir.
    delay_metric = next(
        (m for m in metrics if m["metric"] == "avgDelaySeconds"), None
    )
    changed = bool(delay_metric and delay_metric["improved"] is True)

    return {
        "baselineCandidateId": baseline["candidateId"],
        "winnerCandidateId": winner["candidateId"],
        "changed": changed,
        "metrics": metrics,
        "byApproach": by_approach or None,
    }


class HistoryService:
    def __init__(self, supabase=None) -> None:
        # Koneksi dibuat lazy (lihat property di bawah) supaya import modul
        # ini tidak ikut gagal ketika env Supabase belum terpasang --
        # mengikuti pola LiveScenarioCacheService.
        self._supabase = supabase

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase

    # ------------------------------------------------------------------
    # INTERSECTION
    # ------------------------------------------------------------------

    def _resolve_intersection_row_id(self, intersection_id: str) -> int | None:
        result = (
            self.supabase.table("intersections")
            .select("id")
            .eq("intersectionId", intersection_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return int(rows[0]["id"]) if rows else None

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------

    def list_cycles(
        self,
        *,
        intersection_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Daftar siklus keputusan, terbaru dulu, dipaginasi per siklus."""

        row_id = self._resolve_intersection_row_id(intersection_id)
        if row_id is None:
            return {
                "page": page,
                "pageSize": page_size,
                "totalCycles": 0,
                "items": [],
                "olderCycleContext": None,
            }

        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        # PostgREST memotong di 1000 baris secara DIAM-DIAM tanpa .range().
        # Di sini rentangnya dihitung eksplisit dari nomor halaman supaya
        # tidak pernah bergantung pada batas bawaan itu.
        offset = (page - 1) * page_size * PHASES_PER_CYCLE
        # Ambil SATU siklus ekstra di luar halaman. Siklus ini tidak
        # ditampilkan dan tidak dihitung di paginasi -- dipakai HANYA sebagai
        # pembanding untuk baris terakhir halaman. Tanpa ini baris ke-N
        # (terakhir) tidak punya "siklus sebelumnya" (ada di halaman
        # berikutnya) sehingga frontend selalu menandainya "Tetap".
        limit = (page_size + 1) * PHASES_PER_CYCLE

        result = (
            self.supabase.table("recommendations")
            .select("*", count="exact")
            .eq("intersectionId", row_id)
            .order("timestamp", desc=True)
            .order("id", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        rows = result.data or []
        total_rows = result.count or 0

        cycles = self._group_by_timestamp(rows)
        self._attach_simulations(cycles)

        for cycle in cycles:
            cycle["beforeAfter"] = _compute_before_after(cycle["candidates"])

        visible = cycles[:page_size]
        older_context = cycles[page_size] if len(cycles) > page_size else None

        return {
            "page": page,
            "pageSize": page_size,
            "totalCycles": math.ceil(total_rows / PHASES_PER_CYCLE),
            "items": visible,
            # Siklus tepat sebelum baris terakhir (kronologis), null kalau
            # halaman ini memang menyentuh data paling lama. Frontend
            # memakainya hanya untuk menghitung status baris terakhir.
            "olderCycleContext": older_context,
        }

    # ------------------------------------------------------------------
    # GROUPING
    # ------------------------------------------------------------------

    @staticmethod
    def _group_by_timestamp(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cycles: dict[str, dict[str, Any]] = {}

        for row in rows:
            timestamp = str(row.get("timestamp"))
            cycle = cycles.setdefault(
                timestamp,
                {
                    "timestamp": timestamp,
                    "source": row.get("source"),
                    "recommendationIds": [],
                    "phases": [],
                    "candidates": [],
                    "trafficConditions": [],
                    "winner": None,
                    # Identitas KONDISI LALU LINTAS yang dievaluasi. Penting
                    # ditampilkan: kalau worker berjalan sementara CV tidak,
                    # kondisi terbaru tidak pernah berganti sehingga siklus
                    # yang berbeda sebenarnya mengevaluasi kondisi yang SAMA.
                    # Tanpa penanda ini, 6 baris identik terlihat seperti 6
                    # keputusan berbeda -- klaim yang tidak bisa dipertahankan.
                    "trafficStateId": None,
                },
            )
            cycle["recommendationIds"].append(row.get("id"))
            cycle["phases"].append(
                {
                    # Nama lengan disimpan dalam bahasa Inggris (kontrak
                    # docs/data-contract.md); frontend yang menerjemahkan.
                    "approach": row.get("recommendedPhase"),
                    "greenSeconds": row.get("recommendedGreenSeconds"),
                    "currentGreenSeconds": row.get("currentGreenSeconds"),
                    "confidence": row.get("confidence"),
                    "expectedDelayReductionPercent": row.get(
                        "expectedDelayReductionPercent"
                    ),
                }
            )

        return list(cycles.values())

    # ------------------------------------------------------------------
    # SIMULATIONS + METRICS + KONDISI PEMICU
    # ------------------------------------------------------------------

    def _attach_simulations(self, cycles: list[dict[str, Any]]) -> None:
        """Lengkapi tiap siklus dengan kandidat, metrik, dan kondisi pemicu."""

        all_recommendation_ids = [
            rec_id
            for cycle in cycles
            for rec_id in cycle["recommendationIds"]
            if rec_id is not None
        ]
        if not all_recommendation_ids:
            return

        simulations = (
            self.supabase.table("simulations")
            .select("*")
            .in_("recommendationId", all_recommendation_ids)
            .execute()
        ).data or []

        if not simulations:
            return

        simulation_ids = [row["id"] for row in simulations]
        # PostgREST memotong hasil di 1000 baris SECARA DIAM-DIAM (sama seperti
        # peringatan di list_cycles). Tiap simulasi punya ~22 baris metrik, jadi
        # ~45 simulasi saja sudah menembus batas -- dan yang terpotong justru
        # simulasi TERBARU (id tertinggi), sehingga siklus terbaru di tiap
        # halaman kehilangan metriknya ("menunggu metrik" padahal sudah ditulis).
        # Diambil per batch kecil supaya tiap query tetap di bawah cap.
        metrics: list[dict[str, Any]] = []
        _METRICS_BATCH = 40  # ~40 x ~22 baris = ~880, aman di bawah 1000
        for _start in range(0, len(simulation_ids), _METRICS_BATCH):
            _chunk = simulation_ids[_start:_start + _METRICS_BATCH]
            metrics.extend(
                (
                    self.supabase.table("simulationMetrics")
                    .select("*")
                    .in_("simulationId", _chunk)
                    .execute()
                ).data
                or []
            )

        metrics_by_simulation: dict[int, dict[str, Any]] = {}
        for metric in metrics:
            bucket = metrics_by_simulation.setdefault(metric["simulationId"], {})
            bucket[metric["metricName"]] = metric["metricValue"]

        # Kondisi lalu lintas pemicu — diambil lewat relasi trafficStateId,
        # bukan disalin ulang ke tabel riwayat.
        traffic_state_ids = sorted(
            {
                row["trafficStateId"]
                for row in simulations
                if row.get("trafficStateId") is not None
            }
        )
        conditions_by_state = self._load_traffic_conditions(traffic_state_ids)

        cycle_by_recommendation_id = {
            rec_id: cycle
            for cycle in cycles
            for rec_id in cycle["recommendationIds"]
        }

        for simulation in simulations:
            cycle = cycle_by_recommendation_id.get(simulation.get("recommendationId"))
            if cycle is None:
                continue

            simulation_metrics = metrics_by_simulation.get(simulation["id"], {})
            avg_delay = simulation_metrics.get("avgDelaySeconds")

            # Delay per lengan disimpan sebagai baris metrik terpisah
            # ("delaySeconds_north" dst, lihat scenario_worker.py::write_history()).
            # Cycle lama (sebelum perubahan ini) tidak akan punya baris-baris
            # ini -- delayByApproach jadi dict kosong, bukan error, untuk
            # riwayat lama.
            delay_by_approach = {
                approach: simulation_metrics[f"delaySeconds_{approach}"]
                for approach in ("north", "south", "east", "west")
                if simulation_metrics.get(f"delaySeconds_{approach}") is not None
            }
            los_by_approach = {
                approach: _calculate_los(delay)
                for approach, delay in delay_by_approach.items()
            }
            queue_by_approach = {
                approach: simulation_metrics[f"queueLengthVeh_{approach}"]
                for approach in ("north", "south", "east", "west")
                if simulation_metrics.get(f"queueLengthVeh_{approach}") is not None
            }
            # Versi meter dari queue_by_approach di atas -- baris metrik
            # terpisah ("queueLengthM_<lengan>", lihat
            # scenario_worker.py::write_history()). Cycle lama tidak akan
            # punya baris ini -- dict kosong, bukan error.
            queue_m_by_approach = {
                approach: simulation_metrics[f"queueLengthM_{approach}"]
                for approach in ("north", "south", "east", "west")
                if simulation_metrics.get(f"queueLengthM_{approach}") is not None
            }
            throughput_by_approach = {
                approach: simulation_metrics[f"throughputVeh_{approach}"]
                for approach in ("north", "south", "east", "west")
                if simulation_metrics.get(f"throughputVeh_{approach}") is not None
            }

            candidate_id = str(simulation.get("simulationName", "")).split(" @ ")[0]
            candidate = {
                "candidateId": candidate_id,
                # Baris acuan lampu terpasang -- BUKAN kandidat yang diadu.
                # Dipakai perbandingan Dampak, tidak ditampilkan di tabel
                # "Kandidat yang Diuji".
                "isReference": candidate_id == REFERENCE_CANDIDATE_ID,
                "isWinner": simulation.get("status") == "winner",
                "evaluation": {
                    "id": str(simulation.get("simulationName", "")).split(" | evaluation=")[-1],
                    "trafficStateId": simulation.get("trafficStateId"),
                    "durationSeconds": simulation_metrics.get("evaluationDurationSeconds"),
                    "seed": simulation_metrics.get("evaluationSeed"),
                    "targetVehicles": simulation_metrics.get("evaluationTargetVehicles"),
                    "demandSource": "traffic-state-snapshot",
                } if " | evaluation=" in str(simulation.get("simulationName", "")) else None,
                "avgDelaySeconds": avg_delay,
                "avgQueueLengthM": simulation_metrics.get("avgQueueLengthM"),
                "throughputVeh": simulation_metrics.get("throughputVeh"),
                "los": _calculate_los(avg_delay),
                "delayByApproachSeconds": delay_by_approach or None,
                "losByApproach": los_by_approach or None,
                "queueLengthVehByApproach": queue_by_approach or None,
                "avgQueueLengthMByApproach": queue_m_by_approach or None,
                "throughputVehByApproach": throughput_by_approach or None,
            }
            cycle["candidates"].append(candidate)

            if candidate["isWinner"]:
                cycle["winner"] = candidate

            if cycle["trafficStateId"] is None:
                cycle["trafficStateId"] = simulation.get("trafficStateId")

            if not cycle["trafficConditions"]:
                cycle["trafficConditions"] = conditions_by_state.get(
                    simulation.get("trafficStateId"), []
                )

        for cycle in cycles:
            cycle["candidates"].sort(key=lambda item: item["candidateId"])

    def _load_traffic_conditions(
        self, traffic_state_ids: list[int]
    ) -> dict[int, list[dict[str, Any]]]:
        if not traffic_state_ids:
            return {}

        rows = (
            self.supabase.table("trafficApproachStates")
            .select(
                "trafficStateId, approach, volume, queueLengthVeh, "
                "queueLengthMEst, densityIndex"
            )
            .in_("trafficStateId", traffic_state_ids)
            .execute()
        ).data or []

        grouped: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["trafficStateId"], []).append(
                {
                    "approach": row.get("approach"),
                    "volume": row.get("volume"),
                    "queueLengthVeh": row.get("queueLengthVeh"),
                    "queueLengthMEst": row.get("queueLengthMEst"),
                    "densityIndex": row.get("densityIndex"),
                }
            )
        return grouped


history_service = HistoryService()

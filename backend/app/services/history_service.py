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

BASELINE_CANDIDATE_ID = "baseline"


def _compute_before_after(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Bandingkan kandidat `baseline` (before) vs pemenang (after).

    None kalau datanya tidak lengkap untuk dibandingkan -- mis. siklus lama
    dari sebelum fitur Scenario Generator tersambung ke riwayat, yang tidak
    punya baris `simulations` sama sekali.
    """
    baseline = next(
        (c for c in candidates if c["candidateId"] == BASELINE_CANDIDATE_ID), None
    )
    winner = next((c for c in candidates if c["isWinner"]), None)
    if baseline is None or winner is None:
        return None

    metrics = []
    for field, label, unit, lower_is_better in _BEFORE_AFTER_METRICS:
        before = baseline.get(field)
        after = winner.get(field)
        if before is None or after is None:
            continue

        change_percent = (
            round((after - before) / before * 100, 1) if before != 0 else None
        )
        membaik = (
            None
            if change_percent is None or change_percent == 0
            else (change_percent < 0) == lower_is_better
        )

        metrics.append(
            {
                "metric": field,
                "label": label,
                "unit": unit,
                "before": before,
                "after": after,
                "changePercent": change_percent,
                "improved": membaik,
            }
        )

    return {
        "baselineCandidateId": baseline["candidateId"],
        "winnerCandidateId": winner["candidateId"],
        # False kalau sistem menyimpulkan pengaturan dasar sudah paling
        # baik untuk kondisi ini -- itu keputusan yang SAH, bukan sistem
        # gagal berpikir. Ditandai eksplisit supaya tidak disalahartikan.
        "changed": winner["candidateId"] != baseline["candidateId"],
        "metrics": metrics,
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
            }

        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        # PostgREST memotong di 1000 baris secara DIAM-DIAM tanpa .range().
        # Di sini rentangnya dihitung eksplisit dari nomor halaman supaya
        # tidak pernah bergantung pada batas bawaan itu.
        offset = (page - 1) * page_size * PHASES_PER_CYCLE
        limit = page_size * PHASES_PER_CYCLE

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

        return {
            "page": page,
            "pageSize": page_size,
            "totalCycles": math.ceil(total_rows / PHASES_PER_CYCLE),
            "items": cycles,
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
        metrics = (
            self.supabase.table("simulationMetrics")
            .select("*")
            .in_("simulationId", simulation_ids)
            .execute()
        ).data or []

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

            candidate = {
                "candidateId": str(simulation.get("simulationName", "")).split(" @ ")[0],
                "isWinner": simulation.get("status") == "winner",
                "avgDelaySeconds": avg_delay,
                "avgQueueLengthM": simulation_metrics.get("avgQueueLengthM"),
                "throughputVeh": simulation_metrics.get("throughputVeh"),
                "los": _calculate_los(avg_delay),
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

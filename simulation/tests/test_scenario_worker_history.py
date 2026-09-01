"""Test untuk write_history() -- penyimpanan riwayat keputusan worker.

Kenapa dites terpisah dan agak rinci: fungsi ini MENULIS KE DATABASE PRODUKSI
tiap 60 detik. Dua sifat yang wajib dijaga:

  1. Kegagalannya tidak boleh mematikan worker (tugas utama worker adalah
     mengisi cache dashboard; riwayat cuma pelengkap).
  2. Sumber keputusan dicatat APA ADANYA -- termasuk saat jatuh ke rule-based.
     Riwayat yang menyembunyikan fallback justru berbahaya karena alurnya
     terlihat mulus padahal kotak 7/8/9 sempat terlewat.
"""

import sys
from pathlib import Path

SIMULATION_ROOT = Path(__file__).resolve().parents[1]
if str(SIMULATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMULATION_ROOT))

import scenario_worker as worker  # noqa: E402


class _Result:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Meniru rantai .select().eq().limit().execute() / .insert().execute()."""

    def __init__(self, table_name, recorder, *, insert_id=1):
        self._table = table_name
        self._recorder = recorder
        self._insert_id = insert_id
        self._rows = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def insert(self, rows):
        self._rows = rows
        self._recorder.setdefault(self._table, []).extend(
            rows if isinstance(rows, list) else [rows]
        )
        return self

    def execute(self):
        if self._rows is not None:
            return _Result([{"id": self._insert_id}])
        # jalur select intersections
        return _Result([{"id": 1}])


class _FakeSupabase:
    def __init__(self):
        self.written = {}
        self._counter = 0

    def table(self, name):
        self._counter += 1
        return _FakeQuery(name, self.written, insert_id=self._counter)


class _FakeState:
    trafficStateId = 13784


def _payload(source="scenario-generator"):
    return {
        "intersectionId": "simpang4-pingit",
        "updatedAt": "2026-09-01T10:00:00+00:00",
        "candidateId": "balanced",
        "avgDelaySeconds": 15.7,
        "avgQueueLengthM": 56.0,
        "los": "B",
        "recommendation": {
            "source": source,
            "currentGreenSeconds": 15,
            "expectedDelayReductionPercent": 3.5,
            "confidence": 0.8,
            "cyclePlan": {
                "phases": [
                    {"approach": "north", "greenSeconds": 26},
                    {"approach": "east", "greenSeconds": 17},
                    {"approach": "south", "greenSeconds": 60},
                    {"approach": "west", "greenSeconds": 44},
                ]
            },
        },
        "candidates": [
            {
                "candidateId": "baseline",
                "avgDelaySeconds": 18.2,
                "avgQueueLengthM": 70.0,
                "throughputVeh": 6,
            },
            {
                "candidateId": "balanced",
                "avgDelaySeconds": 15.7,
                "avgQueueLengthM": 56.0,
                "throughputVeh": 8,
            },
        ],
    }


def _reset_cache():
    worker._intersection_row_id = None


def test_menyimpan_satu_baris_per_lengan_dengan_nama_inggris():
    _reset_cache()
    supabase = _FakeSupabase()

    worker.write_history(supabase, _payload(), _FakeState())

    rekomendasi = supabase.written["recommendations"]
    assert len(rekomendasi) == 4

    # Nama lengan mengikuti kontrak data-contract.md (Inggris), BUKAN
    # bahasa Indonesia -- penerjemahan dilakukan di lapisan tampilan.
    assert {row["recommendedPhase"] for row in rekomendasi} == {
        "north",
        "east",
        "south",
        "west",
    }

    selatan = next(r for r in rekomendasi if r["recommendedPhase"] == "south")
    assert selatan["recommendedGreenSeconds"] == 60
    assert selatan["currentGreenSeconds"] == 15


def test_fallback_dicatat_apa_adanya():
    # Saat SUMO gagal / cache basi, engine melaporkan sumber lain. Riwayat
    # harus jujur mencatatnya, bukan menyamarkannya jadi scenario-generator.
    _reset_cache()
    supabase = _FakeSupabase()

    worker.write_history(
        supabase, _payload(source="rule-based+forecast"), _FakeState()
    )

    rekomendasi = supabase.written["recommendations"]
    assert all(row["source"] == "rule-based+forecast" for row in rekomendasi)


def test_semua_kandidat_disimpan_dan_pemenang_ditandai():
    _reset_cache()
    supabase = _FakeSupabase()

    worker.write_history(supabase, _payload(), _FakeState())

    simulasi = supabase.written["simulations"]
    assert len(simulasi) == 2  # baseline + balanced

    status = {row["simulationName"].split(" @ ")[0]: row["status"] for row in simulasi}
    assert status["balanced"] == "winner"
    assert status["baseline"] == "completed"

    # Kondisi lalu lintas pemicu disambungkan lewat relasi, bukan disalin.
    assert all(row["trafficStateId"] == 13784 for row in simulasi)

    # LOS sengaja tidak disimpan -- murni turunan dari avgDelaySeconds.
    metrik = {row["metricName"] for row in supabase.written["simulationMetrics"]}
    assert metrik == {"avgDelaySeconds", "avgQueueLengthM", "throughputVeh"}


def test_kegagalan_database_tidak_mematikan_worker():
    """Sifat paling penting: riwayat gagal != worker mati."""
    _reset_cache()

    class _SupabaseRusak:
        def table(self, _name):
            raise RuntimeError("koneksi database putus")

    # Tidak boleh melempar exception ke pemanggil.
    worker.write_history(_SupabaseRusak(), _payload(), _FakeState())


def test_cycle_plan_kosong_dilewati_dengan_aman():
    _reset_cache()
    supabase = _FakeSupabase()

    payload = _payload()
    payload["recommendation"]["cyclePlan"] = {"phases": []}

    worker.write_history(supabase, payload, _FakeState())

    assert "recommendations" not in supabase.written

"""Test HistoryService — sumber data halaman Riwayat.

Dua hal yang paling penting dijaga di sini:

  1. **Paginasi dihitung eksplisit.** PostgREST memotong hasil di 1000 baris
     secara diam-diam tanpa `.range()`. Repo ini sudah pernah kena (commit
     a14d302), jadi rentangnya diuji sebagai kontrak, bukan detail internal.
  2. **LOS dihitung ulang, bukan disimpan.** Nilainya turunan dari delay;
     kalau ikut disimpan bisa muncul dua angka yang saling bertentangan.
"""

from app.services.history_service import (
    HistoryService,
    _calculate_los,
    _compute_before_after,
)


class _Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, table_name, store, calls):
        self._table = table_name
        self._store = store
        self._calls = calls

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args):
        return self

    def in_(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def range(self, start, end):
        # Dicatat supaya test bisa memverifikasi paginasinya benar-benar
        # dikirim ke PostgREST, bukan mengandalkan batas bawaan.
        self._calls.append((self._table, start, end))
        return self

    def execute(self):
        rows = self._store.get(self._table, [])
        return _Result(rows, count=len(rows))


class _FakeSupabase:
    def __init__(self, store):
        self.store = store
        self.range_calls: list[tuple[str, int, int]] = []

    def table(self, name):
        return _FakeQuery(name, self.store, self.range_calls)


def _service(store):
    supabase = _FakeSupabase(store)
    return HistoryService(supabase=supabase), supabase


def test_los_dihitung_dari_delay_bukan_disimpan():
    assert _calculate_los(8.7) == "A"
    assert _calculate_los(15.0) == "B"
    assert _calculate_los(90.0) == "F"
    assert _calculate_los(None) is None


def test_paginasi_dikirim_eksplisit_ke_postgrest():
    service, supabase = _service({"intersections": [{"id": 1}]})

    service.list_cycles(intersection_id="simpang4-pingit", page=3, page_size=20)

    rentang = [call for call in supabase.range_calls if call[0] == "recommendations"]
    assert rentang, "range() wajib dipanggil -- tanpa itu PostgREST memotong diam-diam"

    _, start, end = rentang[0]
    # Halaman 3, 20 siklus/halaman, 4 baris per siklus -> baris 160..239
    assert (start, end) == (160, 239)


def test_intersection_tidak_dikenal_mengembalikan_kosong():
    service, _ = _service({"intersections": []})

    hasil = service.list_cycles(intersection_id="tidak-ada")

    assert hasil["items"] == []
    assert hasil["totalCycles"] == 0


def test_baris_dikelompokkan_jadi_siklus_per_timestamp():
    store = {
        "intersections": [{"id": 1}],
        "recommendations": [
            {
                "id": 1,
                "timestamp": "2026-09-01T10:00:00+00:00",
                "recommendedPhase": "north",
                "recommendedGreenSeconds": 26,
                "currentGreenSeconds": 15,
                "confidence": 0.8,
                "expectedDelayReductionPercent": 3.5,
                "source": "scenario-generator",
            },
            {
                "id": 2,
                "timestamp": "2026-09-01T10:00:00+00:00",
                "recommendedPhase": "south",
                "recommendedGreenSeconds": 60,
                "currentGreenSeconds": 15,
                "confidence": 0.8,
                "expectedDelayReductionPercent": 3.5,
                "source": "scenario-generator",
            },
            {
                "id": 3,
                "timestamp": "2026-09-01T09:59:00+00:00",
                "recommendedPhase": "north",
                "recommendedGreenSeconds": 24,
                "currentGreenSeconds": 15,
                "confidence": 0.7,
                "expectedDelayReductionPercent": 2.0,
                "source": "rule-based+forecast",
            },
        ],
    }
    service, _ = _service(store)

    hasil = service.list_cycles(intersection_id="simpang4-pingit")

    assert len(hasil["items"]) == 2

    siklus_terbaru = hasil["items"][0]
    assert siklus_terbaru["timestamp"] == "2026-09-01T10:00:00+00:00"
    assert len(siklus_terbaru["phases"]) == 2
    assert {p["approach"] for p in siklus_terbaru["phases"]} == {"north", "south"}

    # Sumber dilaporkan apa adanya, termasuk saat fallback.
    assert hasil["items"][1]["source"] == "rule-based+forecast"


def test_kandidat_dan_kondisi_pemicu_ikut_terlampir():
    store = {
        "intersections": [{"id": 1}],
        "recommendations": [
            {
                "id": 10,
                "timestamp": "2026-09-01T10:00:00+00:00",
                "recommendedPhase": "north",
                "recommendedGreenSeconds": 26,
                "currentGreenSeconds": 15,
                "confidence": 0.8,
                "expectedDelayReductionPercent": 3.5,
                "source": "scenario-generator",
            }
        ],
        "simulations": [
            {
                "id": 100,
                "recommendationId": 10,
                "trafficStateId": 13784,
                "simulationName": "balanced @ 2026-09-01T10:00:00+00:00",
                "status": "winner",
            },
            {
                "id": 101,
                "recommendationId": 10,
                "trafficStateId": 13784,
                "simulationName": "baseline @ 2026-09-01T10:00:00+00:00",
                "status": "completed",
            },
        ],
        "simulationMetrics": [
            {"simulationId": 100, "metricName": "avgDelaySeconds", "metricValue": 15.7},
            {"simulationId": 100, "metricName": "avgQueueLengthM", "metricValue": 56.0},
            {"simulationId": 101, "metricName": "avgDelaySeconds", "metricValue": 18.2},
        ],
        "trafficApproachStates": [
            {
                "trafficStateId": 13784,
                "approach": "south",
                "volume": 12,
                "queueLengthVeh": 3,
                "queueLengthMEst": 21.0,
                "densityIndex": 6.1,
            }
        ],
    }
    service, _ = _service(store)

    siklus = service.list_cycles(intersection_id="simpang4-pingit")["items"][0]

    assert len(siklus["candidates"]) == 2
    assert siklus["winner"]["candidateId"] == "balanced"
    # LOS diturunkan dari delay, tidak diambil dari database.
    assert siklus["winner"]["los"] == "B"

    kalah = next(c for c in siklus["candidates"] if c["candidateId"] == "baseline")
    assert kalah["isWinner"] is False
    assert kalah["avgDelaySeconds"] == 18.2

    # Kondisi pemicu tersambung lewat trafficStateId, bukan disalin.
    assert siklus["trafficConditions"][0]["approach"] == "south"
    assert siklus["trafficConditions"][0]["volume"] == 12

    # Identitas kondisi ikut dilaporkan supaya UI bisa membedakan
    # "kondisi baru" dari "kondisi sama yang dievaluasi ulang".
    assert siklus["trafficStateId"] == 13784

    # beforeAfter dihitung otomatis oleh list_cycles(), bukan cuma dites
    # terpisah lewat _compute_before_after() -- membuktikan keduanya
    # benar-benar tersambung.
    assert siklus["beforeAfter"]["winnerCandidateId"] == "balanced"
    assert siklus["beforeAfter"]["baselineCandidateId"] == "baseline"


def test_before_after_membandingkan_baseline_vs_pemenang():
    kandidat = [
        {
            "candidateId": "baseline",
            "isWinner": False,
            "avgDelaySeconds": 18.2,
            "avgQueueLengthM": 70.0,
            "throughputVeh": 6,
            "los": "B",
        },
        {
            "candidateId": "balanced",
            "isWinner": True,
            "avgDelaySeconds": 15.7,
            "avgQueueLengthM": 56.0,
            "throughputVeh": 8,
            "los": "B",
        },
    ]

    hasil = _compute_before_after(kandidat)

    assert hasil["baselineCandidateId"] == "baseline"
    assert hasil["winnerCandidateId"] == "balanced"
    assert hasil["changed"] is True

    delay = next(m for m in hasil["metrics"] if m["metric"] == "avgDelaySeconds")
    assert delay["before"] == 18.2
    assert delay["after"] == 15.7
    assert delay["changePercent"] < 0  # turun
    assert delay["improved"] is True  # delay turun = membaik

    throughput = next(m for m in hasil["metrics"] if m["metric"] == "throughputVeh")
    assert throughput["changePercent"] > 0  # naik
    assert throughput["improved"] is True  # throughput naik = membaik


def test_before_after_saat_baseline_menang_tidak_dianggap_gagal():
    # Sistem menyimpulkan pengaturan dasar sudah paling baik -- ini
    # keputusan SAH, bukan kegagalan sistem berpikir.
    kandidat = [
        {
            "candidateId": "baseline",
            "isWinner": True,
            "avgDelaySeconds": 14.46,
            "avgQueueLengthM": 56.0,
            "throughputVeh": 10,
            "los": "B",
        },
        {
            "candidateId": "balanced",
            "isWinner": False,
            "avgDelaySeconds": 13.42,
            "avgQueueLengthM": 70.0,
            "throughputVeh": 10,
            "los": "B",
        },
    ]

    hasil = _compute_before_after(kandidat)

    assert hasil["changed"] is False
    assert hasil["baselineCandidateId"] == hasil["winnerCandidateId"] == "baseline"
    for metrik in hasil["metrics"]:
        assert metrik["changePercent"] == 0
        assert metrik["improved"] is None  # bukan membaik, bukan memburuk -- tetap


def test_before_after_tanpa_kandidat_baseline_mengembalikan_none():
    # Siklus lama (sebelum riwayat tersambung ke Scenario Generator) tidak
    # punya baris simulations sama sekali -- harus gagal dengan aman, bukan
    # melempar KeyError.
    assert _compute_before_after([]) is None
    assert (
        _compute_before_after(
            [
                {
                    "candidateId": "aggressive",
                    "isWinner": True,
                    "avgDelaySeconds": 14.0,
                    "avgQueueLengthM": 50.0,
                    "throughputVeh": 9,
                    "los": "B",
                }
            ]
        )
        is None
    )

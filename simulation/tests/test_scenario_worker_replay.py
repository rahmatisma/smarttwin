"""Test untuk ReplaySource -- mode --replay scenario_worker.py.

Kenapa ini perlu ada: tanpa mode replay, worker selalu mengambil kondisi
TERBARU di database. Kalau CV tidak sedang berjalan, "terbaru" itu tidak
pernah berganti -- ditemukan lewat riwayat asli yang menunjukkan 16 siklus
berturut-turut mengevaluasi trafficStateId yang SAMA. ReplaySource memutar
maju melalui data historis supaya tiap siklus benar-benar berbeda.

Dua sifat yang dijaga di sini:
  1. Posisi maju dengan step yang diminta, lalu MELINGKAR (modulo) saat
     mencapai akhir daftar -- replay tidak boleh berhenti.
  2. Urutannya deterministik: dua ReplaySource baru dengan builder yang
     sama menghasilkan urutan identik (reproducible untuk latihan).
  3. Data yang ditambahkan ketika worker hidup langsung masuk ke urutan,
     tanpa harus me-restart backend/worker.
"""

import sys
from pathlib import Path

SIMULATION_ROOT = Path(__file__).resolve().parents[1]
if str(SIMULATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMULATION_ROOT))

from scenario_worker import ReplaySource  # noqa: E402


class _Result:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._eq_id = None

    def select(self, *_args):
        return self

    def eq(self, field, value):
        if field == "id":
            self._eq_id = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        if self._eq_id is not None:
            return _Result([r for r in self._rows if r["id"] == self._eq_id])
        return _Result(self._rows)


class _FakeSupabase:
    def __init__(self, traffic_state_rows):
        self._traffic_state_rows = traffic_state_rows

    def table(self, name):
        if name == "trafficStates":
            return _FakeQuery(self._traffic_state_rows)
        raise AssertionError(f"Tabel tak terduga: {name}")


class _FakeBuilder:
    """Cuma mengimplementasikan yang dipanggil ReplaySource -- bukan
    TrafficStateBuilder asli, supaya test tidak perlu meniru seluruh
    rantai intersections/approaches/lanes."""

    def __init__(self, traffic_state_rows):
        self.supabase = _FakeSupabase(traffic_state_rows)
        self.build_state_calls = []

    def build_relation_maps(self):
        return (
            {1: {"id": 1, "intersectionId": "simpang4-pingit"}},
            {},
            {},
        )

    def get_lane_metrics(self, traffic_state_ids):
        return [{"trafficStateId": tid} for tid in traffic_state_ids]

    def build_state(self, row, lane_metrics, intersection_map, approach_map, lane_map):
        self.build_state_calls.append(row["id"])
        return _FakeBuiltState(traffic_state_id=row["id"])


class _FakeBuiltState:
    def __init__(self, traffic_state_id):
        self.trafficStateId = traffic_state_id


def _lima_baris_trafficstates():
    return [
        {"id": 100 + i, "intersectionId": 1, "windowStart": f"2026-08-15T16:{30+i}:00+00:00"}
        for i in range(5)
    ]


def test_maju_sesuai_step_yang_diminta():
    builder = _FakeBuilder(_lima_baris_trafficstates())
    replay = ReplaySource(builder, "simpang4-pingit", step=2)

    _, posisi1, total = replay.next()
    _, posisi2, _ = replay.next()
    _, posisi3, _ = replay.next()

    assert total == 5
    assert (posisi1, posisi2, posisi3) == (1, 3, 5)


def test_melingkar_saat_mencapai_akhir_daftar():
    builder = _FakeBuilder(_lima_baris_trafficstates())
    replay = ReplaySource(builder, "simpang4-pingit", step=2)

    posisi_urut = [replay.next()[1] for _ in range(4)]

    # 5 baris, step 2: 1, 3, 5, lalu melingkar ke 2 (bukan berhenti/error).
    assert posisi_urut == [1, 3, 5, 2]


def test_urutan_deterministik_antar_instance():
    baris = _lima_baris_trafficstates()
    builder_a = _FakeBuilder(baris)
    builder_b = _FakeBuilder(baris)

    replay_a = ReplaySource(builder_a, "simpang4-pingit", step=2)
    replay_b = ReplaySource(builder_b, "simpang4-pingit", step=2)

    urutan_a = [replay_a.next()[0].trafficStateId for _ in range(6)]
    urutan_b = [replay_b.next()[0].trafficStateId for _ in range(6)]

    assert urutan_a == urutan_b


def test_intersection_tidak_dikenal_melempar_error_jelas():
    builder = _FakeBuilder(_lima_baris_trafficstates())
    replay = ReplaySource(builder, "simpang-lain-yang-tidak-ada", step=1)

    try:
        replay.next()
        assert False, "Harus melempar RuntimeError"
    except RuntimeError as exc:
        assert "tidak ditemukan" in str(exc)


def test_step_nol_atau_negatif_dianggap_minimal_satu():
    # Step 0 akan membuat replay tidak pernah maju -- dipaksa minimal 1
    # supaya tidak diam-diam terjebak di kondisi yang sama selamanya.
    builder = _FakeBuilder(_lima_baris_trafficstates())
    replay = ReplaySource(builder, "simpang4-pingit", step=0)

    _, posisi1, _ = replay.next()
    _, posisi2, _ = replay.next()

    assert posisi2 != posisi1


def test_data_baru_diikuti_sebelum_replay_kembali_ke_awal():
    rows = _lima_baris_trafficstates()
    builder = _FakeBuilder(rows)
    replay = ReplaySource(builder, "simpang4-pingit", step=1)

    ids_awal = [replay.next()[0].trafficStateId for _ in range(5)]
    rows.extend([
        {"id": 105, "intersectionId": 1, "windowStart": "2026-08-15T16:35:00+00:00"},
        {"id": 106, "intersectionId": 1, "windowStart": "2026-08-15T16:36:00+00:00"},
    ])
    ids_lanjutan = [replay.next()[0].trafficStateId for _ in range(3)]

    assert ids_awal == [100, 101, 102, 103, 104]
    assert ids_lanjutan == [105, 106, 100]

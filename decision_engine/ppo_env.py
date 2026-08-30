from __future__ import annotations

import csv
import os
import random
import shutil
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .ppo_engine import GREEN_OPTIONS
from .ppo_features import build_ppo_observation
from .rule_based_engine import FIXED_CYCLE_ORDER, RuleBasedEngine, YELLOW_SECONDS
from app.schemas.traffic import ApproachState, TrafficState

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "simulation/network/simpang4_pingit_live.sumocfg"
DEFAULT_DATA = ROOT / "cv/output/crossing_simpang.csv"
DEFAULT_DENSITY_DATA = ROOT / "cv/output/snapshot_zona.csv"
FEATURE_WINDOW_SECONDS = 5
METERS_PER_QUEUED_VEHICLE = 7.0

CROSS_LABEL_MAP = {
    "selatan": "south",
    "MAGELANG": "north",
    "DIPONEGORO": "east",
    "barat": "west",
}
DENSITY_APPROACH_MAP = {
    "selatan": "south",
    "barat": "west",
    "timur": "east",
    "simpang_tengah": "north",
}

EDGE_HULU = {"north": "484349908#0", "south": "134603786#0", "east": "153857851#2", "west": "590064461#0"}
EDGE_MASUK = {"north": "484349908#2", "south": "134603786#2", "east": "153857851#4", "west": "590064461#2"}
EDGE_KELUAR = {"north": "201299423#0", "south": "153857907#0", "east": "590386082#0", "west": "25006154#0"}
TURN_DESTINATIONS = {
    "north": ("south", "east", "west"), "south": ("north", "west", "east"),
    "east": ("west", "north", "south"), "west": ("east", "south", "north"),
}
GREEN_STATE = {
    "south": "GGGggrrrrrrrrrrrrrrr", "east": "rrrrrGGGggrrrrrrrrrr",
    "north": "rrrrrrrrrrGGGggrrrrr", "west": "rrrrrrrrrrrrrrrGGGgg",
}
YELLOW_STATE = {
    "south": "yyyyyrrrrrrrrrrrrrrr", "east": "rrrrryyyyyrrrrrrrrrr",
    "north": "rrrrrrrrrryyyyyrrrrr", "west": "rrrrrrrrrrrrrrryyyyy",
}

# Reward v2: throughput menjadi tujuan utama. Bobot ketiga komponen berjumlah
# 1,0 agar skala reward tetap mudah dibaca dan dibandingkan antar-training.
THROUGHPUT_REWARD_WEIGHT = 0.45
QUEUE_REWARD_WEIGHT = 0.35
WAIT_REWARD_WEIGHT = 0.20

# Ambang saturasi. SEMUANYA ditetapkan dari PENGUKURAN, bukan tebakan --
# lihat docs/STATUS-DAN-SISA-KERJA.md item P-1.
#
# Riwayat: nilai throughput lama 15,0 membuat reward buta (saturasi 81-97%
# langkah). Dinaikkan ke 30,0 -- tapi itu diukur saat jendela keputusan masih
# 30 detik. Setelah Bug A diperbaiki (jendela = satu rotasi penuh, ~76-256
# detik), kedatangan per langkah melonjak ke 96-170 (rata-rata 154), sehingga
# ambang 30 saturasi 10/10 langkah. Diukur ulang 29 Agustus, ambang jumlah
# mentah dinaikkan ke 200.
#
# BUG E (diperbaiki 30 Agustus): ambang berbasis JUMLAH MENTAH itu sendiri
# cacat. `arrived` diakumulasi sepanjang jendela yang panjangnya DIPILIH AGENT
# (76-256 detik), sedangkan antrean/tunggu cuma snapshot di akhir dan tidak
# ikut memanjang. Akibatnya memperpanjang siklus menaikkan reward tanpa
# memperbaiki apa pun -- terukur: korelasi durasi rotasi vs reward +0,978,
# sementara throughput PER DETIK praktis datar (0,615/0,671/0,654).
#
# Sekarang throughput dinilai sebagai LAJU (kendaraan/detik), bukan jumlah.
# Diukur 30 Agustus pada 5 profil permintaan x 3 panjang rotasi x 2 ulangan:
#   laju: min 0,158 | p50 0,475 | p95 0,669 | maks 0,679 | rata-rata 0,424
#   korelasi durasi vs LAJU          : +0,050  <- bias panjang siklus hilang
#   korelasi durasi vs jumlah mentah : +0,675  <- inilah bias yang diperbaiki
# Ambang 1,0 kend/detik: 0% saturasi, rata-rata ternormalisasi 0,424, maksimum
# 0,679 -- masih menyisakan ~32% kepala ruang di atas apa pun yang pernah
# teramati, jadi reward tetap punya gradien kalau throughput membaik.
#
# ⚠️ UKUR ULANG setelah Bug H & I diperbaiki: cap injeksi dinaikkan dan profil
# permintaan tidak lagi dibekukan, jadi laju yang terjadi akan berubah.
THROUGHPUT_SATURATION_RATE = 1.0
QUEUE_SATURATION_VEH = 100.0

# BUG O (ditemukan 30 Agustus): `jumlah_crossing` di crossing_simpang.csv
# menghitung kendaraan yang melintasi garis ke ARAH MANA PUN -- lihat
# cv/vehicle_counter_pingit.py: `if sisi_lama * sisi_baru < 0`, tanpa filter
# arah (perilaku ini disengaja untuk CV dan didokumentasikan di
# docs/hasil-validasi-akurasi-cv.md).
#
# Masalahnya: jalan pendekat Simpang Pingit DUA ARAH. Diverifikasi geometris
# pada jaringan SUMO -- ruas masuk dan ruas keluar north berjarak 29,1 m dengan
# arah berlawanan 180 derajat (east: 28,4 m / 179 derajat), yaitu jalan yang
# sama. Jadi satu garis hitung memotong DUA arus: kendaraan yang MASUK ke
# simpang dan yang KELUAR dari simpang.
#
# Memakainya mentah-mentah sebagai permintaan pendekat menggandakan angkanya.
# Terukur akibatnya: permintaan 1,66 kend/detik vs kapasitas jaringan ~1,00 --
# 92% episode training macet total, padahal simpang aslinya lancar (antrean
# nyata rata-rata cuma 2,7 kendaraan).
#
# Dibagi 2 sebagai taksiran terbaik yang tersedia (mengasumsikan arus masuk dan
# keluar kira-kira seimbang). Setelah dibagi: 90,5/menit -> 45/menit = 0,75
# kend/detik, yaitu DI BAWAH kapasitas -- konsisten dengan antrean pendek yang
# teramati di lapangan.
#
# ⚠️ Ini TAKSIRAN, bukan pengukuran. Perbaikan yang benar adalah memfilter arah
# di penghitung CV (`hitung_crossing()`), sehingga `volume` berarti arus masuk
# saja. Itu mengubah keluaran CV produksi, jadi belum dikerjakan di sini.
BAGI_ARUS_DUA_ARAH = 2.0


def _floor_five_seconds(timestamp: str) -> str:
    parsed = datetime.fromisoformat(str(timestamp).strip().replace("Z", "+00:00"))
    return parsed.replace(second=(parsed.second // 5) * 5, microsecond=0).isoformat()


def load_demand_profiles(
    path: str | Path = DEFAULT_DATA,
    density_path: str | Path = DEFAULT_DENSITY_DATA,
) -> list[dict[str, float]]:
    """Bangun demand veh/min dari pasangan CSV yang dipakai ingest produksi.

    Flow hanya berasal dari `crossing_simpang.csv`. `snapshot_zona.csv`
    menentukan window/lengan yang benar-benar memiliki pengukuran kehadiran;
    kedua populasi sengaja tidak dijumlahkan.
    """
    crossing_source, density_source = Path(path), Path(density_path)
    missing = [str(item) for item in (crossing_source, density_source) if not item.exists()]
    if missing:
        raise FileNotFoundError(
            "Dataset PPO produksi belum tersedia: " + ", ".join(missing)
        )

    measured: dict[str, set[str]] = defaultdict(set)
    with density_source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            approach = DENSITY_APPROACH_MAP.get(str(row.get("lengan", "")))
            timestamp = str(row.get("timestamp", ""))
            if approach and timestamp:
                measured[_floor_five_seconds(timestamp)].add(approach)

    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    with crossing_source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            approach = CROSS_LABEL_MAP.get(str(row.get("label_garis", "")))
            timestamp = str(row.get("timestamp", ""))
            if approach and timestamp:
                grouped[_floor_five_seconds(timestamp)][approach] += max(
                    0.0, float(row.get("jumlah_crossing", 0) or 0)
                )

    timestamps = sorted(set(grouped).intersection(measured))
    profiles = [
        {
            approach: grouped[timestamp].get(approach, 0.0)
            / BAGI_ARUS_DUA_ARAH
            * (60.0 / FEATURE_WINDOW_SECONDS)
            for approach in FIXED_CYCLE_ORDER
        }
        for timestamp in timestamps
        if measured[timestamp]
    ]
    if not profiles:
        raise ValueError("Dataset crossing/snapshot tidak mempunyai window yang dapat dipasangkan")
    return profiles


def resolve_sumo_binary(explicit: str | Path | None = None) -> Path:
    # Sejak backend/simulation/decision_engine digabung jadi satu venv di
    # root repo (30 Agustus 2026), SUMO cuma ada di situ -- bukan lagi
    # simulation/.venv yang sudah dihapus. SUMO_HOME dicek duluan supaya
    # tetap benar kalau seseorang jalankan dari venv non-standar.
    sumo_home = os.environ.get("SUMO_HOME")
    candidates = [
        Path(explicit) if explicit else None,
        Path(found) if (found := shutil.which("sumo")) else None,
        Path(sumo_home) / "bin" / "sumo.exe" if sumo_home else None,
        ROOT / ".venv/Lib/site-packages/sumo/bin/sumo.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError("sumo/sumo.exe tidak ditemukan; lihat README-PPO-UNTUK-TIM.md")


class SmartTwinSumoEnv(gym.Env[np.ndarray, np.ndarray]):
    """Single-intersection Gymnasium environment with the inference 25-feature contract."""

    metadata = {"render_modes": []}

    def __init__(self, *, data_path: str | Path = DEFAULT_DATA,
                 density_data_path: str | Path = DEFAULT_DENSITY_DATA,
                 config_path: str | Path = DEFAULT_CONFIG,
                 sumo_binary: str | Path | None = None, episode_steps: int = 12,
                 decision_seconds: int = 30, split: str = "train") -> None:
        super().__init__()
        self.profiles = load_demand_profiles(data_path, density_data_path)
        cut = max(1, int(len(self.profiles) * 0.8))
        self.profiles = self.profiles[:cut] if split == "train" else self.profiles[cut:]
        if not self.profiles:
            self.profiles = load_demand_profiles(data_path, density_data_path)
        self.config_path = Path(config_path).resolve()
        self.sumo_binary = resolve_sumo_binary(sumo_binary)
        self.episode_steps = int(episode_steps)
        # PERHATIAN: decision_seconds SUDAH TIDAK MENENTUKAN APA-APA sejak
        # Bug A diperbaiki 29 Agustus. Panjang jendela keputusan kini dihitung
        # dari durasi rotasi yang dipilih (_cycle_seconds()), bukan angka
        # tetap. Parameter dipertahankan agar --decision-seconds di
        # train_ppo.py tidak error dan metadata training lama tetap terbaca,
        # tapi mengubahnya TIDAK berpengaruh pada simulasi.
        self.decision_seconds = int(decision_seconds)
        self.observation_space = spaces.Box(0.0, 1.0, shape=(25,), dtype=np.float32)
        # Empat durasi hijau saja (utara, timur, selatan, barat). Urutan rotasi
        # bukan keputusan PPO -- lihat _set_action().
        self.action_space = spaces.MultiDiscrete([len(GREEN_OPTIONS)] * len(FIXED_CYCLE_ORDER))
        self.connection: Any = None
        self.rule_based_engine = RuleBasedEngine()
        self.label = f"smarttwin-ppo-{uuid.uuid4().hex}"
        self.rng = random.Random()
        self.step_count = self.vehicle_counter = 0
        self.profile: dict[str, float] = self.profiles[0]
        self._profile_index = 0
        self._profile_seconds = 0
        self.current_phase = FIXED_CYCLE_ORDER[0]
        self.current_green = 30
        self.current_greens: dict[str, int] = {a: 30 for a in FIXED_CYCLE_ORDER}
        self.recent_crossings = {a: 0 for a in FIXED_CYCLE_ORDER}
        self._arrived_total = 0

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self.close()
        actual_seed = int(seed if seed is not None else self.np_random.integers(1, 2**31 - 1))
        self.rng.seed(actual_seed)
        # Titik MULAI di rekaman; profilnya akan bergerak maju sendiri tiap
        # FEATURE_WINDOW_SECONDS detik simulasi -- lihat _maju_profil().
        self._profile_index = actual_seed % len(self.profiles)
        self._profile_seconds = 0
        self.profile = self.profiles[self._profile_index]
        import traci
        traci.start([str(self.sumo_binary), "-c", str(self.config_path), "--start", "--seed", str(actual_seed),
                     "--no-step-log", "true", "--xml-validation", "never"], label=self.label)
        self.connection = traci.getConnection(self.label)
        self._add_vehicle_types()
        self.step_count = self.vehicle_counter = 0
        self.current_phase, self.current_green = FIXED_CYCLE_ORDER[0], 30
        self.current_greens = {a: 30 for a in FIXED_CYCLE_ORDER}
        self.recent_crossings = {a: 0 for a in FIXED_CYCLE_ORDER}
        self._arrived_total = 0
        for _ in range(20):
            self._inject_one_second()
            self.connection.simulationStep()
        # Observasi awal memakai crossing SUNGGUHAN, bukan taksiran dari
        # profil permintaan (dulu: profile * 5/60). Taksiran itu semantik lama
        # "volume = permintaan" yang sudah diperbaiki -- memakainya di sini
        # akan membuat observasi pertama tiap episode bersatuan berbeda dari
        # observasi selanjutnya.
        self.recent_crossings = self._hitung_crossing(FEATURE_WINDOW_SECONDS)
        return self._observation(), self._metrics()

    def _add_vehicle_types(self) -> None:
        existing = set(self.connection.vehicletype.getIDList())
        if "smart_car" not in existing:
            self.connection.vehicletype.copy("DEFAULT_VEHTYPE", "smart_car")

    def _maju_profil(self) -> None:
        """Majukan profil permintaan mengikuti rekaman aslinya.

        BUG I (diperbaiki 30 Agustus): `self.profile` dulu ditetapkan SEKALI di
        reset() lalu dibekukan sepanjang episode. Padahal satu profil berasal
        dari jendela 5 DETIK data CV, sementara satu episode = 12 langkah x
        76-256 detik = 15-50 MENIT simulasi. Cuplikan 5 detik direntangkan jadi
        kondisi tetap selama setengah jam.

        Akibatnya terukur parah: dibandingkan kapasitas simpang yang terukur
        (0,68 kend/detik), 92,1% episode training berada DI ATAS kapasitas dan
        71,9% di atas 2x kapasitas. Dalam kondisi macet total, pengaturan lampu
        seperti apa pun tidak berpengaruh -- agent tidak punya apa pun untuk
        dipelajari. Itu menjelaskan kebijakan v4 yang memilih aksi sama 54%
        waktu dan reward yang cepat mendatar.

        Sekarang profil maju satu langkah tiap FEATURE_WINDOW_SECONDS detik
        simulasi, jadi permintaan bergerak persis seperti rekaman CV aslinya --
        ramai dan sepi bergantian sebagaimana kenyataannya.
        """
        self._profile_seconds += 1
        if self._profile_seconds >= FEATURE_WINDOW_SECONDS:
            self._profile_seconds = 0
            self._profile_index = (self._profile_index + 1) % len(self.profiles)
            self.profile = self.profiles[self._profile_index]

    def _inject_one_second(self) -> None:
        self._maju_profil()
        for approach in FIXED_CYCLE_ORDER:
            if self.rng.random() >= min(0.8, self.profile[approach] / 60.0):
                continue
            destination = self.rng.choices(TURN_DESTINATIONS[approach], weights=(0.50, 0.25, 0.25), k=1)[0]
            route_id = f"ppo_route_{self.vehicle_counter}"
            vehicle_id = f"ppo_vehicle_{self.vehicle_counter}"
            self.vehicle_counter += 1
            try:
                self.connection.route.add(route_id, [EDGE_HULU[approach], EDGE_MASUK[approach], EDGE_KELUAR[destination]])
                self.connection.vehicle.add(vehicle_id, route_id, typeID="smart_car", depart="now")
                # recent_crossings TIDAK dinaikkan di sini -- lihat
                # _tally_crossings(). Memunculkan kendaraan itu PERMINTAAN,
                # bukan aliran yang terlayani.
            except Exception:
                pass

    def _set_action(self, action: np.ndarray) -> None:
        """Pasang program TLS dari 4 durasi hijau -- PERSIS seperti produksi.

        Action HANYA berisi durasi hijau per lengan; urutan rotasi sudah
        ditetapkan FIXED_CYCLE_ORDER (utara-timur-selatan-barat) dan tidak
        boleh diputuskan PPO. Sebelum 29 Agustus action[0] memilih fase awal
        lalu dipasang lewat setPhase(selected*2) -- itu tuas kendali yang
        TIDAK ADA di produksi (sumo_controller.apply_cycle_plan dan
        scenario_generator sama-sama memakai setPhase(tls_id, 0) tetap).
        Ketidakcocokan itu membuat baseline dihukum penalti starvation atas
        perilaku yang produksi tidak pernah lakukan, dan menyumbang 80,5%
        keunggulan reward PPO. Lihat docs/STATUS-DAN-SISA-KERJA.md item P-1
        Temuan D.
        """
        greens = {a: GREEN_OPTIONS[int(action[i])] for i, a in enumerate(FIXED_CYCLE_ORDER)}
        phases = []
        for approach in FIXED_CYCLE_ORDER:
            phases.extend([self.connection.trafficlight.Phase(greens[approach], GREEN_STATE[approach]),
                           self.connection.trafficlight.Phase(YELLOW_SECONDS, YELLOW_STATE[approach])])
        tls_id = self.connection.trafficlight.getIDList()[0]
        logic = self.connection.trafficlight.Logic("smarttwin-ppo", 0, 0, phases=phases)
        self.connection.trafficlight.setProgramLogic(tls_id, logic)
        self.connection.trafficlight.setProgram(tls_id, logic.programID)
        self.connection.trafficlight.setPhase(tls_id, 0)
        self.current_greens = greens

    def _cycle_seconds(self) -> int:
        """Durasi satu rotasi penuh: 4 hijau yang dipilih + 4 kuning."""
        return sum(self.current_greens.values()) + YELLOW_SECONDS * len(FIXED_CYCLE_ORDER)

    def _vehicles_on_entry(self) -> dict[str, set]:
        """Kendaraan yang sedang berada di ruas masuk tiap lengan."""
        return {
            approach: set(self.connection.edge.getLastStepVehicleIDs(EDGE_MASUK[approach]))
            for approach in FIXED_CYCLE_ORDER
        }

    def _hitung_crossing(self, jendela_detik: int) -> dict[str, int]:
        """Jalankan simulasi `jendela_detik` sambil mencacah kendaraan yang
        BENAR-BENAR melewati garis henti tiap lengan.

        BUG D (diperbaiki 29 Agustus): dulu `recent_crossings` dinaikkan di
        _inject_one_second(), yaitu saat kendaraan DIMUNCULKAN di ruas hulu --
        itu ukuran PERMINTAAN (datang dari jauh), bukan ALIRAN TERLAYANI, dan
        nilainya sama saja lampu merah atau hijau.

        Produksi mengisi `volume` dari `crossing_simpang.csv`, yaitu kendaraan
        yang memotong garis hitung -- bernilai 0 kalau lampunya merah.
        Ketidakcocokan ini berbahaya: saat inference, lengan ber-lampu merah
        terbaca volume=0, dan model yang dilatih dengan semantik "volume =
        permintaan" akan menyimpulkan lengan itu sepi lalu terus membiarkannya
        merah.

        Kendaraan yang HILANG dari ruas masuk berarti sudah masuk simpang
        (melintasi garis henti) -- ruas masuk bukan tujuan akhir siapa pun,
        jadi satu-satunya cara keluar dari situ adalah melintas.
        """
        crossings = {a: 0 for a in FIXED_CYCLE_ORDER}
        sebelumnya = self._vehicles_on_entry()
        for _ in range(jendela_detik):
            self._inject_one_second()
            self.connection.simulationStep()
            self._arrived_total += int(self.connection.simulation.getArrivedNumber())
            sekarang = self._vehicles_on_entry()
            for approach in FIXED_CYCLE_ORDER:
                crossings[approach] += len(sebelumnya[approach] - sekarang[approach])
            sebelumnya = sekarang
        return crossings

    def _sync_active_phase(self) -> None:
        """Tetapkan current_phase = fase yang akan MEMULAI siklus berikutnya.

        Satu langkah keputusan sekarang mencakup SATU ROTASI PENUH (Bug A),
        dan _set_action() selalu memasang program mulai dari fase 0. Jadi pada
        saat keputusan berikutnya diambil, fase yang akan berjalan adalah
        FIXED_CYCLE_ORDER[0].

        Versi sebelumnya membaca getPhase() dari SUMO di AKHIR langkah, dan
        karena akhir langkah selalu jatuh di penghujung rotasi, hasilnya
        SELALU "west" -- terukur 10/10 langkah, membuat fitur one-hot fase
        praktis konstan dan tidak memberi informasi.

        KETERBATASAN YANG DIKETAHUI (bukan bug, tapi jangan dilupakan): di
        produksi, SignalService memanggil engine pada SETIAP transisi fase,
        sehingga currentPhase yang dilihat inference bisa keempat-empatnya --
        sementara training selalu melihat FIXED_CYCLE_ORDER[0]. Fitur one-hot
        fase karena itu praktis konstan saat training, jadi bobotnya akan
        mengecil sendiri dan variasinya saat inference berdampak kecil. Kalau
        nanti mau benar-benar setara, satu langkah training harus dipersempit
        jadi satu FASE (bukan satu rotasi) -- perubahan desain yang lebih
        besar dan belum dikerjakan.
        """
        self.current_phase = FIXED_CYCLE_ORDER[0]
        self.current_green = self.current_greens.get(
            self.current_phase, self.current_green
        )

    def step(self, action: np.ndarray):
        self._set_action(action)

        # BUG A (diperbaiki 29 Agustus): dulu jendela keputusan SELALU
        # decision_seconds (30 detik) padahal satu rotasi penuh 4 lengan bisa
        # 76-256 detik (hijau 15-60 per lengan + 4 detik kuning x 4). Akibatnya
        # _set_action() memaksa setPhase(0) lagi SEBELUM rotasi sempat sampai
        # timur/selatan/barat -- diukur langsung: 8 dari 8 langkah HANYA utara
        # yang pernah hijau, dan onehot.south/onehot.west SELALU 0 di seluruh
        # observasi. Antrean lengan lain menumpuk tanpa pernah dilayani.
        #
        # Sekarang jendela = durasi rotasi yang BENAR-BENAR dipilih, jadi satu
        # langkah keputusan = satu siklus penuh. Ini juga yang dilakukan
        # produksi: sumo_controller memasang program lalu membiarkannya jalan,
        # bukan menimpanya di tengah siklus.
        window_seconds = self._cycle_seconds()

        # Crossing diakumulasi SEPANJANG rotasi, lalu diskalakan ke laju
        # per-5-detik supaya satuannya sama dengan produksi.
        #
        # Versi pertama perbaikan Bug D cuma mengukur 5 detik TERAKHIR rotasi.
        # Terukur cacat: pada detik-detik itu hanya lengan terakhir (barat)
        # yang hijau, sehingga utara/timur/selatan SELALU bernilai 0 -- bias
        # sistematis, bukan cerminan lalu lintas. Mengukur sepanjang rotasi
        # membuat tiap lengan terwakili sesuai jatah hijaunya masing-masing.
        arrived_sebelum = self._arrived_total
        crossings = self._hitung_crossing(window_seconds)
        arrived = self._arrived_total - arrived_sebelum

        skala = FEATURE_WINDOW_SECONDS / max(1, window_seconds)
        self.recent_crossings = {
            approach: int(round(crossings[approach] * skala))
            for approach in FIXED_CYCLE_ORDER
        }
        self.step_count += 1
        self._sync_active_phase()
        metrics = self._metrics()
        queue_norm = min(1.0, metrics["queue"] / QUEUE_SATURATION_VEH)
        wait_norm = min(1.0, metrics["waiting"] / max(1.0, metrics["vehicles"] * 120.0))
        # BUG E: dinilai sebagai LAJU, bukan jumlah mentah. Tanpa pembagian
        # window_seconds ini, agent bisa menaikkan reward hanya dengan
        # memperpanjang siklus -- lihat catatan di THROUGHPUT_SATURATION_RATE.
        throughput_rate = arrived / max(1, window_seconds)
        throughput_norm = min(1.0, throughput_rate / THROUGHPUT_SATURATION_RATE)
        throughput_reward = THROUGHPUT_REWARD_WEIGHT * throughput_norm
        queue_penalty = QUEUE_REWARD_WEIGHT * queue_norm
        wait_penalty = WAIT_REWARD_WEIGHT * wait_norm
        # Penalti starvation DIHAPUS 29 Agustus: program TLS sekarang selalu
        # dipasang sebagai rotasi penuh 4 lengan dan selalu mulai dari fase 0,
        # sama seperti produksi -- tidak ada lengan yang bisa tidak kebagian
        # hijau, jadi penalti itu tidak punya kondisi pemicu yang sah lagi.
        reward = float(throughput_reward - queue_penalty - wait_penalty)
        # window_seconds WAJIB ikut dilaporkan: panjang satu langkah keputusan
        # ditentukan aksi agent sendiri (76-256 detik), jadi metrik apa pun yang
        # menumpuk sepanjang langkah (throughput, waktu tunggu) TIDAK bisa
        # dibandingkan antar-kebijakan tanpa tahu berapa detik yang dijalankan.
        # Tanpa ini, evaluate_ppo.py sempat membandingkan PPO vs rule-based pada
        # durasi simulasi berbeda (18-20%) dan menyimpulkan PPO kalah throughput
        # 15% -- padahal per detik justru seri. Lihat Bug F di
        # docs/audit-bug-ppo-sebelum-training-ke-5.md.
        metrics.update({"reward": reward, "throughput_interval": float(arrived), "queue_norm": queue_norm,
                        "wait_norm": wait_norm, "window_seconds": float(window_seconds),
                        "throughput_rate": float(throughput_rate),
                        "throughput_reward": throughput_reward, "queue_penalty": queue_penalty,
                        "wait_penalty": wait_penalty})
        return self._observation(), reward, False, self.step_count >= self.episode_steps, metrics

    def _metrics(self) -> dict[str, float]:
        vehicles = list(self.connection.vehicle.getIDList()) if self.connection else []
        waiting = sum(float(self.connection.vehicle.getAccumulatedWaitingTime(v)) for v in vehicles) if self.connection else 0.0
        queue = sum(self.connection.edge.getLastStepHaltingNumber(EDGE_HULU[a]) + self.connection.edge.getLastStepHaltingNumber(EDGE_MASUK[a]) for a in FIXED_CYCLE_ORDER) if self.connection else 0
        arrived = float(self.connection.simulation.getArrivedNumber()) if self.connection else 0.0
        return {"vehicles": float(len(vehicles)), "queue": float(queue), "waiting": waiting, "arrived": arrived}

    def _observation(self) -> np.ndarray:
        state = self._traffic_state()
        return np.asarray(
            build_ppo_observation(
                state,
                current_phase=self.current_phase,
                current_green_seconds=self.current_green,
            ),
            dtype=np.float32,
        )

    def _traffic_state(self) -> TrafficState:
        approaches: list[ApproachState] = []
        for approach in FIXED_CYCLE_ORDER:
            edges = (EDGE_HULU[approach], EDGE_MASUK[approach])
            queue = sum(self.connection.edge.getLastStepHaltingNumber(e) for e in edges)
            density = sum(self.connection.edge.getLastStepVehicleNumber(e) for e in edges)
            speeds = [self.connection.edge.getLastStepMeanSpeed(e) for e in edges]
            speed_kmh = max(0.0, sum(speeds) / len(speeds) * 3.6)
            approaches.append(ApproachState(
                approach=approach,
                volume=int(self.recent_crossings[approach]),
                queueLengthVeh=int(queue),
                queueLengthMEst=float(queue) * METERS_PER_QUEUED_VEHICLE,
                densityIndex=float(density),
                avgSpeedKmh=float(speed_kmh),
            ))
        window_end = datetime.now(timezone.utc)
        return TrafficState(
            intersectionId="simpang4-pingit",
            windowStart=window_end - timedelta(seconds=FEATURE_WINDOW_SECONDS),
            windowEnd=window_end,
            approaches=approaches,
        )

    def rule_based_action(self) -> np.ndarray:
        """Baseline pembanding: durasi hijau dari RuleBasedEngine asli.

        Memakai recommend_cycle() saja -- itu yang benar-benar dipakai
        produksi (SignalService) untuk menentukan durasi keempat lengan.
        recommend() (pemilihan satu lengan pemenang) sengaja TIDAK dipakai
        lagi di sini sejak 29 Agustus, karena env tidak lagi memberi PPO
        maupun baseline kendali atas urutan fase.
        """
        cycle = self.rule_based_engine.recommend_cycle(
            self._traffic_state(), currentPhase=self.current_phase
        )
        green_by_approach = {phase.approach: phase.greenSeconds for phase in cycle.phases}
        green_indexes = [
            min(range(len(GREEN_OPTIONS)), key=lambda index: abs(GREEN_OPTIONS[index] - green_by_approach[approach]))
            for approach in FIXED_CYCLE_ORDER
        ]
        return np.asarray(green_indexes, dtype=np.int64)

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None

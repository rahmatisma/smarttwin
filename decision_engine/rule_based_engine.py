"""
SMARTTWIN — DECISION ENGINE (rule-based)

Ambil traffic_state per lengan (hasil agregasi zona, lihat
cv/vehicle_counter_copy.py) lalu putuskan berapa lama lampu hijau
tiap lengan dan seberapa prioritas lengan itu.

Arsitektur sengaja dipisah jadi interface (DecisionEngine) dan
implementasi (RuleBasedEngine) supaya nanti bisa di-swap ke PPO
tanpa mengubah kode yang memanggilnya — cukup ganti instance-nya:

    engine = RuleBasedEngine()   # sekarang
    engine = PPOEngine()         # nanti, kalau sudah ada

Ini sejalan dengan docs/data-contract.md, di mana SignalRecommendation
punya field `engine: Literal["rule-based", "ppo"]` — "ppo" memang
masih placeholder di kontrak, belum ada implementasinya.
"""

from typing import Dict


# ============================================================
# KONSTANTA ATURAN
# ============================================================

TOTAL_WAKTU_SIKLUS = 120   # detik, tetap untuk satu siklus lampu
WAKTU_HIJAU_MIN = 15       # detik, jatah minimum tiap lengan
BOBOT_KENDARAAN_BESAR = 2  # pengali skor untuk truk dan bus

BATAS_SKOR_TINGGI = 10     # skor > ini -> prioritas "tinggi"
BATAS_SKOR_SEDANG = 5      # skor >= ini (dan <= tinggi) -> "sedang"


# ============================================================
# INTERFACE
# ============================================================

class DecisionEngine:
    """
    Kontrak yang harus dipenuhi semua engine keputusan sinyal,
    baik yang rule-based sekarang maupun PPO nanti.

    decide() menerima kepadatan tiap lengan dan mengembalikan
    alokasi waktu hijau + prioritas tiap lengan.
    """

    def decide(self, traffic_state: dict) -> dict:
        raise NotImplementedError


# ============================================================
# IMPLEMENTASI RULE-BASED
# ============================================================

class RuleBasedEngine(DecisionEngine):
    """
    Bagi waktu hijau satu siklus (120 detik) ke tiap lengan secara
    proporsional terhadap skor kepadatannya. Semua lengan tetap
    dapat jatah minimum 15 detik supaya tidak ada lengan yang
    "kelaparan" walau sepi.
    """

    def decide(self, traffic_state: Dict[str, dict]) -> Dict[str, dict]:
        jumlah_lengan = len(traffic_state)

        # Skor tiap lengan: makin banyak kendaraan (dan makin besar
        # jenisnya) makin tinggi skornya. truk & bus dibobot 2x
        # karena butuh waktu hijau lebih lama untuk melintas
        # dibanding motor/mobil.
        skor_per_lengan = {
            nama: self._hitung_skor(data)
            for nama, data in traffic_state.items()
        }

        total_skor = sum(skor_per_lengan.values())

        # Sisa waktu di luar jatah minimum semua lengan, yang akan
        # dibagi proporsional berdasarkan skor.
        sisa_waktu = TOTAL_WAKTU_SIKLUS - (WAKTU_HIJAU_MIN * jumlah_lengan)

        hasil = {}
        sisa_pecahan = {}

        # Floor (bukan round()) tiap porsi dulu. round() independen per
        # lengan itu sumber bug lama: total dari 4 round() terpisah bisa
        # meleset sampai +-2 detik dari 120, karena tiap pembulatan
        # dilakukan sendiri-sendiri tanpa tahu apa yang terjadi di
        # lengan lain (160 dari 538 window di signal_decisions.csv
        # totalnya jadi 119 atau 121, bukan 120).
        for nama, skor in skor_per_lengan.items():
            if total_skor > 0:
                porsi = (skor / total_skor) * sisa_waktu
            else:
                # Semua lengan sepi (skor 0 semua) — bagi rata sisa
                # waktu supaya tidak ZeroDivisionError.
                porsi = sisa_waktu / jumlah_lengan

            green_exact = WAKTU_HIJAU_MIN + porsi
            green_floor = int(green_exact)

            hasil[nama] = {
                "green_duration": green_floor,
                "prioritas": self._tentukan_prioritas(skor),
                # Diikutkan supaya konsumen hilir (mis. run_decision.py)
                # tidak perlu menghitung ulang skor dengan rumus
                # terpisah yang bisa melenceng dari yang di sini.
                "skor": skor,
            }
            sisa_pecahan[nama] = green_exact - green_floor

        # Metode largest remainder: detik yang "hilang" karena semua
        # porsi di-floor tadi (jumlahnya = sisa_detik, selalu di antara
        # 0 dan jumlah_lengan-1 karena floor tidak pernah melebihi nilai
        # aslinya) dikembalikan satu-satu ke lengan dengan sisa pecahan
        # TERBESAR dulu. Ini menjamin total selalu tepat
        # TOTAL_WAKTU_SIKLUS tanpa pernah perlu koreksi negatif.
        total_terisi = sum(v["green_duration"] for v in hasil.values())
        sisa_detik = TOTAL_WAKTU_SIKLUS - total_terisi

        urutan_pecahan_terbesar = sorted(
            sisa_pecahan, key=sisa_pecahan.get, reverse=True
        )

        for nama in urutan_pecahan_terbesar[:sisa_detik]:
            hasil[nama]["green_duration"] += 1

        return hasil

    @staticmethod
    def _hitung_skor(data: dict) -> float:
        """
        skor = total + (truk * 2) + (bus * 2)

        .get(..., 0) dipakai karena tidak semua lengan tentu punya
        kolom "bus" (lihat contoh traffic_state di docstring modul
        ini, hasil zona kamera yang belum tentu lengkap per kelas).
        """
        total = data.get("total", 0)
        truk = data.get("truk", 0)
        bus = data.get("bus", 0)

        return total + (truk * BOBOT_KENDARAAN_BESAR) + (bus * BOBOT_KENDARAAN_BESAR)

    @staticmethod
    def _tentukan_prioritas(skor: float) -> str:
        if skor > BATAS_SKOR_TINGGI:
            return "tinggi"
        elif skor >= BATAS_SKOR_SEDANG:
            return "sedang"
        else:
            return "rendah"


# ============================================================
# TEST SEDERHANA
# ============================================================

if __name__ == "__main__":
    import json

    contoh_traffic_state = {
        "selatan": {"total": 9, "motor": 2, "mobil": 6, "truk": 1},
        "simpang_tengah": {"total": 3, "motor": 1, "mobil": 2, "truk": 0},
        "barat": {"total": 7, "motor": 3, "mobil": 4, "truk": 0},
        "timur": {"total": 2, "motor": 2, "mobil": 0, "truk": 0},
    }

    engine = RuleBasedEngine()
    signal_timing = engine.decide(contoh_traffic_state)

    print("Input  (traffic_state):")
    print(json.dumps(contoh_traffic_state, indent=2, ensure_ascii=False))

    print("\nOutput (signal_timing):")
    print(json.dumps(signal_timing, indent=2, ensure_ascii=False))

    total_hijau = sum(v["green_duration"] for v in signal_timing.values())
    print(f"\nTotal green_duration semua lengan: {total_hijau} detik "
          f"(target siklus: {TOTAL_WAKTU_SIKLUS} detik)")

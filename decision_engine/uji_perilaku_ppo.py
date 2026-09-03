"""Gerbang uji perilaku PPO -- vonis cepat apakah sebuah checkpoint adaptif.

KENAPA SKRIP INI ADA
--------------------
Lima training berturut-turut (v1-v5) baru ketahuan bermasalah SETELAH dilatih
puluhan ribu langkah dan dievaluasi lewat SUMO. Evaluasi SUMO
(`evaluate_ppo.py`) mahal dan -- yang lebih berbahaya -- bisa LULUS meski
model tidak adaptif sama sekali: v5 menang 7/seri 2/kalah 0 pada metrik
antrean & tunggu, padahal alokasi hijaunya hampir tidak merespons lengan mana
yang sedang padat.

Skrip ini menutup celah itu. Ia mengukur PERILAKU alokasi, bukan hasil akhir
lalu lintas, dan tidak menjalankan SUMO sama sekali -- cuma inference di atas
profil permintaan nyata dari `cv/output/crossing_simpang.csv`. Karena itu
cukup beberapa detik, sehingga bisa dipakai sebagai gerbang di checkpoint dini
(15-20k) untuk memutuskan LANJUT atau HENTIKAN sebelum ongkos training penuh
terlanjur keluar.

TIGA UJI
--------
1. Sebaran aksi     -- apakah model memakai rentang durasi 15-60, atau kolaps
                       ke hijau minimum? (v5: 87,5% keluaran = 15/20 detik)
2. Korelasi alokasi -- Spearman antara peringkat permintaan dan peringkat
                       hijau per lengan, dirata-rata atas seluruh state.
3. Skenario timpang -- satu lengan dipaksa padat, tiga lainnya lengang.
                       Lengan tersibuk seharusnya dapat hijau terpanjang.

Ambang LULUS di bawah ditetapkan di atas garis dasar v5 yang terukur, bukan
ditebak -- lihat AMBANG. Target utamanya adalah membuktikan model BERGERAK
menjauh dari perilaku v5, bukan langsung sempurna.

PEMAKAIAN
---------
    .venv\\Scripts\\python.exe decision_engine/uji_perilaku_ppo.py
    .venv\\Scripts\\python.exe decision_engine/uji_perilaku_ppo.py \\
        --checkpoint decision_engine/models/checkpoints/xxx_20000_steps.zip

Keluar dengan kode 0 kalau LULUS, 1 kalau GAGAL -- supaya bisa dipakai
langsung di skrip pemantau training.

CATATAN METODOLOGI
------------------
State untuk uji 1 & 2 dibangun dari profil permintaan nyata lewat pemetaan
deterministik (veh/min -> volume/antrean/densitas), BUKAN dari SUMO. Jadi
angka absolutnya tidak setara dengan evaluasi SUMO; yang bermakna adalah
perbandingan antar-checkpoint memakai pemetaan yang sama.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.traffic import ApproachState, TrafficState  # noqa: E402

from decision_engine.ppo_engine import GREEN_OPTIONS, PPOEngine  # noqa: E402
from decision_engine.ppo_env import (  # noqa: E402
    DEFAULT_DATA,
    DEFAULT_DENSITY_DATA,
    load_demand_profiles,
)
from decision_engine.rule_based_engine import FIXED_CYCLE_ORDER  # noqa: E402

ARMS = list(FIXED_CYCLE_ORDER)

# Garis dasar TERUKUR dari smarttwin_ppo.zip (v5, checkpoint 60k) pada 2
# September 2026, 538 profil. Dipakai sebagai pembanding, bukan sebagai target.
GARIS_DASAR_V5 = {
    "porsi_hijau_minimum": 0.875,
    "opsi_terpakai": 5,
    "cocok_state_nyata": 0.312,
    "korelasi_rerata": 0.165,
    "cocok_timpang": 1,
}

# AMBANG LULUS. Ditetapkan di tengah antara perilaku v5 dan perilaku ideal --
# cukup longgar untuk checkpoint dini 15-20k (kita mencari TANDA belajar, bukan
# kesempurnaan), cukup ketat untuk menolak pengulangan v5.
AMBANG = {
    # v5 = 0,875. Model yang mulai memakai rentangnya harus turun di bawah ini.
    "porsi_hijau_minimum_maks": 0.70,
    # v5 = 5 dari 10. Keragaman aksi harus bertambah.
    "opsi_terpakai_min": 6,
    # v5 = 0,312, tebak acak = 0,25. Harus jelas di atas kebetulan.
    "cocok_state_nyata_min": 0.45,
    # v5 = +0,165 DIUKUR OLEH UJI INI. (Angka -0,13..+0,08 di catatan Bug P
    # berasal dari environment training, bukan dari uji ini -- jangan
    # dicampur.) v5 sedikit positif karena pada state nyata yang ringan
    # perbedaan antar-lengan kecil sehingga bonus tipis ke utara kebetulan
    # searah. Ambang harus jauh di atasnya supaya benar-benar bermakna.
    "korelasi_min": 0.30,
    # v5 = 1 dari 4 (cuma utara). Minimal 3 dari 4 lengan direspons benar.
    "cocok_timpang_min": 3,
}


# ============================================================
# UTILITAS
# ============================================================

def _peringkat(nilai: list[float]) -> list[float]:
    """Peringkat rata-rata (tie-aware), 1 = terkecil."""
    n = len(nilai)
    urut = sorted(range(n), key=lambda i: nilai[i])
    peringkat = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and nilai[urut[j + 1]] == nilai[urut[i]]:
            j += 1
        rata = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            peringkat[urut[k]] = rata
        i = j + 1
    return peringkat


def _spearman(a: list[float], b: list[float]) -> float | None:
    """Spearman rho lewat Pearson di atas peringkat (menangani ties)."""
    ra, rb = _peringkat(a), _peringkat(b)
    n = len(ra)
    mean_a, mean_b = sum(ra) / n, sum(rb) / n
    kov = sum((ra[i] - mean_a) * (rb[i] - mean_b) for i in range(n))
    var_a = sum((ra[i] - mean_a) ** 2 for i in range(n))
    var_b = sum((rb[i] - mean_b) ** 2 for i in range(n))
    if var_a <= 0 or var_b <= 0:
        # Salah satu sisi seri total -- korelasi tidak terdefinisi.
        return None
    return kov / (var_a * var_b) ** 0.5


def _state(nilai_per_lengan: dict[str, float]) -> TrafficState:
    """Bangun TrafficState dari permintaan veh/min per lengan.

    Pemetaan sengaja deterministik supaya perbandingan antar-checkpoint adil.
    """
    now = datetime.now()
    approaches = []
    for arm in ARMS:
        vpm = nilai_per_lengan[arm]
        antre = int(round(vpm * 0.8))
        approaches.append(
            ApproachState(
                approach=arm,
                volume=int(round(vpm * 5 / 60)),  # crossing per jendela 5 detik
                queueLengthVeh=antre,
                queueLengthMEst=antre * 6.0,
                densityIndex=min(1.0, vpm / 15.0),
                avgSpeedKmh=max(5.0, 40.0 - vpm * 2),
            )
        )
    return TrafficState(
        intersectionId="SIMPANG_CENTER",
        windowStart=now - timedelta(seconds=5),
        windowEnd=now,
        approaches=approaches,
    )


def _hijau(engine: PPOEngine, state: TrafficState) -> dict[str, int]:
    plan = engine.recommend_cycle(state, currentPhase="north")
    return {fase.approach: fase.greenSeconds for fase in plan.phases}


# ============================================================
# UJI
# ============================================================

def uji_sebaran_dan_korelasi(engine: PPOEngine, profil: list[dict[str, float]]) -> dict:
    """Uji 1 & 2 sekaligus -- keduanya jalan di atas state nyata yang sama."""
    sebaran: Counter[int] = Counter()
    korelasi: list[float] = []
    cocok = 0

    for p in profil:
        hijau = _hijau(engine, _state(p))
        for detik in hijau.values():
            sebaran[detik] += 1

        rho = _spearman([p[a] for a in ARMS], [float(hijau[a]) for a in ARMS])
        if rho is not None:
            korelasi.append(rho)

        if max(ARMS, key=lambda a: hijau[a]) == max(ARMS, key=lambda a: p[a]):
            cocok += 1

    n = len(profil)
    total_aksi = n * len(ARMS)
    hijau_minimum = sebaran[GREEN_OPTIONS[0]] + sebaran[GREEN_OPTIONS[1]]
    return {
        "state_diuji": n,
        "sebaran": dict(sorted(sebaran.items())),
        "porsi_hijau_minimum": hijau_minimum / total_aksi,
        "opsi_terpakai": len(sebaran),
        "korelasi_rerata": (sum(korelasi) / len(korelasi)) if korelasi else 0.0,
        "korelasi_terdefinisi": len(korelasi),
        "cocok_state_nyata": cocok / n,
    }


def uji_timpang(engine: PPOEngine) -> dict:
    """Uji 3 -- satu lengan dipaksa padat, tiga lainnya lengang."""
    rincian = []
    cocok = 0
    for padat in ARMS:
        permintaan = {a: (45.0 if a == padat else 2.0) for a in ARMS}
        hijau = _hijau(engine, _state(permintaan))
        terpanjang = max(ARMS, key=lambda a: hijau[a])
        benar = terpanjang == padat
        cocok += int(benar)
        rincian.append(
            {
                "lengan_padat": padat,
                "hijau": {a: hijau[a] for a in ARMS},
                "terpanjang": terpanjang,
                "benar": benar,
            }
        )
    return {"cocok_timpang": cocok, "rincian": rincian}


# ============================================================
# LAPORAN
# ============================================================

def _baris_vonis(nama: str, nilai, ambang, lulus: bool, dasar) -> str:
    tanda = "LULUS" if lulus else "GAGAL"
    return f"  [{tanda}] {nama:<34} {nilai:>8}  (ambang {ambang}, v5 {dasar})"


def laporkan(hasil: dict) -> bool:
    print(f"\nCheckpoint : {hasil['checkpoint']}")
    print(f"State nyata: {hasil['state_diuji']} profil permintaan\n")

    print("SEBARAN DURASI HIJAU")
    total = hasil["state_diuji"] * len(ARMS)
    for detik in GREEN_OPTIONS:
        jumlah = hasil["sebaran"].get(detik, 0)
        pct = 100 * jumlah / total
        print(f"  {detik:>3} dtk : {jumlah:>5} ({pct:>5.1f}%) {'#' * int(pct / 2)}")

    print("\nSKENARIO PERMINTAAN TIMPANG")
    for baris in hasil["rincian"]:
        deret = "/".join(str(baris["hijau"][a]) for a in ARMS)
        tanda = "OK   " if baris["benar"] else "SALAH"
        print(
            f"  {tanda} padat={baris['lengan_padat']:<6} "
            f"hijau(N/E/S/W)={deret:<16} terpanjang={baris['terpanjang']}"
        )

    print("\nVONIS")
    cek = [
        (
            "porsi hijau minimum (15/20 dtk)",
            f"{hasil['porsi_hijau_minimum']:.1%}",
            f"<={AMBANG['porsi_hijau_minimum_maks']:.0%}",
            hasil["porsi_hijau_minimum"] <= AMBANG["porsi_hijau_minimum_maks"],
            f"{GARIS_DASAR_V5['porsi_hijau_minimum']:.1%}",
        ),
        (
            "opsi durasi terpakai (dari 10)",
            str(hasil["opsi_terpakai"]),
            f">={AMBANG['opsi_terpakai_min']}",
            hasil["opsi_terpakai"] >= AMBANG["opsi_terpakai_min"],
            str(GARIS_DASAR_V5["opsi_terpakai"]),
        ),
        (
            "lengan tersibuk dapat hijau max",
            f"{hasil['cocok_state_nyata']:.1%}",
            f">={AMBANG['cocok_state_nyata_min']:.0%}",
            hasil["cocok_state_nyata"] >= AMBANG["cocok_state_nyata_min"],
            f"{GARIS_DASAR_V5['cocok_state_nyata']:.1%}",
        ),
        (
            "korelasi permintaan-alokasi",
            f"{hasil['korelasi_rerata']:+.3f}",
            f">=+{AMBANG['korelasi_min']:.2f}",
            hasil["korelasi_rerata"] >= AMBANG["korelasi_min"],
            f"{GARIS_DASAR_V5['korelasi_rerata']:+.3f}",
        ),
        (
            "skenario timpang benar (dari 4)",
            str(hasil["cocok_timpang"]),
            f">={AMBANG['cocok_timpang_min']}",
            hasil["cocok_timpang"] >= AMBANG["cocok_timpang_min"],
            str(GARIS_DASAR_V5["cocok_timpang"]),
        ),
    ]
    for nama, nilai, ambang, lulus, dasar in cek:
        print(_baris_vonis(nama, nilai, ambang, lulus, dasar))

    lulus_semua = all(item[3] for item in cek)
    jumlah_lulus = sum(1 for item in cek if item[3])
    print(f"\n  {jumlah_lulus}/5 kriteria terpenuhi")
    if lulus_semua:
        print("  ==> LANJUTKAN training. Model menunjukkan alokasi adaptif.")
    else:
        print("  ==> HENTIKAN. Perilaku belum bergerak dari pola v5;")
        print("      training lebih lama tidak akan memperbaikinya sendiri.")
    return lulus_semua


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="path checkpoint .zip (default: decision_engine/models/smarttwin_ppo.zip)",
    )
    parser.add_argument("--json", default=None, help="simpan hasil mentah ke file JSON")
    parser.add_argument(
        "--batas",
        type=int,
        default=0,
        help="pakai N profil pertama saja (0 = semua) -- untuk uji cepat",
    )
    args = parser.parse_args()

    engine = PPOEngine(model_path=args.checkpoint) if args.checkpoint else PPOEngine()
    if not engine.available:
        print(f"GAGAL: checkpoint tidak bisa dimuat -- {engine.load_error}")
        return 1

    profil = load_demand_profiles(DEFAULT_DATA, DEFAULT_DENSITY_DATA)
    if args.batas:
        profil = profil[: args.batas]

    hasil = {"checkpoint": str(engine.model_path)}
    hasil.update(uji_sebaran_dan_korelasi(engine, profil))
    hasil.update(uji_timpang(engine))

    lulus = laporkan(hasil)
    hasil["lulus"] = lulus

    if args.json:
        Path(args.json).write_text(
            json.dumps(hasil, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nHasil mentah disimpan ke {args.json}")

    return 0 if lulus else 1


if __name__ == "__main__":
    raise SystemExit(main())

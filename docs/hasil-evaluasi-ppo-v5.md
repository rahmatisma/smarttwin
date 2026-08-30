# Hasil Evaluasi PPO v5 — Checkpoint 60.000 Langkah (Final)

**Dijalankan 30 Agustus 2026, Rahmat.** Ini evaluasi resmi 3-seed dari
checkpoint yang dipromosikan jadi `decision_engine/models/smarttwin_ppo_v5.zip`
(dan menggantikan `smarttwin_ppo.zip`, path default `PPOEngine`). Latar
belakang lengkap perbaikan Bug E-P yang mengantar ke checkpoint ini ada di
`docs/audit-bug-ppo-sebelum-training-ke-5.md`. Dokumen ini bukan status
tracker; status tetap di `docs/STATUS-DAN-SISA-KERJA.md`.

**Identitas checkpoint:** dilatih dari nol dengan reward+observasi pasca
Bug E-O (`OBSERVATION_SIZE=21`, permintaan dikalibrasi `BAGI_ARUS_DUA_ARAH=2,0`
× `SKALA_PERMINTAAN=0,40`), lalu di-*resume* dua kali dengan `ent_coef=0,05`
(0→20k→50k→60k). Dihentikan manual di 60k, **bukan** hasil `learn()` yang
selesai penuh — lihat metadata di `smarttwin_ppo_v5.training.json`.

---

## Ringkasan eksekutif

| Aspek | Hasil |
|---|---|
| Metrik lalu lintas, 3 seed × 3 metrik (9 perbandingan) | **Menang 7, seri 2, kalah 0** |
| Dibanding v4 (menang 3, kalah 4, seri 2 dari 9) | Lompatan besar |
| `mean_queue_veh` | Menang di **3/3 seed**, −46% s/d −51% |
| `mean_wait_per_vehicle_s` | Menang di **3/3 seed**, −60% s/d −63% |
| `throughput_veh_per_hour` | Menang 1 seed (+2,2%), seri 2 seed (di bawah ambang seri 2%) |
| Gerbang kualitas resmi (butuh menang di SEMUA metrik) | Lulus hanya di seed 1000 |
| Bug P (fairness antar-lengan / respons ke permintaan) | 🔴 **Belum selesai — lihat bagian "Yang tidak dibuktikan" di bawah** |

> ⚠️ Angka bagus di atas **tidak boleh dibaca sebagai "Bug P sudah selesai"**.
> Lihat bagian terakhir dokumen ini sebelum mengutip hasil ini di laporan.

---

## 1. Angka lengkap per seed

Dijalankan dengan `evaluate_ppo.py` versi pasca-Bug F (episode waktu-simulasi
setara, 1.800 detik per policy per seed, bukan jumlah langkah tetap).

| Metrik | Seed 1000 | Seed 2000 | Seed 3000 |
|---|---|---|---|
| `mean_queue_veh` — PPO | 8,27 | 8,51 | 8,12 |
| `mean_queue_veh` — rule-based | 15,42 | 15,96 | 16,46 |
| Selisih | **−46,4%** | **−46,7%** | **−50,6%** |
| `mean_wait_per_vehicle_s` — PPO | 13,48 | 15,32 | 13,38 |
| `mean_wait_per_vehicle_s` — rule-based | 36,20 | 38,47 | 36,33 |
| Selisih | **−62,8%** | **−60,2%** | **−63,2%** |
| `throughput_veh_per_hour` — PPO | 1.122,4 | 1.085,4 | 1.081,4 |
| `throughput_veh_per_hour` — rule-based | 1.098,5 | 1.093,1 | 1.087,7 |
| Selisih | **+2,18%** menang | −0,70% seri | −0,58% seri |
| Kesetaraan durasi simulasi (`skew_percent`) | 0,12% | 1,70% | 1,34% |

Ketiga seed punya `skew_percent` jauh di bawah ambang 5% — perbandingan sah,
bukan artefak durasi tidak setara (lihat Bug F).

`throughput_veh_per_hour` seri di 2 dari 3 seed karena `TIE_THRESHOLD_PERCENT
= 2,0`: selisih di bawah 2% dihitung seri, bukan kalah, supaya noise simulasi
tidak disalahartikan sebagai kekalahan sistematis.

---

## 2. Kenapa ini jauh lebih baik dari v4

v4 (checkpoint 80k, dievaluasi dengan `evaluate_ppo.py` yang SAMA) hanya
menang 3, kalah 4, seri 2 dari 9 perbandingan, dan **tidak pernah menang
throughput** (lihat `docs/hasil-evaluasi-ppo-v4-80k.md` bagian 11). v5 menang
atau seri di semua 9 — tidak pernah kalah sama sekali.

Penyebab paling mungkin bukan satu hal tunggal, tapi akumulasi seluruh
perbaikan Bug E-O sebelum training v5 dimulai:

- Bug O (kalibrasi permintaan dua-arah) membuat beban lalu lintas training
  realistis terhadap kapasitas jaringan (0,75 veh/detik vs ~1,0 kapasitas,
  dulu 1,66 veh/detik jauh melebihi kapasitas).
- Bug I (profil permintaan diperbarui tiap 5 detik, bukan dibekukan
  sepanjang episode) membuat sinyal training jauh lebih realistis.
- Bug J (observasi 21 fitur, one-hot fase konstan dihapus) menghilangkan
  derau yang tadinya aktif di saat inference.
- Bug E/F (throughput dinormalisasi per-detik, evaluasi durasi setara)
  membuat perbandingan v4 vs v5 ini sendiri sah untuk dilakukan.

---

## 3. Yang TIDAK dibuktikan oleh angka di atas

Uji perilaku terkontrol (bukan evaluasi SUMO di atas, tapi uji permintaan
ekstrem — satu lengan dipaksa permintaan tinggi, tiga lainnya nol) pada
checkpoint 60k yang SAMA menunjukkan model **hampir tanpa syarat mengutamakan
lengan utara**, terlepas dari lengan mana yang sebenarnya sedang menumpuk:

| Skenario | Lengan tersibuk dapat hijau terpanjang? |
|---|---|
| Utara timpang | ✅ Ya (35-50 detik) |
| Timur timpang | (belum diuji terpisah — pola sama dengan barat/selatan) |
| Selatan timpang | ❌ Tidak — tetap 15-20 detik, utara tetap dapat porsi terbesar |
| Barat timpang | ❌ Tidak — tetap 15-20 detik, utara tetap dapat porsi terbesar |

Pola ini identik di 5 percobaan perbaikan berbeda (lihat Bug P di
`docs/audit-bug-ppo-sebelum-training-ke-5.md`), jadi kemungkinan bukan salah
tuning yang belum ditemukan, melainkan keterbatasan struktural: utara adalah
lengan dengan service rate terburuk di jaringan (Bug N-2). Evaluasi SUMO di
atas kemungkinan besar menang **karena** strategi "utamakan utara terus"
kebetulan merupakan kebijakan pengaturan sinyal yang baik secara global untuk
jaringan timpang ini — bukan karena model belajar merespons permintaan
per-siklus secara adil ke keempat lengan.

**Cara menulis ini di laporan teknis:** "PPO v5 secara konsisten mengungguli
baseline rule-based pada metrik antrean dan waktu tunggu (evaluasi SUMO 3
seed), namun pengujian perilaku terpisah menunjukkan model belum sepenuhnya
adaptif terhadap distribusi permintaan per-lengan secara real-time —
kemungkinan model mengoptimalkan strategi global yang mengkompensasi
ketidakseimbangan struktural jaringan (lihat keterbatasan jaringan yang
didokumentasikan), bukan murni merespons kepadatan sesaat." Ini konsisten
dengan arahan pembimbing untuk mensimulasikan tanpa mengklaim kesempurnaan.

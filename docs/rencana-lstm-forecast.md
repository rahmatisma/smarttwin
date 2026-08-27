# Rencana LSTM Forecast — apa yang diprediksi, dari data apa, dan kenapa

> **Pembaruan implementasi 26 Agustus 2026:** `queueLengthVeh` dan
> `queueLengthMEst` sekarang berisi estimasi CV yang bervariasi dan model sudah
> dilatih dengan empat fitur. Sequence training yang melintasi gap observasi
> sekarang ditolak dan evaluasi menyertakan baseline last-value. Backend
> menyediakan `POST /api/forecast/approaches`; hasil agregat dialokasikan ke
> pendekat berdasarkan proporsi 12 timestep terakhir. `RuleBasedEngine` dan
> `ScenarioEngine` menerima forecast secara opsional dengan fallback penuh ke
> perilaku lama. Predicted demand belum diinjeksi sebagai kendaraan baru ke
> SUMO, jadi bagian itu tetap pekerjaan lanjutan. Catatan lama di bawah
> dipertahankan sebagai audit trail dan superseded oleh pembaruan ini.

Ditulis 25 Agustus 2026 sebagai rencana, lalu disinkronkan dengan implementasi aktual 27 Agustus. Bagian historis dipertahankan untuk menjelaskan perubahan keputusan; status terkini dan checklist di bagian akhir menjadi acuan.

---

## 1. Tujuan (biar tidak lupa di tengah jalan)

LSTM ini **bukan** buat tebak-tebakan volume lalu lintas jam berapa nanti secara umum. Tujuannya spesifik: **bantu `RuleBasedEngine` mutusin berapa detik satu lengan harus dapat hijau**, dengan cara melihat "kalau lengan ini dikasih hijau terus, kepadatannya bakal turun secepat apa?" — bukan cuma lihat kondisi SEKARANG (yang sudah dijawab data CV real-time), tapi kondisi BEBERAPA DETIK KE DEPAN.

Kalau desainnya tidak mengarah ke pertanyaan itu, dia tidak berguna buat sistem ini — sekeren apa pun akurasinya.

---

## 2. Apa yang diprediksi

4 angka, per approach, per langkah waktu ke depan:

| Fitur | Satuan | Sumber data asli | Status data sekarang |
|---|---|---|---|
| `vehicleCount` | jumlah kendaraan | `volume` di `TrafficState` (dari `crossing_simpang.csv` — ALIRAN, kendaraan lewat garis) | ✅ Data asli, bervariasi |
| `densityIndex` | indeks kepadatan zona | `densityIndex` di `TrafficState` (dari `snapshot_zona.csv` sejak 25 Agustus — KEHADIRAN, kendaraan di zona) | ✅ Data asli, bervariasi |
| `queueLengthVeh` | jumlah kendaraan antre | `queueLengthVeh` di `TrafficState` | ✅ Data estimasi CV asli, bervariasi, sudah dipakai training |
| `queueLengthMEst` | estimasi antrean (meter) | `queueLengthMEst` di `TrafficState` | ✅ Data estimasi CV asli, bervariasi, sudah dipakai training |

**`avgSpeedKmh` TIDAK diprediksi sama sekali** — tidak ada di 4 fitur ini, dan memang belum ada sumber data kecepatan.

**Status terbaru:** dua fitur antrean sudah berasal dari `hitung_antrean()` pada pipeline CV dan tidak lagi konstan nol. Model agregat dan shared LSTM per-approach sudah dilatih dengan empat fitur penuh. Nilainya tetap merupakan estimasi berbasis zona/tracking, bukan pengukuran fisik manual; khusus north, density dan antrean memakai zona `simpang_tengah` sebagai proxy.

### 2.1 Rencana bertahap (historis, sudah superseded)

Supaya Yuli tidak nunggu (waktu tersisa cuma H-6 ke 31 Agustus), disepakati jalan **2 fase paralel**, bukan satu jalur berurutan:

- **Fase 1 — jalan SEKARANG (Yuli).** Latih LSTM cuma pakai 2 fitur yang datanya sudah asli: `vehicleCount` + `densityIndex`. Sekalian benerin granularitas (bagian 4) dan cari `SEQUENCE_LENGTH` yang pas (bagian 6) — kerjaan infrastruktur/pipeline ini tetap kepakai di Fase 2, tidak kebuang.
- **Fase 2 — nanti setelah CSV antrean baru siap (Rahmat).** Rahmat yang jalanin logika perhitungan antrean (definisi ulang buat pendekatan zona + tracking kendaraan berhenti, lihat `docs/realtime-dashboard.md`) dan hasilnya jadi CSV baru dengan `queueLengthVeh`/`queueLengthMEst` yang isinya bukan nol lagi. Begitu CSV itu ada, Yuli **retrain ulang** pipeline yang sama dari Fase 1, sekarang pakai 4 fitur penuh.

Jadi bukan "Yuli pegang kerjaan lain dulu sambil nunggu" — dia tetap di LSTM dari sekarang, cuma scope datanya yang bertahap.

**Hasil aktual:** Fase 1 dua fitur tidak dijalankan karena data antrean selesai lebih cepat. Yuli langsung melatih model empat fitur. Ini perubahan urutan kerja yang disengaja, bukan tugas yang terlewat.

---

## 3. Sumber data — gabungan, bukan satu CSV

LSTM butuh `vehicleCount` (dari crossing) DAN `densityIndex` (dari zona) sekaligus. Tidak ada satu CSV pun di `cv/output/` yang punya keduanya sudah tergabung — kecuali data yang **sudah masuk Supabase** (`trafficStates` + `trafficApproachStates`), karena itu hasil gabungan `crossing_simpang.csv` + `snapshot_zona.csv` lewat `backend/app/pipeline/cv_csv_bridge.py`.

**Rekomendasi awal:** latih langsung dari histori `TrafficState` di Supabase. **Keputusan implementasi aktual:** training memakai snapshot CSV beku (`crossing_simpang.csv` + `snapshot_zona.csv`) agar reproducible, sedangkan serving membaca kontrak `TrafficState` dari Supabase. Pipeline CSV memakai nama, satuan, interval lima detik, dan empat fitur yang sama dengan kontrak runtime. Risiko distribution mismatch tetap dicatat; retraining berikutnya sebaiknya menambahkan uji kesetaraan tensor CSV versus record Supabase yang merepresentasikan window sama.

Kalau terpaksa pakai CSV (misal Supabase belum lengkap): gabung `crossing_simpang.csv` (`vehicleCount`) + `snapshot_zona.csv` (`densityIndex`) persis dengan logika yang ada di `cv_csv_bridge.py::_load_merged()` — jangan bikin logika gabung baru yang beda, biar konsisten sama apa yang sudah ada di Supabase.

---

## 4. Granularitas waktu — 5 detik, BUKAN 1 menit

### Kenapa bukan 1 menit (kesalahan yang ditemukan malam ini)

Implementasi yang ada sekarang (`realtime_forecast_service.py::_prepare_minute_data()`) mengagregasi data ke window **1 menit** (`df["windowStart"].dt.floor("min")`). Ini salah untuk dua alasan:

1. **Kekasaran waktu tidak cocok tujuan.** Satu sesi lampu hijau cuma 15-60 detik (`MIN_GREEN_SECONDS`/`MAX_GREEN_SECONDS` di `decision_engine/rule_based_engine.py`). Prediksi "1 menit ke depan" sudah melewati 1-4 pergantian sesi lampu pas hasilnya keluar — tidak bisa dipakai buat mutusin sesi SAAT INI.
2. **Data jadi terlalu sedikit buat dilatih.** Rekaman CV yang ada cuma **49 menit** (`snapshot_zona.csv`: 2613 timestamp unik, dari `16:30:12` sampai `17:19:16`, 15 Agustus 2026). Diagregasi ke per-menit → cuma **~43 titik data total**. `SEQUENCE_LENGTH = 30` (butuh 30 titik buat "lihat ke belakang") menyisakan **~13 contoh buat belajar** — jauh di bawah jumlah yang wajar buat LSTM mana pun.

### Kenapa 5 detik

Data CV asli (crossing & zona, setelah digabung) sudah dalam window 5 detik — itu granularitas native `WINDOW_SECONDS` di `cv_csv_bridge.py`, dan itu juga satuan yang dipakai di seluruh `trafficStates` Supabase. Pakai granularitas yang sama, bukan dikasarkan lagi, artinya:

- **~589 titik data** dari 49 menit rekaman yang sama (2944 detik ÷ 5 = ~589) — **13x lebih banyak** dari cara per-menit
- Prediksi 12 langkah × 5 detik = **60 detik ke depan** — persis durasi maksimal satu sesi lampu, langsung relevan buat keputusan `recommended_green_seconds`

---

## 5. Horizon prediksi — multi-step ke depan, bukan satu titik

Desain lama (`forecast_service.py` versi awal) cuma prediksi 1 nilai per approach (`values[0]`), sisanya di-hardcode 0. Desain baru (`realtime_forecast_service.py`) sudah multi-step tapi granularitasnya salah (per menit, lihat bagian 4).

**Rencana yang benar:** model prediksi **N langkah ke depan sekaligus** (autoregresif, seperti yang sudah ada di `realtime_forecast_service.py` — pola ini dipertahankan, cuma satuan waktunya diganti), dengan N dipilih supaya totalnya mencakup minimal satu sesi lampu penuh:

```
N = 12   (12 x 5 detik = 60 detik = MAX_GREEN_SECONDS)
```

Output-nya jadi deret: prediksi detik ke-5, ke-10, ke-15, ..., ke-60 — bukan cuma satu angka "nanti". Decision engine bisa lihat TREN sepanjang deret itu (naik/turun/stabil), bukan cuma satu titik.

---

## 6. `SEQUENCE_LENGTH` (seberapa jauh model "melihat ke belakang") — SUDAH DIUJI

Sekarang `SEQUENCE_LENGTH = 30`, didesain buat skala menit (artinya "lihat 30 menit ke belakang" — masuk akal buat tren jam sibuk). Kalau pindah ke skala 5 detik, `SEQUENCE_LENGTH = 30` cuma berarti "lihat 150 detik (2,5 menit) ke belakang" — beda makna total, dan belum tentu masih pilihan yang tepat.

Eksperimen reproducible dijalankan 27 Agustus lewat `forecasting/scripts/lstm/per_approach/sequence_length_experiment.py`. Pemilihan memakai **validation MAE dalam satuan asli**, bukan test MAE, supaya test tidak bocor ke pemilihan konfigurasi.

| Input steps | Histori | Sequence train/val/test | Validation MAE | Status |
|---:|---:|---:|---:|---|
| 6 | 30 detik | 1164 / 136 / 64 | 1,8841 | Layak |
| **12** | **60 detik** | **1044 / 100 / 16** | **1,8046** | **Terpilih** |
| 18 | 90 detik | — | — | Tidak layak: satu split tidak punya sequence kontinu |
| 30 | 150 detik | — | — | Tidak layak |
| 60 | 300 detik | — | — | Tidak layak |
| 120 | 600 detik | — | — | Tidak layak |

Hasil lengkap tersimpan di `forecasting/outputs/lstm/per_approach/sequence_length_experiment.json`. Dengan dataset dan aturan sadar-gap sekarang, 12 langkah adalah kandidat layak terbaik. Kandidat 5-10 menit yang semula disarankan tidak dapat diuji secara sah karena gap dan pendeknya blok kontinu pada validation/test.

---

## 7. Keterbatasan data — jujur dari awal

- **Cuma 49 menit rekaman, dari SATU sesi (15 Agustus, siang hari).** Tidak ada variasi kondisi (tidak ada data malam hari, tidak ada data hari kerja vs weekend, tidak ada data hujan). Model ini **tidak akan bisa generalisasi** ke kondisi yang tidak pernah direkam — itu bukan bug, itu keterbatasan data mentah yang ada.
- **~589 titik data (skala 5 detik)** itu jauh lebih baik dari ~43 (skala menit), tapi tetap kecil untuk LSTM standar. Realistis: model ini pantas diperlakukan sebagai **bukti-konsep** ("LSTM bisa dipasang dan menghasilkan angka yang masuk akal"), bukan model produksi yang diklaim akurat — sama seperti status PeMS04/TMU/Brisbane yang sudah didokumentasikan di `CLAUDE.md` (dilatih & dievaluasi, tapi masalahnya transferabilitas/skala data, bukan modelnya "gagal").
- **Antrean adalah estimasi CV, bukan ground truth manual.** Nilainya sudah bervariasi dan dapat dipakai sebagai proof of concept, tetapi kualitasnya tetap mengikuti akurasi zona, tracking kendaraan berhenti, dan proxy north.

---

## 8. Bagaimana hasil prediksi dipakai `RuleBasedEngine` — SUDAH diimplementasikan

`RuleBasedEngine.recommend()` dan `recommend_cycle()` sekarang menerima forecast opsional. Jalur live (`RecommendationService`/`SignalService`) dan jalur simulasi (`ScenarioEngine`) mencampur 70% state aktual dengan 30% forecast horizon +60 detik. Jika histori/model gagal, forecast menjadi `None` dan perilaku kembali identik ke rule-based lama. Worker cache juga sudah menghubungkan hasil Scenario Generator ke `/recommendation` dan terverifikasi end-to-end.

**Batas klaim:** LSTM tidak action-conditioned—model tidak menerima fase/durasi lampu sebagai input. Ia memprediksi tren demand 60 detik mendatang, bukan kontrafaktual “apa yang terjadi jika south diberi hijau X detik”. Dampak timing diuji setelahnya oleh SUMO. Predicted demand juga belum diinjeksi sebagai kendaraan baru ke route SUMO.

---

## 9. Status implementasi (diperbarui 25 Agustus malam — audit sebelumnya di bagian ini TERBALIK dari kenyataan kode)

Audit awal dokumen ini (ditulis siang 25 Agustus) menyimpulkan `realtime_forecast_service.py` yang aktif dan `forecast_service.py` yang mati. **Itu salah** — waktu itu belum dicek langsung apa yang benar-benar di-import `forecast.py`. Audit ulang malam ini (lewat `grep` ke seluruh repo, bukan menduga dari nama file) membalik kesimpulannya:

1. **`backend/app/services/forecast_service.py`** (`ForecastService`) — model agregat aktif dan fallback. Sudah PyTorch, 4 fitur, `INPUT_TIMESTEPS=12` / `OUTPUT_TIMESTEPS=12` pada skala 5 detik (60 detik histori → 60 detik forecast).
2. **`backend/app/services/realtime_forecast_service.py`** (`RealtimeForecastService`) — **DIHAPUS 25 Agustus malam.** Tidak di-import siapa pun (dikonfirmasi lewat grep, nol hasil di luar dirinya sendiri dan satu baris komentar di `prepare_data.py`), dan tidak bisa jalan sama sekali kalau diinstansiasi (`load_model(...)` dipanggil tanpa pernah di-import — `NameError` instan). Menunjuk ke `.keras`/`backend/models/` yang direktorinya tidak ada. File ini adalah sisa desain lama (agregasi per-menit, masalah yang dibahas di bagian 4) yang tidak pernah disambungkan ke apa pun.
3. **`backend/app/repositories/forecast_repository.py`** (`ForecastRepository`) — **DIHAPUS bersamaan**, karena satu-satunya pemakainya adalah `RealtimeForecastService` di atas. Sebagai catatan audit trail: query-nya sendiri sebenarnya tidak pernah bisa jalan — memfilter kolom `intersectionId`/`windowStart` yang tidak ada di tabel `trafficApproachStates` (kolom itu ada di `trafficStates`), jadi akan melempar `APIError 42703` kalau sempat dipanggil.
4. **`backend/tests/test_forecast_realtime.py`** — **DIHAPUS bersamaan.** Bukan test pytest asli (`def main()`, nol `def test_*`), sama persis polanya dengan 4 file basi yang sudah dihapus di item 2.5 `pembagian-tugas-24-agustus.md`. Sebelum dihapus, file ini aktif MEMBUAT `pytest -q` gagal collection total (bukan cuma 1 test gagal) karena mengimpor dua kelas yang sudah dihapus. Regresi ini tidak tercatat di mana pun sebelum ditemukan malam ini.
5. **`decision_engine/rule_based_engine.py`** — ini bukan model LSTM, tetapi sekarang menjadi konsumen forecast. `recommend()` dan `recommend_cycle()` menerima forecast opsional berbobot runtime 0,3 dengan fallback aman ke state aktual.

**Pembaruan 26 Agustus:** modul ONNX legacy `backend/app/models/lstm_forecast.py` dan test pasangannya sudah dihapus setelah dipastikan tidak dipakai kode produksi. Serving aktif memakai `backend/app/services/forecast_service.py`; shared LSTM per-approach memiliki pipeline dan artefak terpisah di `forecasting/outputs/lstm/per_approach/`.

---

## 10. Checklist

### Fase 1 — Yuli (hasil aktual)

- [ ] Sumber training diputuskan: gabungan CSV beku yang reproducible; serving tetap dari `TrafficState` Supabase
- [ ] Granularitas lima detik (window native)
- [ ] Eksperimen `SEQUENCE_LENGTH`: 12 langkah terpilih berdasar validation MAE; kandidat lebih panjang tidak feasible karena gap
- [ ] Fase dua fitur superseded; langsung empat fitur karena data antrean sudah siap
- [ ] Model dan scaler tersimpan/ter-track dalam format keputusan tim: PyTorch `.pt` + JSON, bukan Keras `.keras` + pickle
- [ ] `forecast_service.py` dipertahankan sebagai model agregat/fallback; shared model per-approach menjadi jalur utama
- [ ] Forecast tersambung ke `RuleBasedEngine.recommend()`/`recommend_cycle()`, jalur live, ScenarioEngine, dan cache dashboard

### Fase 2 — Rahmat, jalankan logika antrean → Yuli retrain 4 fitur

- [ ] Rahmat: desain ulang definisi "antrean" buat pendekatan zona + logika kendaraan berhenti
- [ ] Rahmat: jalankan ke rekaman; CSV antrean berisi nilai bervariasi dan sudah di-ingest
- [x] Yuli: retrain ulang pipeline dari Fase 1, sekarang 4 fitur penuh (`vehicleCount`, `densityIndex`, `queueLengthVeh`, `queueLengthMEst`)
- [x] Update tabel di bagian 2 dokumen ini — status `queueLengthVeh`/`queueLengthMEst` sudah diperbarui menjadi data estimasi CV asli

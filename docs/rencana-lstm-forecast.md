# Rencana LSTM Forecast — apa yang diprediksi, dari data apa, dan kenapa

Ditulis 25 Agustus 2026 setelah diskusi panjang soal kenapa implementasi LSTM yang sudah ada malam ini (ada 3 versi berbeda, saling tidak sinkron) belum benar-benar cocok buat tujuan aslinya: bantu atur durasi lampu hijau. Dokumen ini rencana yang disepakati, bukan yang sudah diimplementasikan — checklist di bagian akhir yang menandai mana yang sudah/belum.

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
| `queueLengthVeh` | jumlah kendaraan antre | `queueLengthVeh` di `TrafficState` | ⚠️ **SELALU 0** — CV belum pernah menghitung ini (lihat `docs/realtime-dashboard.md`) |
| `queueLengthMEst` | estimasi antrean (meter) | `queueLengthMEst` di `TrafficState` | ⚠️ **SELALU 0** — sama, belum ada logikanya di CV |

**`avgSpeedKmh` TIDAK diprediksi sama sekali** — tidak ada di 4 fitur ini, dan memang belum ada sumber data kecepatan.

**Implikasi peringatan di atas:** karena 2 dari 4 fitur selalu 0 di seluruh data training, model akan "belajar" bahwa antrean selalu 0 — bukan salah modelnya, itu jujur cerminan data yang ada. Prediksi `queueLengthVeh`/`queueLengthMEst` dari model ini **tidak boleh dipercaya** sampai CV benar-benar menghitung antrean asli (lihat catatan RunPod di `docs/realtime-dashboard.md`). Kalau mau, latih dulu cuma pakai 2 fitur yang datanya asli (`vehicleCount`, `densityIndex`) — lebih jujur daripada pura-pura prediksi antrean dari data yang isinya nol semua.

---

## 3. Sumber data — gabungan, bukan satu CSV

LSTM butuh `vehicleCount` (dari crossing) DAN `densityIndex` (dari zona) sekaligus. Tidak ada satu CSV pun di `cv/output/` yang punya keduanya sudah tergabung — kecuali data yang **sudah masuk Supabase** (`trafficStates` + `trafficApproachStates`), karena itu hasil gabungan `crossing_simpang.csv` + `snapshot_zona.csv` lewat `backend/app/pipeline/cv_csv_bridge.py`.

**Rekomendasi: latih langsung dari histori `TrafficState` di Supabase**, bukan dari CSV mentah manapun. Alasannya bukan cuma "lebih gampang" — ini soal **konsistensi training vs serving**: `ForecastRepository.get_recent_traffic_states()` (yang dipakai pas prediksi live nanti) baca dari Supabase. Kalau training pakai sumber lain (CSV mentah, atau CSV yang digabung manual dengan cara berbeda), ada risiko datanya sedikit beda dari yang dilihat model pas serving — model bisa "kaget" sama distribusi data yang berbeda dari waktu latihan.

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

## 6. `SEQUENCE_LENGTH` (seberapa jauh model "melihat ke belakang")

Sekarang `SEQUENCE_LENGTH = 30`, didesain buat skala menit (artinya "lihat 30 menit ke belakang" — masuk akal buat tren jam sibuk). Kalau pindah ke skala 5 detik, `SEQUENCE_LENGTH = 30` cuma berarti "lihat 150 detik (2,5 menit) ke belakang" — beda makna total, dan belum tentu masih pilihan yang tepat.

**Belum ada jawaban pasti** untuk angka yang benar di skala 5 detik — ini butuh eksperimen (coba beberapa nilai, lihat mana yang hasil validasinya paling baik), bukan ditebak dari dokumen ini. Titik awal yang masuk akal: coba `SEQUENCE_LENGTH` setara 5-10 menit histori (60-120 langkah) dulu, sesuaikan dari hasil.

---

## 7. Keterbatasan data — jujur dari awal

- **Cuma 49 menit rekaman, dari SATU sesi (15 Agustus, siang hari).** Tidak ada variasi kondisi (tidak ada data malam hari, tidak ada data hari kerja vs weekend, tidak ada data hujan). Model ini **tidak akan bisa generalisasi** ke kondisi yang tidak pernah direkam — itu bukan bug, itu keterbatasan data mentah yang ada.
- **~589 titik data (skala 5 detik)** itu jauh lebih baik dari ~43 (skala menit), tapi tetap kecil untuk LSTM standar. Realistis: model ini pantas diperlakukan sebagai **bukti-konsep** ("LSTM bisa dipasang dan menghasilkan angka yang masuk akal"), bukan model produksi yang diklaim akurat — sama seperti status PeMS04/TMU/Brisbane yang sudah didokumentasikan di `CLAUDE.md` (dilatih & dievaluasi, tapi masalahnya transferabilitas/skala data, bukan modelnya "gagal").
- **2 dari 4 fitur (antrean) selalu 0** — lihat bagian 2. Kalau mau laporan yang jujur, sebutkan ini eksplisit: LSTM memprediksi `vehicleCount` dan `densityIndex` dengan data asli, TIDAK memprediksi antrean secara bermakna (datanya tidak pernah ada nilai selain 0).

---

## 8. Bagaimana hasil prediksi dipakai `RuleBasedEngine` — BELUM diimplementasikan

Sampai dokumen ini ditulis, **belum ada kode yang menyambungkan** hasil forecast ke `RuleBasedEngine.recommend()`. Decision engine sekarang murni reaktif (lihat kondisi SEKARANG dari `TrafficState`), belum memakai prediksi masa depan sama sekali. Ini pekerjaan terpisah, belum masuk scope siapa pun secara eksplisit — perlu diputuskan di rapat tim apakah ini dikerjakan sebelum 31 Agustus atau didokumentasikan sebagai "arsitektur mendukung, implementasi belum", mengingat sisa waktu H-6.

Kalau dikerjakan, pola yang masuk akal: `RuleBasedEngine.recommend()` menerima parameter opsional `forecast: ForecastResult | None` — kalau ada, dipakai buat menyesuaikan `green_time` (misal: kalau prediksi kepadatan lengan itu naik terus 60 detik ke depan, kasih hijau lebih lama dari yang dihitung murni dari kondisi sekarang). Kalau `None`, tetap jalan seperti sekarang (murni rule-based dari kondisi saat ini) — supaya forecast jadi PENYEMPURNA, bukan SYARAT WAJIB (kalau LSTM gagal/model belum ada, sistem tetap jalan).

---

## 9. Status implementasi malam ini (25 Agustus) — ada 3 versi berbeda, membingungkan

Ditemukan lewat audit langsung ke kode, dicatat di sini biar tidak diulang kebingungannya:

1. **`backend/app/services/forecast_service.py`** (`ForecastService`) — versi PERTAMA. TensorFlow, cuma pakai `values[0]` buat `predictedVehicleCount`, sisanya hardcode 0/None. Sepertinya sudah tidak dipakai (`forecast.py` routes tidak import ini lagi), tapi filenya masih ada — perlu diputuskan hapus atau tidak, biar tidak ada 2 sumber kebenaran yang beda soal "bagaimana forecast dihitung".
2. **`backend/app/services/realtime_forecast_service.py`** (`RealtimeForecastService`) — versi yang **aktif dipakai sekarang** (di-import `app/api/routes/forecast.py`). TensorFlow juga, 4 fitur, agregasi per-MENIT (masalah yang dibahas di bagian 4).
3. **`decision_engine/rule_based_engine.py`** — ini BUKAN LSTM (ini rule-based, dibahas di dokumen `pembagian-tugas-24-agustus.md`), disebut di sini cuma buat menegaskan: **LSTM dan RuleBasedEngine masih dua sistem terpisah yang belum saling bicara** (lihat bagian 8).

**Rekomendasi kebersihan kode:** setelah desain di dokumen ini disepakati, `forecast_service.py` (versi 1) sebaiknya dihapus supaya tidak ada dua implementasi forecast yang membingungkan orang berikutnya yang buka kode ini.

---

## 10. Checklist buat Yuli

- [ ] Putuskan: latih dari histori Supabase (`ForecastRepository`) atau gabungan CSV manual (lihat bagian 3) — Supabase lebih disarankan
- [ ] Ganti agregasi dari per-menit (`.dt.floor("min")`) ke per-5-detik (window native `WINDOW_SECONDS`)
- [ ] Eksperimen ulang `SEQUENCE_LENGTH` di skala 5 detik (bagian 6) — jangan asumsikan `30` masih benar
- [ ] Pertimbangkan: latih cuma dari `vehicleCount` + `densityIndex` (data asli) dulu, pisahkan dari `queueLengthVeh`/`queueLengthMEst` (selalu 0) — atau minimal beri catatan jelas di output bahwa 2 fitur itu tidak bisa dipercaya
- [ ] Retrain model (`lstm_model.keras` + `scaler.pkl`) dengan setup baru, commit hasilnya (jangan lupa — `forecasting/outputs/` sekarang kosong, lihat `pembagian-tugas-24-agustus.md` item 2.7)
- [ ] Putuskan nasib `forecast_service.py` (versi lama) — hapus atau biarkan
- [ ] Kalau ada waktu: mulai sambungkan hasil forecast ke `RuleBasedEngine.recommend()` (bagian 8) — kalau tidak sempat sebelum 31 Agustus, dokumentasikan sebagai keterbatasan, jangan diklaim sudah terintegrasi kalau belum

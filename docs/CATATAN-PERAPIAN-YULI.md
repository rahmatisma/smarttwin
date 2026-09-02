# Catatan Perapian, Hasil Audit, dan Tindak Lanjut

**Audit awal:** 1 September 2026  
**Pembaruan P0:** 1 September 2026  
**Jenis pekerjaan:** perapian dokumentasi, audit repository, dan stabilisasi P0

Dokumen ini membantu anggota tim, terutama penanggung jawab audit, membedakan:

1. perubahan yang benar-benar sudah diimplementasikan;
2. hasil pemeriksaan yang masih menjadi pekerjaan;
3. keterbatasan yang sudah diketahui tetapi belum diselesaikan.

Dokumen ini bukan pengganti status resmi proyek. Status seluruh modul tetap
mengacu pada [`STATUS-DAN-SISA-KERJA.md`](STATUS-DAN-SISA-KERJA.md).

## Ringkasan kondisi proyek

SmartTwin sudah kuat sebagai prototype lomba dan demo end-to-end, tetapi belum
production-ready. Estimasi hasil audit adalah sekitar **80–87% untuk kebutuhan
demo** dan **55–65% untuk sistem operasional**. Nilai ini adalah penilaian
kesiapan, bukan hasil perhitungan coverage otomatis.

Fondasi sistem tidak perlu dibuat ulang. Fokus utamanya adalah stabilitas demo,
sinkronisasi kontrak, keamanan backend, reproducibility, dan kualitas input CV.

## Hasil pengujian

### Kondisi saat audit awal

| Area | Hasil awal | Keterangan |
|---|---:|---|
| Backend | 88 lolos, 7 gagal | Empat gagal karena Supabase tidak dapat diakses; sisanya terkait route/fallback traffic |
| Frontend lint | Gagal | 1 error dan 21 warning |
| Frontend build | Gagal | Tiga Google Fonts harus diambil ketika build |
| Frontend test | Tidak tersedia | Belum ada unit, component, atau E2E suite |
| CI/CD | Tidak ditemukan | Belum ada pipeline otomatis |
| Deployment | Belum lengkap | Belum reproducible dari satu konfigurasi deployment |
| Dokumentasi | Tidak sinkron | Klaim hasil test lama tidak sama dengan pemeriksaan aktual |

### Kondisi setelah perbaikan P0

| Pemeriksaan | Hasil | Status |
|---|---:|---|
| Backend unit/local suite | 92 passed, 4 deselected | Lulus |
| Backend integration suite | 4 test tersedia terpisah | Jalankan saat Supabase dapat diakses |
| Frontend lint | 0 error, 21 warning | Lulus; warning menjadi pekerjaan perapian |
| Frontend production build | Berhasil, 13/13 route | Lulus tanpa request Google Fonts |
| Browser end-to-end | Belum dijalankan ulang | Masih terbuka |

Perintah verifikasi:

```powershell
# Unit/local backend
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q

# Integrasi Supabase, dijalankan ketika jaringan dan environment tersedia
.\.venv\Scripts\python.exe -m pytest -q -m integration

# Frontend
Set-Location ..\frontend
npm run lint
npm run build
```

## Perubahan yang sudah diimplementasikan

### README dan indeks dokumentasi

File yang diubah:

- [`../README.md`](../README.md)
- [`README.md`](README.md)

Perubahannya:

- Judul README utama menjadi **SmartTwin — Digital Twin Adaptif untuk Simpang
  Bersinyal**.
- Isi README lama diganti dengan gambaran proyek, alur sistem, modul, teknologi,
  setup, cara menjalankan, pengujian, sumber data, dan aturan kontribusi.
- Indeks dokumentasi diberi tautan menuju catatan ini.

### P0-1 — Regresi respons endpoint traffic

File yang diubah:

- `backend/app/services/traffic_service.py`
- `backend/app/api/routes/traffic.py`
- `backend/tests/test_traffic_api.py`

Hasil:

- Route legacy `/api/traffic/{intersectionId}` dipastikan tetap tersedia.
- Gangguan koneksi Supabase sekarang dibedakan dari data tidak ditemukan.
- Gangguan upstream dikembalikan sebagai HTTP 503, bukan 404 yang menyesatkan.
- Respons 503 tetap memiliki CORS header dan tidak membocorkan exception internal.
- Test kontrak route menggunakan fixture/mock sehingga reproducible tanpa jaringan.

### P0-2 — Fallback endpoint `live-csv`

File yang diubah:

- `backend/app/api/routes/traffic.py`
- `backend/tests/test_api.py`
- `backend/tests/test_traffic_api.py`

Hasil:

- Kegagalan Supabase pada `/api/v1/traffic/live-csv` menjadi HTTP 503 dengan
  pesan aman dan konsisten.
- Jalur sukses dan jalur fallback memiliki automated test tanpa bergantung pada
  isi database aktif.

### P0-3 — Pemisahan unit dan integration test

File yang diubah:

- `backend/pytest.ini`
- `backend/tests/test_database_connection.py`
- `backend/tests/test_database_tables.py`
- `backend/tests/test_supabase_connection.py`
- `backend/tests/test_traffic_state_repository.py`

Hasil:

- Empat test yang benar-benar membutuhkan Supabase diberi marker `integration`.
- `pytest` biasa menjalankan suite lokal yang reproducible.
- Integration test tidak dihapus dan dapat dijalankan eksplisit dengan
  `pytest -m integration`.

### P0-4 — Frontend lint

File yang diubah:

- `frontend/src/components/SharedSignalPanels.tsx`

Hasil:

- `Date.now()` tidak lagi dipanggil sebagai initializer ketika render.
- `npm run lint` berubah dari gagal menjadi lulus tanpa error.
- Masih ada 21 warning non-blocking yang dicatat pada P2.

### P0-5 — Build frontend tanpa ketergantungan Google Fonts

File yang diubah:

- `frontend/src/app/layout.tsx`
- `frontend/src/app/globals.css`

Hasil:

- Import `next/font/google` dihapus.
- Font diganti ke system font stack yang tidak memerlukan download saat build.
- Production build berhasil menghasilkan seluruh 13 route.

## P0 yang masih terbuka

### Verifikasi browser end-to-end

Perlu menjalankan backend, frontend, scenario worker, SUMO, dan sumber data
secara bersamaan. Pemeriksaan minimum:

- angka dashboard cocok dengan `POST /recommendation`;
- status panel cocok dengan `GET /signal/status`;
- kandidat yang dipilih benar-benar memengaruhi simulasi;
- badge sumber SUMO muncul saat cache scenario worker masih segar;
- lifecycle start, pause, resume, dan stop tidak meninggalkan proses SUMO;
- dashboard tetap memberi keadaan error/loading yang jelas jika satu service mati.

## P1 — pengembangan kualitas sistem

### Implementasi P1 pada 1 September 2026

Bagian fondasi yang sudah diselesaikan dan diuji:

- Backend memiliki autentikasi bearer token Supabase yang dapat diwajibkan
  melalui `AUTH_REQUIRED=true`.
- Endpoint mutasi simulation, signal, CCTV upload, traffic notify, dan engine
  test dibatasi untuk role operator/admin/service-role.
- Upload video dibatasi ukuran dan ekstensi; error storage tidak lagi
  membocorkan detail exception eksternal.
- `CORS_ORIGINS` dari environment sekarang benar-benar digunakan aplikasi.
- Endpoint `/api/v1/health/details` menampilkan readiness forecast, engine,
  autentikasi, dan sesi simulation tanpa memaksa koneksi eksternal.
- State SUMO menyimpan scenario, seed, dan waktu mulai; request juga memiliki
  batas durasi dan GUI delay.
- Checkpoint PPO divalidasi terhadap observation space 21 fitur serta action
  space empat lengan sebelum boleh digunakan. Checkpoint tidak kompatibel
  otomatis jatuh ke rule-based.
- Respons forecast menyertakan baseline persistence dan empirical error band
  berdasarkan MAE holdout. Rentang diberi label eksplisit sebagai bukan
  confidence interval statistik.
- `BuiltTrafficState` menyertakan `dataQuality` untuk kelengkapan empat lengan,
  jumlah metric row, dan warning. Nilai ini tidak diklaim sebagai akurasi CV.
- Verifikasi setelah perubahan: backend **96 passed, 4 integration deselected**;
  forecasting sequence test **1 passed**; frontend lint tetap lulus.

Konfigurasi baru:

```env
AUTH_REQUIRED=false
OPERATOR_ROLES=operator,admin,service_role
MAX_VIDEO_UPLOAD_BYTES=1073741824
```

Mode lokal tetap kompatibel dengan `AUTH_REQUIRED=false`. Deployment publik
wajib mengaktifkannya dan memberi `app_metadata.role` yang sesuai pada user.

Pekerjaan yang memerlukan eksperimen/model baru tetap dicatat di bawah dan
tidak dianggap selesai hanya karena guardrail runtime sudah tersedia.

### Computer Vision

Keterbatasan terbesar adalah akurasi crossing rata-rata **48,7%**, terutama saat
padat. Pengembangan yang disarankan:

- fine-tuning YOLO dengan dataset Simpang Pingit;
- evaluasi per kamera, kelas, waktu, dan kepadatan;
- tuning ByteTrack dan pengurangan ID switch/double counting;
- confidence threshold adaptif, kalibrasi perspektif, dan ROI per kamera;
- monitoring frame drop serta kesehatan RTSP;
- dataset ground truth dengan precision, recall, MAE, dan MAPE;
- quality/confidence flag pada setiap `TrafficState`.

### Forecasting LSTM

- Walk-forward validation dan pembanding persistence/moving average/seasonal naive.
- Confidence interval atau uncertainty score.
- Deteksi data drift dan pipeline retraining reproducible.
- Versioning dataset, model, scaler, dan metrik.
- Evaluasi per approach dan kondisi kepadatan.
- Fallback eksplisit ketika model atau input tidak tersedia.

### Decision engine PPO

- PPO jangan menjadi default sebelum fairness per lengan lolos.
- Tambahkan batas minimum/maksimum green dan starvation prevention.
- Uji skenario ekstrem dengan lebih banyak seed dan snapshot.
- Pisahkan reward training dari KPI lalu lintas nyata.
- Tambahkan model registry dan pengecekan kompatibilitas checkpoint.
- Pastikan action/state semantics training sama dengan production.
- Sediakan rollback otomatis ke rule-based dan penjelasan rekomendasi.

### Digital Twin dan SUMO

- Pastikan pilihan skenario benar-benar mengubah simulasi.
- Isi seluruh statistik hanya dari hasil aktual, bukan default.
- Tambahkan job queue dan isolasi run untuk banyak pengguna.
- Persist status job dan hasil simulasi.
- Tambahkan timeout, cancellation, retry, serta cleanup proses.
- Bandingkan baseline dan rekomendasi dengan seed sama.
- Simpan metadata input, seed, model, dan konfigurasi pada hasil.

### Keamanan dan operasional

- Validasi JWT Supabase langsung pada backend.
- Role-based authorization untuk upload, simulation control, signal update, dan
  recommendation testing.
- Proteksi WebSocket dan endpoint notify.
- Rate limiting serta pembatasan ukuran, MIME, dan durasi upload.
- Sanitasi sumber URL/RTSP untuk mengurangi risiko SSRF.
- Audit log, structured logging, dan request/correlation ID.
- Health check terpisah untuk Supabase, HF, forecast, PPO, CV, dan SUMO.
- Rotasi dan dokumentasi secret deployment.

## P2 — kualitas engineering dan perapian

### Implementasi P2 pada 1 September 2026

- Frontend lint dibersihkan dari **21 warning menjadi 0 warning/0 error**.
- FastAPI shutdown dimigrasikan dari `@app.on_event` ke lifespan handler.
- Frontend memiliki test runner bawaan Node dan tiga unit test kontrak pilihan
  simpang/lengan.
- Workflow `.github/workflows/ci.yml` menjalankan backend test, frontend
  lint/test/build, Gitleaks, `pip-audit`, dan `npm audit`.
- Dependency Python dipisahkan menjadi core, simulation, forecast, PPO, dan dev;
  `requirements.txt` tetap menjadi agregator instalasi lengkap.
- README frontend template diganti dengan dokumentasi SmartTwin.
- Deployment backend/frontend ditambahkan melalui Dockerfile dan Compose;
  `.dockerignore` mencegah secret/cache/artefak besar masuk build context.
- Next.js memakai output standalone untuk image runtime yang lebih kecil.
- Model dan dataset card ditambahkan tanpa mengubah atau membesar-besarkan
  hasil evaluasi yang ada.
- Verifikasi lokal: backend **96 passed**, frontend lint bersih, frontend test
  **3 passed**, dan production build **13/13 route**.
- Timeline kamera sekarang otomatis kembali ke detik 0 dan langsung memutar
  seluruh video lagi ketika durasi berakhir; tidak menunggu klik Play/Start.
- Regresi start SUMO diperbaiki: frontend sebelumnya mengirim durasi 86.400
  detik sementara backend menerima maksimal 3.600 detik, sehingga request
  selalu ditolak 422. Durasi kini sesuai kontrak, request paralel dicegah, dan
  UI berhenti menunggu dengan pesan diagnostik setelah timeout 20 detik.
- Reload backend tidak lagi boleh tertahan oleh MJPEG stream tanpa akhir:
  generator berhenti saat client disconnect dan maksimal berumur 30 detik.
  Perintah Uvicorn resmi memakai graceful-shutdown timeout 5 detik agar
  WebSocket/stream lama tidak menahan restart bermenit-menit.
- Clock Digital Twin/SUMO kini mengikuti posisi dan durasi rekaman CCTV. Ketika
  video mengulang ke detik 0, `simulationTimeSeconds` dan fase lampu ikut ke
  awal siklus, sedangkan waktu internal mesin, kendaraan, dan controller SUMO
  tetap berjalan selama backend hidup. Log membedakan `time` (clock CCTV) dan
  `engineTime` (umur internal SUMO). Verifikasi: test sinkronisasi backend
  **5 passed**, frontend test **3 passed**, lint bersih, dan production build
  berhasil menghasilkan **13/13 route**.

Docker Compose belum dapat divalidasi lewat executable lokal karena Docker tidak
terpasang pada mesin audit. Konfigurasinya harus menjalani `docker compose
config` dan smoke test di mesin yang memiliki Docker sebelum disebut siap
deployment.

P2 yang masih terbuka:

- component test dan browser E2E test;
- migration baseline Supabase yang diekspor dari schema aktual;
- service worker scenario dan CV GPU pada Compose;
- smoke test Docker pada mesin yang memiliki Docker;
- audit/arsip script debug root setelah pemilik tim memastikan tidak dipakai.

## Urutan pengerjaan lanjutan

1. Jalankan dan dokumentasikan browser verification end-to-end.
2. Bekukan versi demo dan selaraskan dokumen status resmi.
3. Tambahkan autentikasi backend serta proteksi endpoint sensitif.
4. Bersihkan warning frontend dan tambahkan CI.
5. Stabilkan lifecycle Digital Twin/SUMO.
6. Tingkatkan akurasi CV.
7. Perkuat LSTM dan baru pertimbangkan aktivasi PPO.

## Batas perubahan saat ini

Tahap P0 ini tidak mengubah algoritma CV, bobot/dataset LSTM, environment atau
checkpoint PPO, network/program lampu SUMO, maupun schema/data Supabase.
Perubahan runtime hanya mencakup pemetaan error traffic yang lebih benar,
countdown frontend yang lint-safe, dan font frontend yang dapat dibangun offline.

Temuan audit tidak boleh ditandai selesai sebelum ada implementasi dan hasil
verifikasi. P0 browser verification tetap terbuka sampai seluruh stack diuji.

## Format pencatatan perubahan berikutnya

```text
Tanggal:
Pelaksana:
File yang diubah:
Tujuan:
Ringkasan perubahan:
Cara verifikasi:
Hasil verifikasi:
Status: selesai / perlu tindak lanjut
```

Jika sebuah perubahan menyelesaikan status proyek, perbarui juga
[`STATUS-DAN-SISA-KERJA.md`](STATUS-DAN-SISA-KERJA.md), karena dokumen tersebut
tetap menjadi sumber status resmi tim.

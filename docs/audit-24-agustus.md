# Audit Kelengkapan Sistem — 24 Agustus 2026

Audit menyeluruh seluruh modul, dibaca langsung dari kode (bukan dari checklist roadmap yang sudah ketinggalan). Dijalankan H-7 sebelum tenggat 31 Agustus.

**Metode:** tiap modul dibaca file per file; test dijalankan sungguhan (bukan cuma dilihat nama filenya); endpoint dipanggil nyata untuk memastikan responsnya asli atau stub; bukti run SUMO diperiksa isinya (bukan cuma keberadaan filenya).

---

## Skor per modul

| Modul | Skor | Ringkasan |
|---|---|---|
| **Frontend** (`frontend/`) | **90%** | Paling matang. `mockData` sudah **100% bersih** — target utama roadmap tercapai. Semua 9 komponen dashboard terhubung data asli, `tsc --noEmit` bersih. |
| **CV** (`cv/`) | **78%** | 4 zona kepadatan sudah dikalibrasi interaktif (termasuk utara, yang 17 Agustus belum tersentuh). Garis crossing CCTV_4 belum ada; identitas koridor timur baru sebagian terjawab. |
| **Simulation** (`simulation/`) | **70%** | SUMO/TraCI benar-benar jalan, ada bukti run asli (telemetry per-kendaraan). Tapi `demand_adapter.py` & `tls_controller.py` tidak dipakai runner — runner punya logika duplikat inline. |
| **Backend** (`backend/`) | **60%** | Endpoint traffic inti + WebSocket + integrasi SUMO nyata. Tapi `forecast` & `recommendation` 100% hardcoded, `/live-csv` rusak (500), test suite membusuk. |
| **Decision Engine** (`decision_engine/`) | **55%** | Logika rule-based nyata & sudah diuji ke 2.152 baris data asli. Tapi tidak pakai kontrak data resmi, dan tidak tersambung ke `simulation/`. |
| **Forecasting (LSTM)** | **70% riset / 0% terintegrasi** | PeMS04 & TMU terlatih+terevaluasi (R² 0,879). Tidak pernah masuk sistem live — konsumen fallback ke volume flat. |
| **PPO (RL)** | **0%** | Sesuai keputusan sadar 17 Agustus. Bukan kegagalan. |

## Skor keseluruhan: **~62%**

Bukan rata-rata angka di atas — diturunkan karena masalah terberat bukan di kualitas modul (individual cukup solid), tapi di **sambungan antar-modul**.

---

## Temuan kritis (urut prioritas)

### 1. Rantai end-to-end terputus di dua titik

Roadmap Fase 2 menargetkan "video → deteksi → data → simulasi → rekomendasi jalan end-to-end". Kondisi nyata:

- **CV-zona → decision_engine**: tersambung, tapi lewat jalur CSV ad-hoc dengan istilah Indonesia sendiri (`selatan/barat/timur/simpang_tengah`), bukan kontrak `TrafficState`.
- **decision_engine → simulation**: **tidak tersambung sama sekali.** `run_tls_simulation.py` memakai logika keputusan 2-fase inline miliknya sendiri, bukan hasil `RuleBasedEngine`. Jadi "rekomendasi" yang tampil di simulasi bukan keluaran decision engine yang sudah dibuat.

### 2. Test suite backend sudah membusuk

Dijalankan nyata (`pytest -q`): **24 gagal + 3 error koleksi, hanya 7 lolos** dari 15 file. Yang lolos pun cuma tes koneksi infrastruktur, bukan logika bisnis. Penyebab: mayoritas test masih menguji API arsitektur CSV lama yang sudah diganti (`TrafficService(csv_path=...)`, endpoint `/api/v1/traffic/state`, path legacy `/api/traffic/*`).

**Risiko demo:** kalau juri minta jalankan test, hasilnya merah semua.

### 3. Endpoint yang masih hardcoded

- `forecast_service.py` — 8 angka statis, tidak ada model/logika.
- `recommendation_service.py` — semua konstan (`confidence=0.75`, `source="pending"`), tidak membaca request sama sekali.
- `signal_service.py` — fallback `get_demo_status()` hardcoded; state realtime cuma in-memory, hilang tiap restart (tidak persist ke tabel `signalStatuses` yang sudah ada).

**Risiko demo:** kalau juri tanya "rekomendasi ini asalnya dari mana?", jawaban jujurnya sekarang: angka tetap.

### 4. Endpoint rusak

`GET /api/v1/traffic/live-csv` → **HTTP 500**. Memanggil `builder.buildFromSupabase()` yang sudah tidak ada di `TrafficStateBuilder` versi baru. Juga mengakses `builder.last_matched_video_time` yang tidak pernah di-set.

### 5. Kode yatim & rute mati

- `app/api/routes/health.py` tidak pernah di-`include_router` → `/api/v1/health` 404.
- `legacy_router` (`/api/traffic/*`) juga tidak dipasang → 3 test gagal karenanya.
- `traffic_ingestion_service.py`, `repositories/traffic_state_repository.py`, `intersection_repository.py` — tidak dipakai kode aktif.
- Frontend: `DashboardSkeleton.tsx`, `DashboardLayout.tsx` tidak dipakai; halaman `/digitaltwin` (802 baris) 100% simulasi statis tanpa fetch apa pun.

### 6. Dokumentasi menyesatkan kalau tidak dicek ke kode

- `docs/database.md` **inkonsisten secara internal**: bagian prosa mendeskripsikan `trafficApproachStates`/`trafficLaneMetrics`/`cameraVideos` (sesuai kode), tapi blok `CREATE TABLE` di akhir file memakai nama lama (`approachStates`, `videoUploads`) dan tidak punya DDL untuk `trafficLaneMetrics` sama sekali.
- `cv/vehicle_counter_copy.py:295` masih menulis "BELUM DIPAKAI logika apa pun" untuk crossing, padahal fungsinya aktif dipanggil dan menghasilkan `crossing_simpang.csv`.

### 7. Isu validitas data yang masih menggantung (dari roadmap 17 Agustus)

- **Garis crossing CCTV_4 (timur) belum dikalibrasi** — `CROSSING_LINES` hanya berisi CCTV_1, CCTV_2 (dua garis), CCTV_3. Output CSV tidak punya label `timur`.
- **Identitas koridor timur baru sebagian terjawab.** Crossing CCTV_2 sudah dipecah jadi label `MAGELANG`/`DIPONEGORO` (manual, lewat klik), tapi belum diverifikasi lewat bearing ke network SUMO seperti rencana roadmap. Ada juga sumber ganda belum direkonsiliasi: zona CCTV_4 (label "timur") vs crossing "DIPONEGORO" dari frame CCTV_2.
- **Utara bukan lengan murni.** Zona CCTV_2 berlabel `simpang_tengah` (badan simpang, campuran arah) dipakai sebagai proxy density utara. Konsisten dipakai di CV, backend (`DENSITY_LENGAN_MAP`), dan decision engine (`run_decision.py:29-37`) — tapi artinya keputusan hijau untuk "utara" berbasis kepadatan campuran, bukan ruas Magelang murni.
- Kolom `approach` di Supabase untuk CCTV_3/CCTV_4 pernah terbalik vs pemetaan kode (didokumentasikan di `vehicle_counter_copy.py:874-879`) — perlu dipastikan sudah beres.

---

## Yang sudah kuat (jangan diutak-atik lagi tanpa alasan)

- **Pipeline CV → Database → Dashboard** hidup end-to-end, sudah diuji sampai ke database dengan data nyata.
- **Frontend** lepas total dari mockData, build bersih, semua fallback ditandai jujur di UI (`source: "mock"` → badge "Simulated" amber, bukan disamarkan jadi data asli).
- **SUMO/TraCI** benar-benar berjalan dengan bukti telemetry asli, bukan angka isian.
- **Rule-based engine** logikanya benar (alokasi hijau proporsional + largest-remainder rounding untuk menjamin total tepat 120 detik) dan sudah diuji ke data nyata.
- **Kualitas dokumentasi kode CV** sangat tinggi — riwayat revisi tiap zona/garis ditulis lengkap dengan alasannya. Bagus untuk audit trail lomba.

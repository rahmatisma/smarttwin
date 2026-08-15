# SmartTwin — Roadmap Pengembangan (REVISI DARURAT: 16 Hari)

**Tim:** AkU dan DuA ORang PLEnGer — Politeknik Negeri Lhokseumawe
**Kompetisi:** KMIPN VIII 2026, final di Makassar
**Timeline:** 15–31 Agustus 2026 (~16 hari)
**Status:** REVISI DARURAT — timeline asli 4 minggu (28 hari) terkompresi jadi 16 hari
**Disinkronkan dengan kondisi repo:** 15 Agustus 2026 — sebagian Fase 0 ternyata sudah selesai, lihat penandaan di bawah

> **Kenapa direvisi:** Rencana 3-track paralel (CV, Digital Twin, RL) diasumsikan punya ruang sampai akhir bulan. Ternyata batas waktu riil cuma sampai 31 Agustus — 16 hari dari sekarang, sekitar 57% dari waktu yang direncanakan. Perubahan wajib: **PPO dan LSTM keluar dari scope aktif mulai sekarang**, bukan dievaluasi nanti — checkpoint Minggu 3 yang direncanakan sebelumnya sendiri sudah tidak muat. Yuli dialihkan dari RL & Forecast ke track Web/Backend. Statusnya beda jauh antara keduanya: PPO belum disentuh sama sekali, sementara LSTM sudah menghasilkan dua eksperimen terlatih dan terevaluasi (PeMS04 R² 0,879 dan TMU) — lihat [Status PPO dan LSTM](#status-ppo-dan-lstm).

---

## Pembagian tim (revisi)

| Peran | Fokus | Perubahan dari rencana sebelumnya |
|---|---|---|
| Rahmat — Setup & Digital Twin | Monorepo, SUMO/TraCI, integrasi seluruh modul | Tidak berubah |
| Melpi — Data & CV | Video, anotasi, YOLO+ByteTrack, Traffic State Builder | Tidak berubah — ini jalur kritis tercepat yang harus selesai duluan |
| Yuli — Web & Backend (dialihkan) | `backend/` — FastAPI + PostgreSQL dari nol, lalu sambungkan `frontend/src/app/page.tsx` dari `mockData` ke data asli | **Dialihkan dari RL & Forecast.** Eksperimen LSTM dihentikan setelah PeMS04 & TMU selesai dievaluasi; PPO tidak jadi dikerjakan |

**Alasan realokasi Yuli:** dengan 16 hari, tidak ada slack buat track ke-4 yang risikonya tinggi dan hasilnya tidak pasti (PPO/LSTM). Kapasitas itu dipindah ke bottleneck yang justru pasti terjadi.

**Bottleneck-nya bukan dashboard.** `frontend/` sudah punya 9 komponen (Header, Sidebar, StatsRow, DonutRing, DigitalTwinPanel, CameraFeedPanel, SignalStatusPanel, RecommendationPanel, ForecastChart) dan `simulation/snapshot_dashboard_data.py` sudah menghasilkan data density asli dari SUMO. Yang kosong total justru `backend/` — nol file. Jadi fokus Yuli:

1. **`backend/` FastAPI + PostgreSQL dari nol** — ini satu-satunya modul yang belum punya baris kode sama sekali
2. **Lepas `page.tsx` dari data dummy** — `frontend/src/app/page.tsx:19` masih `import { ... } from "@/lib/mockData"`; ganti ke data asli lewat backend
3. Komponen dashboard baru dibuat hanya kalau memang ada yang kurang, bukan sebagai kerjaan utama

## Status PPO dan LSTM

Keduanya sama-sama di luar scope 16 hari, tapi statusnya **jauh berbeda** — jangan disamakan waktu menyusun laporan atau presentasi.

| Komponen | Status |
|---|---|
| PPO (Decision Engine RL) | Di luar scope, **belum dikerjakan sama sekali**. Tidak ada kode RL di repo — hanya `simulation/requirements-rl.txt` berisi dua nama package (`stable-baselines3`, `sumo-rl`). Tidak ada environment wrapper, tidak ada training script. Tetap dibawakan di laporan sebagai bagian desain sistem dan roadmap lanjutan |
| LSTM (Traffic Forecast) | **Tiga eksperimen dijalankan, dua di antaranya selesai dilatih & dievaluasi.** Pengerjaan dihentikan 15 Agustus 2026 untuk fokus ke scope 16 hari. Kode, data, model, dan seluruh hasil evaluasi ada di repo (`forecasting/`) dan dipakai sebagai bahan laporan teknis |

### Rincian tiga eksperimen LSTM

| Dataset | Apa itu | Status | Hasil utama |
|---|---|---|---|
| **PeMS04** | Sensor jalan tol California (Caltrans), 307 sensor × 3 feature | Dilatih & dievaluasi — **paling lengkap** | **R² 0,879** overall; flow **0,933**, occupancy 0,869, speed 0,839. Test 2.535 sampel |
| **TMU** | Sensor jalan raya Inggris (A174, Teesside), interval 15 menit | Dilatih & dievaluasi | **MAPE speed 2,09%**; MAPE vehicle_count 25,6% (MAE 27,87). Test 444 sampel |
| **Brisbane** | API open data simpang, Brisbane City Council | **Hanya diproses — tidak pernah masuk training** | Tidak ada metrik. Dari 66 baris mentah cuma 5 baris lolos preprocessing (rentang 5 menit), sedangkan modelnya butuh 16 timestep untuk satu sequence |

**PeMS04 porsinya jangan dikecilkan di narasi laporan** — itu satu-satunya eksperimen dengan artefak lengkap (model tersimpan, evaluasi per-sensor dan per-feature, plot actual-vs-predicted).

### Cara membawakannya

**Yang benar:** modelnya bekerja, tapi datanya bukan data lokasi target. R² 0,879 dan MAPE speed 2,09% membuktikan pipeline LSTM-nya jalan. Masalahnya transferabilitas — TMU dan PeMS04 sama-sama sensor ruas jalan menerus di luar negeri, bukan simpang bersinyal Indonesia. Brisbane satu-satunya data simpang asli, dan justru itu yang durasi pengumpulannya tidak cukup.

**Yang salah dan jangan dipakai:** "hasilnya jelek" atau "modelnya gagal". Angkanya ada di repo dan bisa dibuka juri dalam satu menit — klaim itu akan langsung terbantah oleh datanya sendiri.

**Temuan yang dilaporkan:** hambatan utama forecasting untuk simpang target adalah **ketersediaan data lokasi**, bukan arsitektur model. Ini hasil penelitian yang bisa dipertanggungjawabkan.

**Hati-hati saat mengutip angka:** MAE/RMSE PeMS04 dalam satuan ter-scale (bukan kendaraan/jam), dan MAPE tidak dapat dipercaya di dataset ini — `queue_proxy` TMU menghasilkan MAPE 1.008.321.136% karena pembagian mendekati nol. Pakai MAE/RMSE/R² di slide.

**Fallback untuk demo 16 hari:** asumsi volume flat dari `TrafficState` terakhir.

---

## Keputusan kunci

| Area | Keputusan |
|---|---|
| Jenis simpang | Simpang 4 bersinyal |
| Lokasi | Simpang Pingit, Yogyakarta — sudah dikonfirmasi sebagai "Simpang Empat Pingit" oleh Dishub Kota Yogyakarta, dilengkapi ATCS + detektor kendaraan khusus. Ada penelitian akademik (metodologi MKJI) yang sudah memodelkan keempat lengannya — bisa jadi pembanding validasi PKJI 2023 |
| Sumber video | Live feed CCTV ATCS via app agregator, direkam via screen-record |
| Decision Engine | Rule-based — satu-satunya pendekatan untuk 16 hari ini, sesuai proposal sendiri yang menyatakan ini valid untuk tahap awal |

## Kebutuhan data

| # | Data | Jumlah | Sumber | Buat apa |
|---|---|---|---|---|
| 1 | Video mentah | Minimal 20–30 menit, dari sudut yang tersedia di Simpang Pingit | Screen-record app CCTV ATCS | Input pipeline CV |
| 2 | Geometri persimpangan | 1 network | OpenStreetMap + `netconvert` | Bangun model SUMO |
| 3 | Konfigurasi sinyal existing | 3–5 siklus penuh | Rewind-pause dari video rekaman | Baseline fixed-time |
| 4 | Video teranotasi | 5–10 menit, klip pendek | Subset video sendiri + CVAT | Ukur mAP, MOTA/IDF1 |
| 5 | Historis volume kendaraan Simpang Pingit | — | Tidak dikejar lagi di 16 hari ini | LSTM — pencarian data pengganti dihentikan; ketiadaan data historis lokasi target justru jadi temuan yang dilaporkan |

## Stack teknologi

| Komponen | Teknologi |
|---|---|
| Deteksi kendaraan | YOLOv8 (`ultralytics`) + ByteTrack bawaan |
| Simulasi | SUMO + TraCI mentah |
| Backend | FastAPI + WebSocket |
| Frontend | Next.js + Tailwind |
| Database | PostgreSQL |
| Deployment | Docker Compose (native run tetap oke buat demo kalau waktu mepet) |

---

## Roadmap 16 hari

### Fase 0 — Hari 1–3 (15–17 Agustus): Tutup data, mulai setup

Sebagian besar sudah selesai sebelum revisi ini dibuat:

- [x] Rahmat: init monorepo `/frontend` `/backend` `/cv` `/simulation` `/docker` + `/forecasting`
- [x] Rahmat: kontrak data — `docs/data-contract.md`
- [x] Rahmat: export geometri Pingit dari OSM + `netconvert` → `simulation/network/simpang4_pingit.net.xml.gz`
- [x] Rahmat: SUMO network Pingit valid — 34 junction, satu TLS `SIMPANG_CENTER`, 20 koneksi, coverage TLS 100% (`check_tls_coverage.py`). Artefak roundabout dari OSM sudah diratakan jadi satu junction lewat `flatten_roundabout.py`
- [x] Rahmat: TraCI terhubung ke network Pingit dan terverifikasi — `run_intersection.py` (`test_traci.py` hanya diagnostik instalasi, pakai network `cross` bawaan SUMO, bukan network proyek)
- [x] Melpi: CV dasar jalan — `cv/vehicle_counter.py` + `cv/output/smarttwin_traffic_data.csv`
- [x] Yuli: scaffold Next.js dashboard — 9 komponen sesuai mockup, masih pakai `mockData`
- [ ] **Yuli: scaffold FastAPI + skema PostgreSQL** — `backend/` masih kosong total (0 file), ini satu-satunya sisa Fase 0
- [ ] Melpi: rekam semua sudut Simpang Pingit yang tersedia (minimal 2 dari 4 lengan jelas), observasi 3–5 siklus sinyal existing

> **Catatan regresi (15 Agustus).** Centang SUMO/TraCI di atas sempat tidak sesuai kenyataan: `run_intersection.py` memuat `network/simpang4.net.xml.gz` — network **Bandung** dari sebelum pindah lokasi — karena commit `050324f` tanpa sengaja membatalkan migrasi Pingit `811f7c4`. Sudah diperbaiki (`92fbe98`) dan network lamanya dihapus (`37d493b`). Sekarang hanya ada satu network proyek: `simpang4_pingit.net.xml.gz`. Kalau ada file network lain muncul lagi, itu regresi.

### Fase 1 — Hari 4–7 (18–21 Agustus): CV jalan, SUMO matang, backend nyambung

- [ ] Melpi: YOLOv8+ByteTrack jalan di footage Pingit, mulai Traffic State Builder
- [x] Rahmat: TraCI kontrol fase manual terverifikasi di `SIMPANG_CENTER` — program 4 fase, siklus 90 detik (39 hijau / 6 kuning per arah); `setPhase()` dan `setRedYellowGreenState()` dua-duanya terbukti mengubah state lampu
- [ ] Yuli: endpoint FastAPI yang menyajikan `TrafficState` + skeleton WebSocket; komponen dashboard sudah ada, jadi yang dikerjakan sisi penyedia datanya

### Fase 2 — Hari 8–11 (22–25 Agustus): Integrasi MVP

**Goal:** video → deteksi → data → simulasi → rekomendasi jalan end-to-end

- [ ] Traffic State Builder tersambung ke SUMO, demand kendaraan ikut deteksi asli
- [~] Ekstraksi state per lengan dari SUMO — `simulation/snapshot_dashboard_data.py` sudah jalan: simulasi Pingit 300 detik, klasifikasi lengan dari sudut kompas, tulis `outputs/approach_snapshot.json`. Masih snapshot manual sekali jalan, belum aliran data hidup
- [ ] Scenario Generator (heuristik) + Decision Engine rule-based
- [ ] Yuli: `frontend/src/app/page.tsx` lepas dari `@/lib/mockData`, ambil data asli dari backend

**Milestone.**

### Fase 3 — Hari 12–14 (26–28 Agustus): Rule-based final, validasi PKJI

- [ ] Rule-based + Performance Analysis selesai dan teruji
- [ ] Anotasi klip pendek via CVAT, ukur mAP dan MOTA/IDF1
- [ ] Validasi hasil SUMO terhadap PKJI 2023 — cross-check ke penelitian Simpang Pingit yang sudah ada
- [ ] Dashboard mendekati selesai penuh

### Fase 4 — Hari 15–16 (29–31 Agustus): Demo prep

- [ ] Docker Compose kalau sempat — native run tetap oke buat demo
- [ ] Bug fixing, latihan presentasi
- [ ] Siapkan narasi jujur soal PPO dan LSTM — **dua narasi berbeda**: PPO sebagai desain/roadmap lanjutan yang belum dikerjakan, LSTM sebagai eksperimen yang sudah menghasilkan model terlatih dan terevaluasi. Yang kedua dibawakan sebagai hasil penelitian, bukan sebagai kekurangan
- [x] Tarik metrik & plot evaluasi LSTM ke repo — sudah masuk di `forecasting/outputs/` (commit `9148b6c`)
- [ ] Siapkan slide hasil LSTM: pakai R² dan MAE/RMSE, **jangan pakai MAPE** (rusak di dataset ini), dan jangan sebut MAE PeMS04 sebagai satuan kendaraan (angkanya ter-scale)

---

## Rencana kontingensi (lebih agresif — sudah dikompresi maksimal)

Di 16 hari, tidak ada ruang "cek nanti". Kalau ada tanda molor, langsung ambil urutan ini:

1. Scenario Generator jadi 2 opsi saja
2. Visualisasi digital twin: diagram statis + titik posisi kendaraan berkala, bukan animasi penuh
3. WebSocket → polling sederhana
4. Docker Compose → native run satu laptop

**Yang tidak boleh dikorbankan:** pipeline CV → Digital Twin → rekomendasi rule-based end-to-end, dan validasi terhadap PKJI 2023.

**Risiko terbesar:** penyelesaian data di Fase 0 (Melpi). Ini satu-satunya bagian yang bergantung waktu kalender riil, bukan cuma kecepatan coding. Kalau Fase 0 molor lebih dari 3 hari, semua fase berikutnya ikut tergeser.

**Risiko kedua:** `backend/` masih nol file per 15 Agustus. Ini satu-satunya modul yang belum punya kode sama sekali, dan dia duduk persis di antara pipeline (CV/SUMO) dan dashboard yang keduanya sudah jalan. Selama backend belum ada, `page.tsx` tidak bisa lepas dari `mockData`.

---

## Referensi

- **PKJI 2023 resmi:** Direktorat Jenderal Bina Marga, binamarga.pu.go.id — bagian relevan: kapasitas simpang APILL
- **Penelitian pembanding:** "Pemodelan Lalu Lintas pada Simpang Bersinyal di Kota Yogyakarta (Studi Kasus Simpang Pingit)" — kapasitas per lengan sudah dihitung, bisa jadi cross-check validasi PKJI
- **Live CCTV:** App agregator CCTV ATCS Indonesia (iOS/Android), Dishub Kota Yogyakarta
- **Anotasi:** CVAT (cvat.ai, gratis dan open-source)
- **Library:** `ultralytics` (YOLOv8+ByteTrack), `traci`, `sumolib`

---

*Revisi darurat: kompresi dari 28 hari menjadi 16 hari (15–31 Agustus 2026). PPO tidak dikerjakan; eksperimen LSTM dihentikan setelah dilatih & dievaluasi dengan data proxy. Yuli dialihkan ke Web/Backend. Disinkronkan dengan kondisi repo per 15 Agustus 2026.*

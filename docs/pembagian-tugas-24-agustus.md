# Pembagian Tugas H-7 — 24 Agustus 2026

Disusun dari dua sumber: [`docs/audit-24-agustus.md`](audit-24-agustus.md) (kondisi kode per hari ini) dan log commit aktual tiap anggota (`git log`), bukan dari tabel peran `docs/roadmap.md` yang sudah tidak mencerminkan kerja nyata seminggu terakhir. Tenggat: **31 Agustus 2026 — 7 hari lagi.**

> **Update malam 24 Agustus** (setelah `main.py` sempat rusak total & insiden git Yuli/Melpi) — lihat [Update malam](#update-malam-24-agustus--backend-hidup-lagi) di bagian bawah sebelum baca checklist per-orang, situasinya sudah banyak berubah dari draft pagi.

---

## 0. Temuan dari cross-check log commit (baca ini dulu sebelum bagi tugas)

### Peran sudah bergeser dari roadmap

| Orang | Peran di `roadmap.md` | Yang benar-benar dikerjakan (commit 20–24 Agustus) |
|---|---|---|
| **Rahmat** | Setup & Digital Twin (SUMO/TraCI, integrasi modul) | Pipeline CV→CCTV (`cv/vehicle_counter_copy.py`, `cv/process_uploaded_video.py`), mekanisme upload CCTV di backend+frontend (`backend/app/api/routes/cctv.py`, `backend/app/services/cctv_service.py`, `frontend/src/app/cctv/page.tsx`), dan baru mulai kerangka `decision_engine/` (`rule_based_engine.py`, `run_decision.py`) tanggal 23 Agustus |
| **Yuli** | Web & Backend (FastAPI + PostgreSQL, lepas frontend dari mockData) | Backend inti (`traffic_state_builder.py`, `simulation_service.py`, db models, routes `traffic.py`) **plus** integrasi SUMO yang aslinya bukan job dia di roadmap (`simulation/tls_controller.py`, `backend/app/simulation/sumo/sumo_controller.py`, `traffic_state_adapter.py`, `simulation/run_simulation.py`) — hari ini berhasil "traffic state ke sumo dan api nya dah bisa" |
| **Melpi (Santi Melvira)** | Data & CV (video, YOLO+ByteTrack, Traffic State Builder) | Nyaris 100% frontend (`Sidebar.tsx`, `CameraFeedPanel.tsx`, halaman `cctv/account/settings/login/register`) — **tidak ada commit ke `cv/` sejak sebelum 17 Agustus**; hari ini (24 Agustus) baru mulai nyentuh `decision_engine/feed_to_supabase.py` dan `simulation/tls_controller.py`/`run_tls_simulation.py` |

### ⚠️ Risiko yang perlu diselesaikan SEBELUM mulai kerja dari checklist di bawah

1. **Tabrakan Yuli × Melpi hari ini.** Keduanya sama-sama commit ke `simulation/tls_controller.py` dan `simulation/run_tls_simulation.py` pada 24 Agustus, dan Melpi juga baru masuk ke `decision_engine/feed_to_supabase.py`. Kalau tidak disinkronkan, berisiko kerja dobel atau saling menimpa logic penyambungan decision_engine→simulation (ini justru temuan kritis #1 di audit). **Wajib disepakati di awal: siapa yang pegang wiring decision_engine→simulation, siapa yang bantu di bagian lain.**
2. **CV terbengkalai ~1 minggu.** Kalibrasi crossing CCTV_4 (timur) dan identitas koridor timur (temuan audit #7) menggantung karena Melpi — pemilik track CV di roadmap — sudah pindah fokus ke frontend. Tugas ini dialihkan ke Rahmat di bawah karena dia yang paling terakhir menyentuh `vehicle_counter_copy.py`, **kecuali** tim memutuskan Melpi kembali ke CV.
3. **Kemungkinan scope creep — fitur auth.** Halaman login/register/account/settings (buatan Melpi) tidak disebut sama sekali di `roadmap.md` atau di audit sebagai kebutuhan. Perlu diputuskan eksplisit: masuk prioritas demo 31 Agustus, atau ditunda — supaya kapasitas Melpi tidak habis di fitur yang mungkin tidak dinilai juri, sementara ada dead code frontend yang justru dia sendiri yang buat (lihat item Melpi #2 di bawah).

**Rekomendasi: buka dengan sinkronisasi 15 menit di grup/meet pagi ini untuk menyepakati 3 poin di atas, baru jalankan checklist per-orang.**

---

## Peta kepemilikan mulai hari ini (24 Agustus – 31 Agustus)

Ini pembagian **direktori/file**, bukan cuma daftar tugas — biar kalau ada perubahan di luar checklist di bawah, jelas siapa yang harus dihubungi atau siapa yang review.

| Area | Pemilik utama | Bantu / ikut campur | Direktori & file kunci |
|---|---|---|---|
| **CV / computer vision** | **Rahmat** (sementara, lihat Risiko #2) | Melpi kalau balik ke track aslinya | `cv/vehicle_counter_copy.py`, `cv/process_uploaded_video.py`, `cv/output/*` |
| **CCTV pipeline (upload, trigger, tampil)** | **Rahmat** | Yuli (backend service), Melpi (halaman cctv) | `backend/app/api/routes/cctv.py`, `backend/app/services/cctv_service.py`, `backend/app/services/cv_trigger_service.py`, `frontend/src/app/cctv/page.tsx` |
| **Decision Engine (logika rule-based)** | **Rahmat** (pembuat kerangka) | — | `decision_engine/rule_based_engine.py`, `decision_engine/run_decision.py` |
| **Decision Engine → Supabase feed** | **Melpi** (baru mulai 24 Agustus) | Rahmat (review, karena dia pemilik logic-nya) | `decision_engine/feed_to_supabase.py` |
| **Backend inti (traffic state, db, routes)** | **Yuli** | — | `backend/app/pipeline/traffic_state_builder.py`, `backend/app/services/traffic_service.py`, `backend/app/services/simulation_service.py`, `backend/app/api/routes/traffic.py`, `backend/app/db/*` |
| **Integrasi SUMO/TraCI (simulation + backend/app/simulation)** | **Yuli** (paling dalam konteksnya sekarang) | Melpi (baru masuk 24 Agustus — **wajib sinkron dulu**, lihat Risiko #1) | `simulation/tls_controller.py`, `simulation/run_tls_simulation.py`, `simulation/demand_adapter.py`, `backend/app/simulation/sumo/sumo_controller.py`, `backend/app/simulation/sumo/traffic_state_adapter.py` |
| **Network SUMO (`.net.xml.gz`)** | **Rahmat** | — | `simulation/network/*` |
| **Test suite backend** | **Yuli** | — | `backend/tests/*` |
| **Dokumentasi backend/database** | **Yuli** | — | `docs/database.md`, `backend/docs/traffic-state-builder.md` |
| **Frontend — dashboard & komponen inti** | **Melpi** | Rahmat (CameraFeedPanel, terkait CCTV) | `frontend/src/components/Sidebar.tsx`, `frontend/src/components/CameraFeedPanel.tsx`, `frontend/src/app/page.tsx` |
| **Frontend — fitur auth (login/register/account/settings)** | **Melpi** | — (status masih dipertanyakan, lihat Risiko #3) | `frontend/src/app/{login,register,account,settings}/page.tsx` |
| **Frontend — dead code / halaman `/digitaltwin`** | **Melpi** (pembuat, keputusan keep-or-delete di tangan dia) | — | `frontend/src/components/DashboardSkeleton.tsx`, `frontend/src/components/DashboardLayout.tsx`, `frontend/src/app/digitaltwin/page.tsx` |
| **Forecasting (LSTM live)** | **Yuli** (aktif, bukan cuma iseng — lihat catatan) | — | `backend/app/services/forecast_service.py`, `backend/app/models/lstm_forecast.py`, `backend/app/schemas/forecast.py`, `backend/app/api/routes/forecast.py`, `forecasting/server.py` (training) |

> **Update: ini bukan lagi commit iseng.** Malam 24 Agustus Yuli mendorong fitur ini jadi cukup jauh — `forecast_service.py` & `lstm_forecast.py` ditulis ulang total (PyTorch, bukan TensorFlow lagi), plus `forecasting/server.py` (1796 baris) buat training model barunya dari `percobaan_logic_simpang.csv`. Ini **bertentangan langsung** dengan keputusan `CLAUDE.md`/`roadmap.md` bahwa LSTM dihentikan 15 Agustus supaya fokus scope 16 hari. **Perlu obrolan eksplisit dengan Yuli**: apakah ini disetujui jadi fitur demo (dan berarti prioritas #2.1–2.6 di bawah harus digeser), atau dihentikan lagi supaya fokus kembali ke yang audit tandai kritis. Kabar baiknya: fitur ini sekarang **tidak lagi memblokir orang lain** (lihat Update malam) — jadi tidak darurat, tapi tetap perlu keputusan sebelum Yuli investasi waktu lebih jauh.

---

## 1. Rahmat (kamu)

### 1.1 [SELESAI 24 Agustus] Validitas data CV — temuan audit #7
- [x] ~~Kalibrasi garis crossing CCTV_4 (timur)~~ — **tidak diperlukan.** Diklarifikasi langsung ke Rahmat: sudut kamera CCTV_4 tidak menangkap crossing dari arah Jl. Diponegoro dengan jelas; garis `DIPONEGORO` milik CCTV_2 sudah jadi sumber sah untuk crossing lengan timur, dan sudah benar diwire di `backend/app/pipeline/cv_csv_bridge.py` (`CROSS_LABEL_MAP`)
- [x] Rekonsiliasi sumber ganda (zona CCTV_4 vs crossing CCTV_2 DIPONEGORO) — **bukan konflik.** Dua metrik berbeda: zona CCTV_4 = density (`DENSITY_LENGAN_MAP["timur"] = "east"`), crossing CCTV_2 DIPONEGORO = volume (`CROSS_LABEL_MAP["DIPONEGORO"] = "east"`). Sudah konsisten di kode
- [x] Kolom `approach` Supabase CCTV_3/CCTV_4 — **diverifikasi langsung ke database (read-only query):** `CCTV_3 → west`, `CCTV_4 → east`. Sudah benar, bug lama sudah tidak ada
- [x] Verifikasi Magelang vs Diponegoro lewat bearing ke network SUMO — **dilakukan** lewat `simulation/verify_corridor_bearing.py` (baca geometri `.net.xml.gz` langsung, tanpa perlu venv/sumolib). Hasil: Jalan Diponegoro bearing 74.5°–93.0° (timur), Jalan Magelang bearing 351.8°–6.3° (utara) — **cocok persis** dengan `CROSS_LABEL_MAP`. Skrip disimpan permanen sebagai bukti audit trail
- [x] Komentar basi di `vehicle_counter_copy.py:295` — diperbaiki, sekarang menjelaskan kenapa CCTV_4 sengaja tidak punya garis crossing sendiri

### 1.2 [SELESAI 24 Agustus] Decision Engine — logika inti direfactor ke kontrak resmi
- [x] `rule_based_engine.py` di-refactor total (bukan cuma adapter tipis) — `decide()` sekarang terima `TrafficState` dan hasilkan `SignalRecommendation` asli dari `backend/app/schemas/`, bukan dict Indonesia (`timur`/`total`) lagi. **Catatan:** target-nya kontrak yang HIDUP di backend, BUKAN `docs/data-contract.md` — versi di dokumen itu (`ScenarioResult`, `chosen_scenario`) ternyata tidak pernah diimplementasikan sama sekali, tidak ada konsumennya
- [x] `run_decision.py` diupdate mengikuti signature baru — sudah dites jalan penuh ke 538 baris data asli (`percobaan_logic_simpang.csv`), hasilnya masuk akal
- [x] **Efek berantai ke file Melpi:** perubahan skema `signal_decisions.csv` (dari 4-baris-per-timestamp jadi 1 rekomendasi per timestamp) bikin `feed_to_supabase.py::feed_signal_decisions()` ikut rusak (baca kolom lama `lengan`/`skor`/`prioritas`/`total_kend`). Sudah diperbaiki mengikuti skema baru — **ternyata selaras**, fungsi itu sebelumnya sudah menghitung sendiri `confidence`/`delay_pct` secara manual dari `skor`/`prioritas` menuju bentuk yang sama persis dengan `SignalRecommendation`, sekarang tidak perlu dihitung ulang lagi (pass-through langsung)
- [ ] **Belum dikerjakan di sesi ini:** wiring `run_tls_simulation.py` (Yuli, task 2.1) — `create_phase_plan()` di sana perlu diganti dari logika inline max-queue jadi panggil `RuleBasedEngine.decide()`. Bentuknya sudah cocok (satu `recommended_phase` + durasi per panggilan, sama seperti pola `create_phase_plan()` sekarang) — **kabari Yuli skema barunya sebelum dia mulai wiring**

### 1.2b [SELESAI 24 Agustus malam] Service_role key ter-hardcode di `decision_engine/feed_to_supabase.py`
- [x] Ditemukan saat mengerjakan 1.2: `feed_to_supabase.py` (commit Melpi hari ini) punya Supabase **service_role key** (bypass RLS) ter-hardcode langsung di kode, dan commit "perbaikan" berikutnya cuma menyamarkannya jadi default value `os.getenv(..., "<key yang sama>")` — key-nya tetap hidup di kode
- [x] Kode sudah diperbaiki: sekarang WAJIB dari environment variable (`SUPABASE_SERVICE_ROLE_KEY`, disamakan namanya dengan `backend/.env`), tidak ada fallback hardcode lagi
- [x] **Key sudah di-rotate Rahmat di Supabase Dashboard, dan diverifikasi langsung** (query test ke tabel `cameras` berhasil pakai key baru). Key lama otomatis tidak berlaku lagi. Cuma ada satu `.env` di seluruh repo (`backend/.env`), jadi tidak ada tempat lain yang perlu diupdate — item ini **tuntas sepenuhnya**

### 1.3 [SELESAI 24 Agustus] Regresi network SUMO — diperiksa & dibersihkan
- [x] Diperiksa asal-usul `simpang44_pingit.net.xml.gz`, `simpang44_baru.net.xml`, `simpang4.xml`, `simpang4_pingit.add.xml` yang masuk dari commit Melpi hari ini ("sumocuy"). **Hasil: bukan perbaikan TLS seperti yang diduga awalnya** — diff level baris (`gzip` + `difflib`) menunjukkan `simpang44_pingit.net.xml.gz` **byte-identik** dengan `simpang4_pingit.net.xml.gz` kanonik, cuma beda 3 baris (timestamp generate netconvert & nama file di komentar, keduanya kosmetik). Program TLS `SIMPANG_CENTER` (4 fase, 39/6/39/6 detik, satu grup hijau per fase — pola yang dikira baru) ternyata **sudah ada di network kanonik sejak sebelum hari ini** juga (didokumentasikan di `roadmap.md` sekitar 17-21 Agustus)
- [x] `simpang4_pingit.sumocfg` dikembalikan ke `net-file="simpang4_pingit.net.xml.gz"` (network kanonik) — sempat menunjuk ke file duplikat bertypo
- [x] 6 file duplikat/scratch dihapus (`git rm`, fully recoverable dari history): `simpang44_pingit.net.xml.gz`, `simpang44_pingit.net.xml.gz.xml`, `simpang44_baru.net.xml`, `simpang4.xml`, `simpang4_pingit.add.xml`, `simpang4_pingit.sumocfg.bak` — semua terverifikasi tidak dipakai script mana pun dan tidak berisi apa pun yang beda dari network kanonik
- [x] `simulation/network/` sekarang cuma berisi 2 file: `simpang4_pingit.net.xml.gz` dan `simpang4_pingit.sumocfg` — sesuai kebijakan "satu network project" di CLAUDE.md. XML sumocfg divalidasi well-formed, route file yang dirujuk (`demo_mobil.rou.xml`) dikonfirmasi ada
- [x] **Divalidasi dengan simulasi jalan sungguhan** — Rahmat menjalankan `python run_intersection.py` di mesinnya sendiri (venv siap): TraCI konek, `Traffic light ID: SIMPANG_CENTER` terbaca, `State RYG: GGGggrrrrrrrrrrrrrrr` (fase 0, cocok persis dengan yang diverifikasi tadi), `setPhase()` berhasil. **Catatan:** `run_intersection.py` load `network/simpang4_pingit.net.xml.gz` langsung (bukan lewat `simpang4_pingit.sumocfg`, tidak ada spawn kendaraan) — jadi ini validasi network file-nya sendiri, bukan smoke-test route/config lengkap. Kalau mau validasi `sumocfg` secara utuh (dengan route file), perlu jalankan `run_tls_simulation.py` atau `run_simulation.py` (punya Yuli) terpisah

---

## 2. Yuli

### 2.1 [KRITIS, MASIH BELUM DIKERJAKAN per malam 24 Agustus] Sambungkan decision_engine → simulation — temuan audit #1
- [ ] `run_tls_simulation.py` saat ini pakai logika 2-fase inline sendiri, **bukan** output `RuleBasedEngine` milik Rahmat — ganti supaya rekomendasi yang tampil di simulasi benar-benar hasil decision engine
- [ ] Konsolidasi `demand_adapter.py` & `tls_controller.py` yang tidak dipakai runner (logika duplikat inline) — kamu paling dalam konteksnya karena sudah pegang `sumo_controller.py` & `traffic_state_adapter.py`
- [ ] **Koordinasi dengan Melpi** — dia juga commit ke file yang sama hari ini, samakan dulu siapa ngerjain bagian mana
- **Verifikasi malam 24 Agustus:** dicek `simulation/run_tls_simulation.py` — belum ada satu pun referensi ke `RuleBasedEngine`/`rule_based_engine`. Sepanjang sore-malam ini Yuli fokus penuh ke fitur forecast LSTM (lihat catatan Forecasting di atas) dan refactor `traffic_state_builder.py`/`sumo_controller.py`/`traffic.py` routes (626 baris berubah) — item ini belum tersentuh sama sekali. **Ini masih jadi risiko demo #1 terbesar** kalau tidak dikerjakan sebelum 31 Agustus

### 2.2 [KRITIS, MASIH BELUM] Test suite backend — temuan audit #2
- [ ] **Dicek ulang malam 24 Agustus (`pytest -q --continue-on-collection-errors`):** hasilnya **persis sama** dengan audit pagi — 24 gagal + 7 lolos + 3 error koleksi. Refactor besar `traffic_state_builder.py`/`traffic.py` (626 baris) malam ini **tidak menyentuh compatibility test sama sekali**
- [ ] Error koleksi masih ada 3: `tests/test_full_traffic_ingestion.py`, `tests/test_traffic_bulk_repository.py`, `tests/test_traffic_state_repository.py` — semuanya gagal di baris import `from backend.app.repositories...` (harusnya `from app.repositories...`, tanpa prefix `backend.`)
- [ ] **Risiko demo:** kalau juri minta jalankan test, hasilnya merah semua — masih berlaku persis seperti pagi

### 2.3 [SELESAI, terverifikasi malam 24 Agustus] Endpoint rusak — temuan audit #4
- [x] `GET /api/v1/traffic/live-csv` — **dites langsung pakai TestClient, sekarang 200** dengan data asli (`trafficStateId`, 4 approach lengkap). `buildFromSupabase()` sekarang ADA di `TrafficStateBuilder` (baris 1097) dan dipanggil dengan benar. `last_matched_video_time` sudah tidak direferensikan sama sekali lagi. Ini bonus dari refactor besar Yuli malam ini, bukan hasil kerja sengaja menutup item ini — tapi hasilnya genuinely fixed

### 2.4 [SEBAGIAN SELESAI] Endpoint hardcoded — temuan audit #3
- [x] `forecast_service.py` — **tidak hardcoded lagi.** Ditulis ulang total malam ini jadi pipeline LSTM asli (history tracking → fitur → `forecaster.predict()`) — bukan lagi 8 angka statis. Catatan: modelnya sendiri belum ada file terlatih di repo (lihat catatan Forecasting di Peta Kepemilikan), jadi endpoint akan balik `None`/404 sampai modelnya siap, tapi itu beda soal dari "hardcoded"
- [ ] `recommendation_service.py` — **dicek ulang, masih persis sama**: baris 30 `confidence=0.75`, baris 43 `source="pending"`. Belum disambungkan ke `RuleBasedEngine` yang sudah dibuat Rahmat (lihat 1.2) — padahal bentuknya sudah cocok, tinggal panggil
- [ ] `signal_service.py` — **dicek ulang, `get_demo_status()` masih ada** (baris 38), belum diverifikasi apa persist-nya ke `signalStatuses` sudah jalan
- [ ] **Risiko demo:** untuk `/recommendation` masih berlaku — angka tetap. Untuk `/forecast` sudah tidak lagi (tapi belum punya model buat dijawab beneran)

### 2.5 [SEBAGIAN SELESAI] Rute mati — temuan audit #5
- [x] `app/api/routes/health.py` — **sudah di-`include_router`** (main.py baris 9 & 43), dites langsung `GET /api/v1/health` → 200 `{"status":"ok","service":"smarttwin-backend"}`. Selesai
- [ ] `legacy_router` (`/api/traffic/*`) — **dicek ulang, masih TIDAK dipasang** di `main.py` (didefinisikan di `traffic.py` tapi tidak ada `app.include_router(legacy_router)` di mana pun)
- [ ] Kode yatim `traffic_ingestion_service.py` — **dicek ulang, masih tidak direferensikan** oleh kode aktif mana pun. Belum diputuskan hapus atau sambungkan

### 2.6 Dokumentasi — temuan audit #6
- [ ] `docs/database.md` — **dicek ulang, masih inkonsisten**: `CREATE TABLE "videoUploads"` (baris 1465) dan `CREATE TABLE "approachStates"` (baris 1605) masih pakai nama tabel lama, belum disatukan dengan prosa yang sudah pakai nama baru

---

## 3. Melpi (Santi Melvira)

> **Update malam:** Risiko #1 (tabrakan Yuli×Melpi di `tls_controller.py`/`run_tls_simulation.py`/`feed_to_supabase.py`) **benar-benar kejadian** — bukan cuma potensi. Melpi & Yuli sama-sama edit `main.py`/`forecast.py` secara paralel malam ini, ketemu merge conflict, dan proses resolusinya sempat bikin ~2 jam kehabisan waktu buat insiden git (termasuk file `backend.zip` 2,23 GB ke-commit tidak sengaja lewat `git add -A`, bikin push gagal berulang). Sudah beres (lihat Update malam di bawah), tapi **item 3.1–3.4 di bawah ini otomatis mundur** karena kapasitas Melpi habis buat itu, bukan buat checklist aslinya. Perlu direncanakan ulang kapan dia bisa balik ke ini.

### 3.1 [TERJADI, BUKAN TERSELESAIKAN] Sinkronisasi dulu (lihat Risiko #1)
- [ ] Klarifikasi dengan Yuli: siapa pegang wiring `tls_controller.py`/`run_tls_simulation.py`/`decision_engine/feed_to_supabase.py` — kalian berdua sama-sama commit ke situ hari ini
- **Update malam:** tabrakannya beneran kejadian (lihat catatan di atas), tapi resolusinya cuma soal "ambil versi siapa buat 2 file yang conflict" (main.py/forecast.py, dimenangkan versi Rahmat) — **bukan** kesepakatan pembagian tugas yang sebenarnya. Pertanyaan "siapa pegang wiring decision_engine→simulation" (item 2.1) di atas **masih belum terjawab**, masih 0% dikerjakan siapa pun

### 3.2 [DICEK ULANG, MASIH BELUM] Dead code frontend — temuan audit #5 (kamu pembuatnya, paling paham keep-or-delete)
- [ ] `DashboardSkeleton.tsx` (`frontend/src/components/`) — **dicek ulang malam ini, masih tidak diimpor dari mana pun.** Catatan: sekarang ada FUNGSI LOKAL berbeda dengan nama sama persis `DashboardSkeleton` di dalam `frontend/src/app/page.tsx` (baris 173) yang dipakai aktif — itu bukan file lama ini, jangan sampai ketuker pas mau hapus
- [ ] `DashboardLayout.tsx` — dicek ulang, masih tidak diimpor dari mana pun sama sekali
- [ ] Halaman `/digitaltwin` — dicek ulang, masih 0 baris yang mengandung `fetch`/`useEffect`/`await`, tetap 100% statis

### 3.3 [BELUM DIPUTUSKAN] Keputusan scope — fitur auth (lihat Risiko #3)
- [ ] Diskusikan dengan tim: halaman login/register/account/settings masuk prioritas demo 31 Agustus atau tidak? Tidak ada di `roadmap.md` maupun audit sebagai requirement
- [ ] Kalau **tidak** prioritas: alihkan waktu ke item 3.2 di atas atau kembali pegang CV (lihat 3.4)
- **Verifikasi malam:** halaman-halaman itu (`app/login`, `app/register`, `app/account`) masih ada, terakhir disentuh 21 Agustus (tidak ada progres/keputusan baru malam ini)

### 3.4 Opsional — kembali ke CV (kalau kapasitas ada & tim sepakat)
- [ ] Track CV (item 1.1 di atas) sudah 1 minggu tidak disentuh oleh pemilik aslinya. Kalau Melpi mau ambil balik, koordinasikan dengan Rahmat supaya tidak dobel kerja di `vehicle_counter_copy.py`

---

## 4. Yang sudah kuat — jangan diutak-atik tanpa alasan

(disalin dari `docs/audit-24-agustus.md`, berlaku untuk semua orang)

- Pipeline CV → Database → Dashboard hidup end-to-end dengan data nyata
- Frontend lepas total dari `mockData`, build bersih, fallback ditandai jujur (`source: "mock"` → badge "Simulated")
- SUMO/TraCI berjalan dengan bukti telemetry asli
- Rule-based engine (alokasi hijau proporsional + largest-remainder rounding, total tepat 120 detik) sudah diuji ke data nyata
- Dokumentasi kode CV — riwayat revisi tiap zona/garis lengkap dengan alasannya, bagus untuk audit trail lomba

---

## 5. Checklist koordinasi (isi saat rapat, bukan solo)

- [ ] Sudah sepakat siapa pegang wiring decision_engine→simulation (Yuli / Melpi / berdua dibagi per fungsi)? **Masih terbuka per malam 24 Agustus — belum dikerjakan siapa pun**
- [ ] Sudah diputuskan status fitur auth (in-scope / ditunda)?
- [ ] Sudah diputuskan siapa lanjut kalibrasi CV CCTV_4 & identitas koridor timur (Rahmat / Melpi balik)? **Selesai — lihat 1.1, tidak perlu dikerjakan siapa pun, sudah terverifikasi cukup**
- [x] Sudah dicek file network baru (`simpang44_*`) — aset atau regresi? **Selesai — regresi/duplikat, sudah dihapus (1.3)**
- [ ] **Baru:** apakah fitur forecast LSTM (Yuli) disetujui in-scope demo 31 Agustus, atau dihentikan lagi? (lihat catatan Forecasting di Peta Kepemilikan)

---

## Update malam 24 Agustus — backend hidup lagi

Ringkasan padat buat siapa pun yang baca dokumen ini besok pagi:

**Yang terjadi malam ini (setelah checklist awal di atas ditulis):**
1. `backend/app/main.py` sempat rusak **total** dua kali beruntun — pertama karena merge Yuli yang bentrok (dua `FastAPI()`, import salah path), lalu setelah itu diperbaiki, ketahuan `forecast_service.py` juga gagal start karena `LSTMForecaster` di-load langsung saat import (butuh tensorflow yang belum terinstall + file model yang belum ada). Sudah diperbaiki bertahap oleh Rahmat (dengan konfirmasi eksplisit tiap langkah, bukan otomatis).
2. Yuli & Melpi paralel ngerjain `main.py`/`forecast.py` di malam yang sama → merge conflict → proses resolusinya sempat melenceng jadi insiden git: **file `backend.zip` (2,23 GB) ke-commit tidak sengaja** lewat `git add -A`, bikin `git push` gagal berulang (HTTP 408 timeout). Sudah dibersihkan lewat `git reset --soft origin/main` (buang commit bermasalah, kode asli tidak hilang). `.gitignore` ditambah aturan `*.zip` biar tidak kejadian lagi.
3. Yuli lanjut nulis ulang fitur forecast LSTM total malam ini (PyTorch, bukan TensorFlow) — **dan bikin loading model-nya lazy**, jadi walau file model `.pt` masih belum ada di repo, backend **tidak lagi crash** pas start. Ini perbaikan penting yang tidak diminta siapa pun tapi menyelesaikan masalah blocking yang sempat berlarut-larut.

**Status backend per malam ini:** ✅ **`python -c "from app.main import app"` berhasil, 11 routes terdaftar.** Backend bisa dijalankan lagi oleh siapa pun di tim.

**Dicek ulang satu-satu malam ini (bukan asumsi — dijalankan test/curl/grep beneran), ternyata campuran:**

Ikut kebenerin (efek samping refactor besar Yuli, bukan dikerjakan sengaja):
- ✅ 2.3 `/api/v1/traffic/live-csv` — sekarang 200 dengan data asli (dulu 500)
- ✅ 2.4 `forecast_service.py` — bukan lagi 8 angka statis, sekarang pipeline LSTM asli (walau modelnya sendiri belum ada file terlatih)
- ✅ 2.5 (sebagian) `health.py` — sekarang ter-`include_router`, `/api/v1/health` sudah 200

Masih persis sama seperti audit pagi, belum tersentuh:
- ❌ 2.1 (wiring decision_engine→simulation) — **masih 0%**, `run_tls_simulation.py` belum tersentuh sama sekali. **Ini risiko demo terbesar yang tersisa**
- ❌ 2.2 (test suite) — **masih 24 gagal, 7 lolos, 3 error koleksi**, angka identik dengan audit pagi meski 626 baris kode di sekitarnya berubah
- ❌ 2.4 (sebagian) `recommendation_service.py`/`signal_service.py` — masih hardcoded persis sama
- ❌ 2.5 (sebagian) `legacy_router` masih tidak dipasang, kode yatim `traffic_ingestion_service.py` masih menggantung
- ❌ 2.6 (docs/database.md) — masih inkonsisten, belum disentuh
- ❌ 3.1–3.4 Melpi — **mundur total**, kapasitasnya habis buat insiden git, bukan buat checklist aslinya (dead code frontend & keputusan fitur auth masih persis sama seperti pagi)

**Rekomendasi paling mendesak buat besok:** sebelum lanjut fitur baru apa pun, putuskan dulu di rapat: (a) status forecast LSTM in-scope atau tidak, (b) siapa mengerjakan 2.1 (paling kritis buat demo, masih 0% — satu-satunya item KRITIS yang belum ada kemajuan sama sekali). Waktu tersisa 6 hari.

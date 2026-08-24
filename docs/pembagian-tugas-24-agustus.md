# Pembagian Tugas H-7 — 24 Agustus 2026

Disusun dari dua sumber: [`docs/audit-24-agustus.md`](audit-24-agustus.md) (kondisi kode per hari ini) dan log commit aktual tiap anggota (`git log`), bukan dari tabel peran `docs/roadmap.md` yang sudah tidak mencerminkan kerja nyata seminggu terakhir. Tenggat: **31 Agustus 2026 — 7 hari lagi.**

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
| **Backend inti (traffic state, db, routes)** | **Yuli** (historis) → **Rahmat** untuk `recommendation_service.py`/legacy_router/kode yatim mulai 25 Agustus | — | `backend/app/pipeline/traffic_state_builder.py`, `backend/app/services/traffic_service.py`, `backend/app/services/simulation_service.py`, `backend/app/services/recommendation_service.py`, `backend/app/api/routes/traffic.py`, `backend/app/db/*` |
| **Integrasi SUMO/TraCI (simulation + backend/app/simulation)** | **Yuli** (paling dalam konteksnya sekarang) | Melpi (baru masuk 24 Agustus — **wajib sinkron dulu**, lihat Risiko #1) | `simulation/tls_controller.py`, `simulation/run_tls_simulation.py`, `simulation/demand_adapter.py`, `backend/app/simulation/sumo/sumo_controller.py`, `backend/app/simulation/sumo/traffic_state_adapter.py` |
| **Network SUMO (`.net.xml.gz`)** | **Rahmat** | — | `simulation/network/*` |
| **Test suite backend** | **Rahmat** mulai 25 Agustus (dipindah dari Yuli, lihat catatan di section 2) | — | `backend/tests/*` |
| **Dokumentasi backend/database** | **Rahmat** mulai 25 Agustus (dipindah dari Yuli) | — | `docs/database.md`, `backend/docs/traffic-state-builder.md` |
| **Forecasting (LSTM) — Fase 1 (2 fitur asli)** | **Yuli** (dedicated mulai 25 Agustus) | — | `forecasting/`, `backend/app/services/realtime_forecast_service.py` |
| **CV — logika antrean baru (Fase 2 LSTM)** | **Rahmat** | — | `cv/vehicle_counter_copy.py`, `cv/output/*` — lihat `docs/rencana-lstm-forecast.md` bagian 2.1 |
| **Frontend — dashboard & komponen inti** | **Melpi** | Rahmat (CameraFeedPanel, terkait CCTV) | `frontend/src/components/Sidebar.tsx`, `frontend/src/components/CameraFeedPanel.tsx`, `frontend/src/app/page.tsx` |
| **Frontend — fitur auth (login/register/account/settings)** | **Melpi** | — (status masih dipertanyakan, lihat Risiko #3) | `frontend/src/app/{login,register,account,settings}/page.tsx` |
| **Frontend — dead code / halaman `/digitaltwin`** | **Melpi** (pembuat, keputusan keep-or-delete di tangan dia) | — | `frontend/src/components/DashboardSkeleton.tsx`, `frontend/src/components/DashboardLayout.tsx`, `frontend/src/app/digitaltwin/page.tsx` |
| **Forecasting (LSTM)** | — (tidak ada di roadmap sekarang, lihat catatan) | Yuli masih commit "train lstm" 24 Agustus meski status resmi "dihentikan" | `forecasting/` |

> Catatan Forecasting: `CLAUDE.md` & `roadmap.md` bilang LSTM dihentikan 15 Agustus supaya fokus 16 hari, tapi Yuli tetap ada commit "modified traffic state builder and train lstm" hari ini. Perlu diklarifikasi apakah ini kerja sampingan di luar jam prioritas atau ada rencana yang belum dikomunikasikan ke tim — kalau memang masih jalan, waktunya bersaing langsung dengan item 2.1–2.6 di bawah yang menurut audit lebih kritis untuk demo.

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
- [x] **Update 25 Agustus:** wiring `run_tls_simulation.py` **akhirnya dikerjakan Yuli** (lihat 2.1) — tapi dia menulis ulang total `rule_based_engine.py` jadi versinya sendiri (`.recommend()`, bukan `.decide()` yang Rahmat buat), jadi bukan cuma "dipanggil", tapi "diganti". Sisi kode Rahmat di item ini (kontrak resmi) sudah tidak berlaku lagi — kalau perlu dipakai lagi butuh keputusan tim, bukan tanggung jawab Rahmat lanjut kejar

### 1.2b [TEMUAN BARU, SUDAH DIPERBAIKI] Service_role key ter-hardcode di `decision_engine/feed_to_supabase.py`
- [x] Ditemukan saat mengerjakan 1.2: `feed_to_supabase.py` (commit Melpi hari ini) punya Supabase **service_role key** (bypass RLS) ter-hardcode langsung di kode, dan commit "perbaikan" berikutnya cuma menyamarkannya jadi default value `os.getenv(..., "<key yang sama>")` — key-nya tetap hidup di kode
- [x] Kode sudah diperbaiki: sekarang WAJIB dari environment variable (`SUPABASE_SERVICE_ROLE_KEY`, disamakan namanya dengan `backend/.env`), tidak ada fallback hardcode lagi
- [x] **Sudah dilakukan manual oleh Rahmat:** rotate service_role key di Supabase Dashboard → Settings → API. Key lama yang bocor ke git history (`69e37bf`, `c6e5a65`) sudah tidak berlaku lagi

### 1.3 [SELESAI 24 Agustus] Regresi network SUMO — diperiksa & dibersihkan
- [x] Diperiksa asal-usul `simpang44_pingit.net.xml.gz`, `simpang44_baru.net.xml`, `simpang4.xml`, `simpang4_pingit.add.xml` yang masuk dari commit Melpi hari ini ("sumocuy"). **Hasil: bukan perbaikan TLS seperti yang diduga awalnya** — diff level baris (`gzip` + `difflib`) menunjukkan `simpang44_pingit.net.xml.gz` **byte-identik** dengan `simpang4_pingit.net.xml.gz` kanonik, cuma beda 3 baris (timestamp generate netconvert & nama file di komentar, keduanya kosmetik). Program TLS `SIMPANG_CENTER` (4 fase, 39/6/39/6 detik, satu grup hijau per fase — pola yang dikira baru) ternyata **sudah ada di network kanonik sejak sebelum hari ini** juga (didokumentasikan di `roadmap.md` sekitar 17-21 Agustus)
- [x] `simpang4_pingit.sumocfg` dikembalikan ke `net-file="simpang4_pingit.net.xml.gz"` (network kanonik) — sempat menunjuk ke file duplikat bertypo
- [x] 6 file duplikat/scratch dihapus (`git rm`, fully recoverable dari history): `simpang44_pingit.net.xml.gz`, `simpang44_pingit.net.xml.gz.xml`, `simpang44_baru.net.xml`, `simpang4.xml`, `simpang4_pingit.add.xml`, `simpang4_pingit.sumocfg.bak` — semua terverifikasi tidak dipakai script mana pun dan tidak berisi apa pun yang beda dari network kanonik
- [x] `simulation/network/` sekarang cuma berisi 2 file: `simpang4_pingit.net.xml.gz` dan `simpang4_pingit.sumocfg` — sesuai kebijakan "satu network project" di CLAUDE.md. XML sumocfg divalidasi well-formed, route file yang dirujuk (`demo_mobil.rou.xml`) dikonfirmasi ada
- [x] **Divalidasi dengan simulasi jalan sungguhan** — Rahmat menjalankan `python run_intersection.py` di mesinnya sendiri (venv siap): TraCI konek, `Traffic light ID: SIMPANG_CENTER` terbaca, `State RYG: GGGggrrrrrrrrrrrrrrr` (fase 0, cocok persis dengan yang diverifikasi tadi), `setPhase()` berhasil. **Catatan:** `run_intersection.py` load `network/simpang4_pingit.net.xml.gz` langsung (bukan lewat `simpang4_pingit.sumocfg`, tidak ada spawn kendaraan) — jadi ini validasi network file-nya sendiri, bukan smoke-test route/config lengkap. Kalau mau validasi `sumocfg` secara utuh (dengan route file), perlu jalankan `run_tls_simulation.py` atau `run_simulation.py` (punya Yuli) terpisah

---

## 2. Yuli (LSTM saja mulai 25 Agustus — lihat catatan pemecahan tugas di bawah)

> **Update 25 Agustus malam:** kerjaan Yuli dipecah. Dia sekarang **dedicated ke LSTM saja** (lihat `docs/rencana-lstm-forecast.md`, Fase 1). Item 2.1/2.2/2.5/2.6 di bawah ini **BUKAN LAGI tanggung jawab Yuli** — dipindah ke Rahmat karena sifatnya backend/wiring, bukan LSTM. Dibiarkan di bawah judul "2. Yuli" apa adanya (arsip riwayat), tapi status kepemilikan sekarang ada di tabel "Peta kepemilikan" — update di sana yang jadi rujukan aktif, bukan judul section ini.

### 2.1 [SEBAGIAN SELESAI, tapi bikin bug baru — SEKARANG PUNYA RAHMAT] Sambungkan decision_engine → simulation — temuan audit #1
- [x] **Dicek ulang 25 Agustus siang/malam — akhirnya beneran disambungkan!** `simulation/run_tls_simulation.py` sekarang `from decision_engine.rule_based_engine import RuleBasedEngine` dan manggil `engine.recommend(state=trafficState, ...)` — bukan lagi logika 2-fase inline. Ini progres nyata, item paling kritis di audit akhirnya tersentuh
- [x] **Tapi:** `rule_based_engine.py` ditulis ulang TOTAL oleh Yuli (693 baris, class `Recommendation` dataclass sendiri, method `.recommend()`) — bukan lagi versi Rahmat (`.decide()`, target `backend/app/schemas/recommendation.py::SignalRecommendation`). Bukan masalah kalau cuma dipakai `run_tls_simulation.py` sendiri (dia sudah disesuaikan ke method baru), TAPI:
- [x] **[SELESAI 25 Agustus malam, Rahmat]** `backend/app/services/recommendation_service.py` disesuaikan: `request.intersection_id` → `request.intersectionId`, `self.engine.decide(...)` → `.recommend(state=, currentGreenSeconds=, currentPhase=)`, fallback branch juga dibetulkan ke camelCase. Sekalian ketemu 2 bug lain di rantai yang sama: conflict marker Git belum diselesaikan di `main.py` (bikin backend gagal start total) dan batas `le=1` basi di `ApproachState.densityIndex` (data zona real bisa sampai 13.4). Diverifikasi lewat `TestClient`: `POST /recommendation` sekarang **200 OK**

### 2.2 [SEBAGIAN BESAR SELESAI 25 Agustus malam — root cause ketemu & diperbaiki Rahmat] Test suite backend — temuan audit #2
- [x] **Root cause hang ketemu:** BUKAN interaksi antar-modul kayak dugaan awal — pytest tanpa config default nyapu SELURUH `backend/`, termasuk 5 script manual yang nyasar di root (`test_start.py`, `test_run_backend.py`, `test_screenshot.py`, `test_sim_service.py`, `test_regression.py`, semua namanya cocok pola `test_*.py`). `test_start.py` isinya kode level-modul yang langsung `requests.post()` ke server yang belum tentu jalan — begitu diimport (bukan dijalankan) oleh pytest, langsung hang nunggu koneksi
- [x] **Fix:** tambah `backend/pytest.ini` (`testpaths = tests`) — pytest sekarang cuma nyari test di folder `tests/`, tidak nyapu seluruh `backend/`. Script manual dibiarkan (tidak dihapus, kemungkinan masih dipakai buat debug manual)
- [x] **Verifikasi:** `pytest --collect-only -q` dari hang tanpa batas → 4.68 detik. `pytest -q` full run dari harus di-force-kill → ~13 detik
- [x] **Bonus cleanup sekalian (di luar scope hang, tapi ditemukan pas ngebenerin):** dari 27 test gagal awal → sekarang tinggal **1 gagal** (`test_lstm_forecaster.py`, bukan bug — nunggu Yuli commit model LSTM baru) + **3 error collection** (belum disentuh, lihat catatan di bawah). Detail perbaikan: hapus `test_traffic_service.py`+`test_traffic_state_builder.py` (nge-test desain CSV-langsung yang sudah pensiun, dikonfirmasi Yuli aman dihapus), fix route basi di `test_api.py`/`test_traffic_api.py`, fix enum `Approach.SOUTH`→`Approach.south` + type mismatch di `test_sumo_adapter.py`, pasang `legacy_router` di `main.py` (nutup juga item 2.5), fix bug nyata di `app/repositories/traffic_state_repository.py` (`exclude={"approach"}` bikin kolom NOT NULL `approach` selalu kosong pas insert ke Supabase — data korup tiap test ini jalan), fix import salah di test-nya sendiri (`from backend.app...` → `from app...`)
- [x] **Update lanjutan — Kategori C tuntas juga (lihat item 2.5):** `test_full_traffic_ingestion.py` & `test_traffic_bulk_repository.py` dihapus (bukan test asli, dependen ke kode yatim yang rusak). `test_rule_based_engine.py` diperbaiki (path import ke `decision_engine.rule_based_engine`, 2 assertion basi dibetulkan). **`pytest -q` polos sekarang: `1 failed, 18 passed`, NOL error collection.** Satu-satunya sisa gagal (`test_lstm_forecaster.py`) nunggu Yuli commit model, bukan bug.

### 2.3 [SELESAI, diperbaiki Rahmat 24-25 Agustus] Endpoint rusak — temuan audit #4
- [x] `GET /api/v1/traffic/live-csv` — sudah 200 sejak semalam (perbaikan tidak sengaja lewat refactor `traffic_state_builder.py`), dan datanya sudah disinkronkan ulang ke CSV asli. Tuntas.

### 2.4 [SELESAI 25 Agustus malam] Endpoint hardcoded — temuan audit #3
- [x] `forecast_service.py` — sudah bukan hardcode lagi sejak semalam (lihat 2.3), lanjut dikembangkan Yuli jadi `realtime_forecast_service.py` (LSTM PyTorch beneran, masih terus berkembang)
- [x] **`recommendation_service.py` — SUDAH DIPERBAIKI (lihat 2.1).** `POST /recommendation` sekarang 200 OK
- [x] **`signal_service.py` — dicek ulang 25 Agustus malam, ternyata BUKAN cuma hardcode, tapi CRASH juga (bug yang sama persis polanya dengan `recommendation_service.py`).** `app/schemas/signal.py` full camelCase (`intersectionId`, `phaseId`, `durationSeconds`, dst, tanpa alias), tapi `signal_service.py` construct pakai kwarg snake_case (`intersection_id=`, `phase_id=`, `duration_seconds=`). Karena `GET /signal/status` fallback ke `get_demo_status()` kalau belum ada yang POST, endpoint ini **crash 500 dari backend baru nyala pertama kali**, sebelum siapa pun sempat pakai. Diperbaiki: semua kwarg disamakan ke camelCase. Diverifikasi lewat `TestClient`: `GET` dan `POST /signal/status` sekarang 200 OK
- [x] **Risiko demo teratasi:** baik `/recommendation` maupun `/signal/status` sekarang jalan normal, bukan lagi crash

### 2.5 [SELESAI 25 Agustus malam, Rahmat] Rute mati — temuan audit #5
- [x] `app/api/routes/health.py` — sudah di-`include_router` di `main.py`, `/api/v1/health` sudah 200 (perbaikan Rahmat)
- [x] `legacy_router` (`/api/traffic/*`) — **dipasang** di `main.py`. Sekaligus nutup 2 test gagal di `test_traffic_api.py`
- [x] Kode yatim `traffic_ingestion_service.py` — **dihapus**. Ternyata bukan cuma yatim, tapi rusak total: manggil `TrafficStateBuilder.buildFromCvOutput()` yang sudah tidak ada sama sekali (builder sekarang 100% Supabase-based). 4 file di `tests/` yang mereferensikannya (`test_traffic_ingestion.py`, `test_traffic_repository.py`, `test_traffic_bulk_repository.py`, `test_full_traffic_ingestion.py`) ternyata semuanya bukan test pytest asli (cuma `def main()`, nol `def test_*`) — ikut dihapus, nol coverage yang hilang. Ini sekaligus menutup 2 dari 3 error collection Kategori C di item 2.2

### 2.6 [SELESAI 25 Agustus malam, Rahmat] Dokumentasi — temuan audit #6
- [x] `docs/database.md` — 3 nama tabel basi di blok SQL (`CREATE TABLE`, index, FK, dan cleanup `DROP TABLE`) disamakan ke nama asli yang dipakai prosa/Supabase: `"videoUploads"` → `"cameraVideos"`, `"approachStates"` → `"trafficApproachStates"`, dan 1 temuan tambahan yang belum ada di audit awal: `"simulationRuns"` → `"simulations"`. Diverifikasi tidak ada `CREATE TABLE` duplikat setelah rename

### 2.7 [BARU, DIKLARIFIKASI — bukan bug] `forecasting/outputs/` & `forecasting/scripts/` (pems04/tmu/brisbane) terhapus
- Ditemukan lewat commit `355fabc` (Yuli): seluruh folder `forecasting/outputs/{pems04,tmu,brisbane}/` dan `forecasting/scripts/{pems04,tmu,brisbane}/` — yang `CLAUDE.md` tandai wajib dijaga sebagai bukti laporan — hilang dari repo. Sempat dikira kecelakaan, **diklarifikasi langsung ke Rahmat: ini disengaja**, Yuli lagi melatih ulang LSTM pakai CSV proyek asli (bukan dataset proxy PeMS04/TMU/Brisbane lagi), hasil barunya sudah ada di lokal dia tinggal di-commit
- **Belum di-commit per saat ini** — sampai itu terjadi, repo sekarang tidak punya bukti LSTM SAMA SEKALI (baik yang lama maupun yang baru). Perlu dipastikan Yuli commit hasil barunya sebelum tenggat, dan idealnya `docs/*` yang menjelaskan hasil PeMS04/TMU/Brisbane lama diupdate juga supaya tidak nyebut angka yang buktinya sudah tidak ada di repo

---

## 3. Melpi (Santi Melvira)

### 3.1 [SELESAI DENGAN SENDIRINYA] Sinkronisasi dulu (lihat Risiko #1)
- [x] Klarifikasi dengan Yuli: siapa pegang wiring `tls_controller.py`/`run_tls_simulation.py`/`decision_engine/feed_to_supabase.py` — **terselesaikan lewat proses git merge malam ini** (bukan lewat obrolan eksplisit): Yuli akhirnya jadi pemilik utama wiring simulasi (lihat 2.1), Melpi merge perubahannya sendiri di atas itu tanpa konflik berarti. Tidak perlu tindakan lanjutan di poin ini

### 3.2 Dead code frontend & Optimasi Digital Twin — temuan audit #5
- [x] `DashboardSkeleton.tsx` — **SUDAH DIHAPUS** (Tidak dipakai, `page.tsx` sudah punya komponen internal).
- [x] `DashboardLayout.tsx` — **SUDAH DIHAPUS** (Dead code).
- [x] Halaman `/digitaltwin` (802 baris) — **SUDAH DISELESAIKAN:** Telah berhasil disambungkan ke data asli. Tampilan statis telah diganti dengan Live Video Stream dari SUMO, dan panel "Signal Status" sudah terhubung secara dinamis ke *Rule-Based Decision Engine* (`rule_decision.py`). Tombol Reset juga sudah terhubung ke backend.
- [ ] **Catatan Optimasi Streaming Simulasi (RunPod vs Lokal):** Saat ini streaming SUMO di halaman Digital Twin menggunakan metode MJPEG (`traci.gui.screenshot` ke local disk) yang menyebabkan frame patah-patah dan beban CPU tinggi di laptop lokal. **Saran:** Jangan ubah ke FFmpeg + WebRTC di lingkungan lokal (akan membuat laptop makin lag). Pertahankan MJPEG untuk lokal, dan optimalkan nanti saat *deploy* ke RunPod (Linux) dengan menggunakan Xvfb (Virtual Monitor) dan RAM Disk (`/dev/shm`) untuk menyimpan *cache screenshot*. RunPod memiliki spesifikasi tinggi yang akan memproses streaming tersebut jauh lebih mulus tanpa membebani laptop *client*.

### 3.3 Keputusan scope — fitur auth (lihat Risiko #3)
- [x] Diskusikan dengan tim: halaman login/register/account/settings masuk prioritas demo 31 Agustus atau tidak? — **KEPUTUSAN:** Tidak prioritas untuk demo, namun kode dibiarkan saja (tidak dihapus) untuk pengembangan di masa depan.
- [x] Kalau **tidak** prioritas: alihkan waktu ke item 3.2 di atas atau kembali pegang CV (lihat 3.4) — *Sudah dialihkan dan diselesaikan.*

### 3.4 [TIDAK PERLU LAGI] Opsional — kembali ke CV (kalau kapasitas ada & tim sepakat)
- [x] Sudah tidak relevan — item 1.1 (validitas data CV) **sudah tuntas dikerjakan Rahmat** 24 Agustus. Melpi tidak perlu balik ke `vehicle_counter_copy.py`, kapasitasnya lebih baik tetap di frontend/digital twin seperti sekarang

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

- [x] Sudah sepakat siapa pegang wiring decision_engine→simulation? — **Yuli**, dan akhirnya beneran dikerjakan 25 Agustus (lihat 2.1). Tapi menyisakan bug baru di `recommendation_service.py` yang perlu diberesin
- [x] Sudah diputuskan status fitur auth (in-scope / ditunda)? — **Ditunda**, kode dibiarkan (keputusan Melpi, lihat 3.3)
- [x] Sudah diputuskan siapa lanjut kalibrasi CV CCTV_4 & identitas koridor timur (Rahmat / Melpi balik)? — **Selesai** oleh Rahmat 24 Agustus, tidak perlu siapa pun lanjut
- [x] Sudah dicek file network baru (`simpang44_*`) — aset atau regresi? — **Regresi, sudah dihapus** 24 Agustus

## 6. Update malam 25 Agustus — review detail push Yuli & Melpi

**Progres nyata (bukan cuma klaim, sudah diverifikasi langsung):**
- Item 2.1 (KRITIS) akhirnya tersambung — `run_tls_simulation.py` beneran manggil `RuleBasedEngine` sekarang
- Item 3.2 (dead code) tuntas — `DashboardSkeleton.tsx`/`DashboardLayout.tsx` sudah terhapus, dikonfirmasi langsung
- Backend sempat gagal start **3 kali terpisah** malam ini (dependency `joblib` kurang, import salah `app.db.supabase_client`, dan `traci` belum terinstall + path SUMO binary hardcode ke `simulation/.venv` yang tidak pernah ada) — semuanya diperbaiki Rahmat, termasuk pengaman baru di `main.py` (`forecast_router` sekarang gagal dengan aman, tidak lagi bikin backend mati total kalau ada masalah lagi ke depannya)
- `forecasting/outputs/`+`scripts/` (pems04/tmu/brisbane) yang sempat dikira terhapus tidak sengaja — **dikonfirmasi disengaja** (Yuli lagi latih ulang pakai CSV asli), tapi **hasil barunya belum di-commit**, jadi repo sementara tidak punya bukti LSTM sama sekali sampai itu terjadi

**Regresi baru yang perlu diperbaiki:**
- `recommendation_service.py` sekarang **500 crash** (bukan cuma hardcode lagi) — `rule_based_engine.py` ditulis ulang total oleh Yuli (`.decide()` → `.recommend()`, schema custom sendiri), tapi `recommendation_service.py` belum ikut disesuaikan. **Masih belum diperbaiki** setelah commit susulan Yuli (`673cea7`) — dites ulang, error persis sama
- Test suite backend **sekarang hang total** (bukan lagi "32 gagal" — sudah tidak bisa dijalankan sama sekali, macet tanpa batas di "collecting...", harus di-force-kill). Ini lebih parah dari temuan sebelumnya di sesi yang sama

**Update setelah commit susulan Yuli (`673cea7 "bismillah decision enginenya gak error lagi"`, 743 baris `rule_based_engine.py` + 825 baris `run_tls_simulation.py` + 896 baris `simulation_result_writer.py` berubah lagi):** dia benerin error yang dia lihat sendiri pas jalanin simulasi (`run_tls_simulation.py`), TAPI **tidak menyentuh `recommendation_service.py`** — jadi endpoint backend `/recommendation` yang dipakai frontend/dashboard tetap 500. Dua konteks (simulasi vs backend API) dipakai `RuleBasedEngine` yang sama tapi ditest terpisah-pisah, jadi perbaikan di satu sisi tidak otomatis nutup sisi lain.

**Rekomendasi paling mendesak:** perbaiki `recommendation_service.py` dulu (regresi paling parah, endpoint yang tadinya "cuma bohong" sekarang benar-benar mati) DAN cari akar hang di test suite (kemungkinan besar terkait — banyak modul yang saling terkoneksi sekarang: `rule_based_engine`, `realtime_forecast_service`, LSTM, Supabase — kemungkinan ada yang saling rebutan resource pas semua diimport bareng).

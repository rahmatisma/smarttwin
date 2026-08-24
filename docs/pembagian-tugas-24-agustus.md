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
| **Backend inti (traffic state, db, routes)** | **Yuli** | — | `backend/app/pipeline/traffic_state_builder.py`, `backend/app/services/traffic_service.py`, `backend/app/services/simulation_service.py`, `backend/app/api/routes/traffic.py`, `backend/app/db/*` |
| **Integrasi SUMO/TraCI (simulation + backend/app/simulation)** | **Yuli** (paling dalam konteksnya sekarang) | Melpi (baru masuk 24 Agustus — **wajib sinkron dulu**, lihat Risiko #1) | `simulation/tls_controller.py`, `simulation/run_tls_simulation.py`, `simulation/demand_adapter.py`, `backend/app/simulation/sumo/sumo_controller.py`, `backend/app/simulation/sumo/traffic_state_adapter.py` |
| **Network SUMO (`.net.xml.gz`)** | **Rahmat** | — | `simulation/network/*` |
| **Test suite backend** | **Yuli** | — | `backend/tests/*` |
| **Dokumentasi backend/database** | **Yuli** | — | `docs/database.md`, `backend/docs/traffic-state-builder.md` |
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
- [ ] **Belum dikerjakan di sesi ini:** wiring `run_tls_simulation.py` (Yuli, task 2.1) — `create_phase_plan()` di sana perlu diganti dari logika inline max-queue jadi panggil `RuleBasedEngine.decide()`. Bentuknya sudah cocok (satu `recommended_phase` + durasi per panggilan, sama seperti pola `create_phase_plan()` sekarang) — **kabari Yuli skema barunya sebelum dia mulai wiring**

### 1.2b [TEMUAN BARU, SUDAH DIPERBAIKI] Service_role key ter-hardcode di `decision_engine/feed_to_supabase.py`
- [x] Ditemukan saat mengerjakan 1.2: `feed_to_supabase.py` (commit Melpi hari ini) punya Supabase **service_role key** (bypass RLS) ter-hardcode langsung di kode, dan commit "perbaikan" berikutnya cuma menyamarkannya jadi default value `os.getenv(..., "<key yang sama>")` — key-nya tetap hidup di kode
- [x] Kode sudah diperbaiki: sekarang WAJIB dari environment variable (`SUPABASE_SERVICE_ROLE_KEY`, disamakan namanya dengan `backend/.env`), tidak ada fallback hardcode lagi
- [ ] **WAJIB kamu lakukan manual, di luar kendali saya:** rotate service_role key di Supabase Dashboard → Settings → API. Key lama sudah bocor permanen ke git history (`69e37bf`, `c6e5a65`) — mengubah kode saja tidak cukup

### 1.3 [SELESAI 24 Agustus] Regresi network SUMO — diperiksa & dibersihkan
- [x] Diperiksa asal-usul `simpang44_pingit.net.xml.gz`, `simpang44_baru.net.xml`, `simpang4.xml`, `simpang4_pingit.add.xml` yang masuk dari commit Melpi hari ini ("sumocuy"). **Hasil: bukan perbaikan TLS seperti yang diduga awalnya** — diff level baris (`gzip` + `difflib`) menunjukkan `simpang44_pingit.net.xml.gz` **byte-identik** dengan `simpang4_pingit.net.xml.gz` kanonik, cuma beda 3 baris (timestamp generate netconvert & nama file di komentar, keduanya kosmetik). Program TLS `SIMPANG_CENTER` (4 fase, 39/6/39/6 detik, satu grup hijau per fase — pola yang dikira baru) ternyata **sudah ada di network kanonik sejak sebelum hari ini** juga (didokumentasikan di `roadmap.md` sekitar 17-21 Agustus)
- [x] `simpang4_pingit.sumocfg` dikembalikan ke `net-file="simpang4_pingit.net.xml.gz"` (network kanonik) — sempat menunjuk ke file duplikat bertypo
- [x] 6 file duplikat/scratch dihapus (`git rm`, fully recoverable dari history): `simpang44_pingit.net.xml.gz`, `simpang44_pingit.net.xml.gz.xml`, `simpang44_baru.net.xml`, `simpang4.xml`, `simpang4_pingit.add.xml`, `simpang4_pingit.sumocfg.bak` — semua terverifikasi tidak dipakai script mana pun dan tidak berisi apa pun yang beda dari network kanonik
- [x] `simulation/network/` sekarang cuma berisi 2 file: `simpang4_pingit.net.xml.gz` dan `simpang4_pingit.sumocfg` — sesuai kebijakan "satu network project" di CLAUDE.md. XML sumocfg divalidasi well-formed, route file yang dirujuk (`demo_mobil.rou.xml`) dikonfirmasi ada
- [x] **Divalidasi dengan simulasi jalan sungguhan** — Rahmat menjalankan `python run_intersection.py` di mesinnya sendiri (venv siap): TraCI konek, `Traffic light ID: SIMPANG_CENTER` terbaca, `State RYG: GGGggrrrrrrrrrrrrrrr` (fase 0, cocok persis dengan yang diverifikasi tadi), `setPhase()` berhasil. **Catatan:** `run_intersection.py` load `network/simpang4_pingit.net.xml.gz` langsung (bukan lewat `simpang4_pingit.sumocfg`, tidak ada spawn kendaraan) — jadi ini validasi network file-nya sendiri, bukan smoke-test route/config lengkap. Kalau mau validasi `sumocfg` secara utuh (dengan route file), perlu jalankan `run_tls_simulation.py` atau `run_simulation.py` (punya Yuli) terpisah

---

## 2. Yuli

### 2.1 [KRITIS] Sambungkan decision_engine → simulation — temuan audit #1
- [ ] `run_tls_simulation.py` saat ini pakai logika 2-fase inline sendiri, **bukan** output `RuleBasedEngine` milik Rahmat — ganti supaya rekomendasi yang tampil di simulasi benar-benar hasil decision engine
- [ ] Konsolidasi `demand_adapter.py` & `tls_controller.py` yang tidak dipakai runner (logika duplikat inline) — kamu paling dalam konteksnya karena sudah pegang `sumo_controller.py` & `traffic_state_adapter.py`
- [ ] **Koordinasi dengan Melpi** — dia juga commit ke file yang sama hari ini, samakan dulu siapa ngerjain bagian mana

### 2.2 [KRITIS] Test suite backend — temuan audit #2
- [ ] `pytest -q` sekarang: 24 gagal + 3 error koleksi, cuma 7 lolos dari 15 file — dan yang lolos cuma tes infrastruktur, bukan logika bisnis
- [ ] Root cause utama: test masih menguji arsitektur CSV lama (`TrafficService(csv_path=...)`, endpoint `/api/v1/traffic/state` versi lama, path legacy `/api/traffic/*`) — update ke arsitektur baru yang sudah kamu bangun
- [ ] **Risiko demo:** kalau juri minta jalankan test, hasilnya merah semua

### 2.3 Endpoint rusak — temuan audit #4
- [ ] `GET /api/v1/traffic/live-csv` → HTTP 500. Manggil `builder.buildFromSupabase()` yang sudah tidak ada di `TrafficStateBuilder` versi baru, dan akses `builder.last_matched_video_time` yang tidak pernah di-set

### 2.4 Endpoint hardcoded — temuan audit #3
- [ ] `forecast_service.py` — 8 angka statis, tidak ada model/logika
- [ ] `recommendation_service.py` — semua konstan (`confidence=0.75`, `source="pending"`), tidak baca request sama sekali
- [ ] `signal_service.py` — fallback `get_demo_status()` hardcoded; state realtime cuma in-memory, hilang tiap restart (belum persist ke tabel `signalStatuses` yang sudah ada)
- [ ] **Risiko demo:** kalau juri tanya "rekomendasi ini asalnya dari mana?", jawaban jujurnya sekarang: angka tetap

### 2.5 Rute mati — temuan audit #5
- [ ] `app/api/routes/health.py` tidak pernah di-`include_router` → `/api/v1/health` 404
- [ ] `legacy_router` (`/api/traffic/*`) juga tidak dipasang → penyebab 3 test gagal
- [ ] Putuskan nasib kode yatim: `traffic_ingestion_service.py`, `repositories/traffic_state_repository.py`, `intersection_repository.py` — tidak dipakai kode aktif, hapus atau sambungkan

### 2.6 Dokumentasi — temuan audit #6
- [ ] `docs/database.md` inkonsisten secara internal: bagian prosa pakai nama tabel baru (`trafficApproachStates`/`trafficLaneMetrics`/`cameraVideos`, sesuai kode), tapi blok `CREATE TABLE` di akhir file masih pakai nama lama (`approachStates`, `videoUploads`) dan tidak ada DDL untuk `trafficLaneMetrics` sama sekali — file ini kamu yang paling sering update, tinggal disatukan

---

## 3. Melpi (Santi Melvira)

### 3.1 Sinkronisasi dulu (lihat Risiko #1)
- [ ] Klarifikasi dengan Yuli: siapa pegang wiring `tls_controller.py`/`run_tls_simulation.py`/`decision_engine/feed_to_supabase.py` — kalian berdua sama-sama commit ke situ hari ini

### 3.2 Dead code frontend & Optimasi Digital Twin — temuan audit #5
- [x] `DashboardSkeleton.tsx` — **SUDAH DIHAPUS** (Tidak dipakai, `page.tsx` sudah punya komponen internal).
- [x] `DashboardLayout.tsx` — **SUDAH DIHAPUS** (Dead code).
- [x] Halaman `/digitaltwin` (802 baris) — **SUDAH DISELESAIKAN:** Telah berhasil disambungkan ke data asli. Tampilan statis telah diganti dengan Live Video Stream dari SUMO, dan panel "Signal Status" sudah terhubung secara dinamis ke *Rule-Based Decision Engine* (`rule_decision.py`). Tombol Reset juga sudah terhubung ke backend.
- [ ] **Catatan Optimasi Streaming Simulasi (RunPod vs Lokal):** Saat ini streaming SUMO di halaman Digital Twin menggunakan metode MJPEG (`traci.gui.screenshot` ke local disk) yang menyebabkan frame patah-patah dan beban CPU tinggi di laptop lokal. **Saran:** Jangan ubah ke FFmpeg + WebRTC di lingkungan lokal (akan membuat laptop makin lag). Pertahankan MJPEG untuk lokal, dan optimalkan nanti saat *deploy* ke RunPod (Linux) dengan menggunakan Xvfb (Virtual Monitor) dan RAM Disk (`/dev/shm`) untuk menyimpan *cache screenshot*. RunPod memiliki spesifikasi tinggi yang akan memproses streaming tersebut jauh lebih mulus tanpa membebani laptop *client*.

### 3.3 Keputusan scope — fitur auth (lihat Risiko #3)
- [x] Diskusikan dengan tim: halaman login/register/account/settings masuk prioritas demo 31 Agustus atau tidak? — **KEPUTUSAN:** Tidak prioritas untuk demo, namun kode dibiarkan saja (tidak dihapus) untuk pengembangan di masa depan.
- [x] Kalau **tidak** prioritas: alihkan waktu ke item 3.2 di atas atau kembali pegang CV (lihat 3.4) — *Sudah dialihkan dan diselesaikan.*

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

- [ ] Sudah sepakat siapa pegang wiring decision_engine→simulation (Yuli / Melpi / berdua dibagi per fungsi)?
- [ ] Sudah diputuskan status fitur auth (in-scope / ditunda)?
- [ ] Sudah diputuskan siapa lanjut kalibrasi CV CCTV_4 & identitas koridor timur (Rahmat / Melpi balik)?
- [ ] Sudah dicek file network baru (`simpang44_*`) — aset atau regresi?

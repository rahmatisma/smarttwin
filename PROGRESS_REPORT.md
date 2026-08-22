# SmartTwin — Progress Report

**Tanggal audit:** 22 Agustus 2026
**Hari ke:** 8 dari 16
**Auditor:** Claude Code (otomatis)

---

## Ringkasan Eksekutif

Separuh depan pipeline (video → CV → CSV/Supabase) sudah **benar-benar berjalan dan terbukti**, bukan stub: 29.453 baris CSV crossing dari empat lengan, dan empat job YOLO+ByteTrack yang tuntas lewat jalur upload web → Supabase pada 21–22 Agustus. Separuh belakang (Scenario Generator → Decision Engine) **belum ada satu baris pun** — dan itulah yang membuat produk ini masih "dashboard monitoring", belum "digital twin untuk optimasi sinyal adaptif".

Tiga temuan yang paling menentukan, semuanya terverifikasi dengan eksekusi langsung, bukan pembacaan kode:

1. **Setiap baris `trafficStates` di Supabase cuma punya SATU approach** (5.314 dari 5.314). Dashboard tidak akan pernah bisa menampilkan empat lengan sekaligus dari data yang ada sekarang.
2. **Ada dua Traffic State Builder dengan semantik agregasi yang berbeda**, dan yang versi `simulation/` sekarang **crash**. Versi backend melaporkan antrean **5× lebih besar** dari yang benar.
3. **Replay CSV → SUMO jalan, tapi cuma 41,1% kendaraan berhasil berangkat** — 4.525 dari 7.681 tertahan di mulut lengan karena program sinyal default tidak mampu melepasnya.

**Estimasi kemajuan keseluruhan: 56%**

Dihitung sebagai rata-rata tertimbang per komponen terhadap definisi "MVP siap demo" di `docs/roadmap.md`, bukan terhadap rencana 4 minggu yang asli:

| Komponen | Bobot | Capaian | Kontribusi |
|---|---:|---:|---:|
| CV & deteksi | 20% | 85% | 17,0 |
| Traffic State Builder | 10% | 60% | 6,0 |
| SUMO & simulasi | 15% | 65% | 9,8 |
| Scenario Generator | 10% | 0% | 0,0 |
| Decision Engine | 10% | 5% | 0,5 |
| Backend API | 15% | 55% | 8,3 |
| Frontend | 15% | 75% | 11,3 |
| Forecasting (di luar scope aktif) | 5% | 60% | 3,0 |
| **Total** | **100%** | | **≈56%** |

Capaian per komponen dinilai dari bukti yang bisa dijalankan (output file, hasil test, baris database), bukan dari keberadaan file. Kode yang ada tapi tidak terpanggil dari `main.py` dihitung ≤ 20%.

---

## Status Per Komponen

### CV & Pipeline Deteksi

**Counting line sudah berbasis crossing.** `cv/vehicle_counter.py` (2.811 baris) memakai `side_of_line()` + `potongan_dalam_ruas()` dan mencatat crossing pada lajur tempat kendaraan memotong garis. Dokumentasi di kepala file memisahkan dua populasi secara eksplisit: ALIRAN (`vehicle_count`, `*_count`) vs KEHADIRAN (`queue_*`, `density_index`). Perbaikan 17 Agustus sudah masuk dan bukan lagi klaim di dokumen saja.

**Dataset — `cv/output/smarttwin_traffic_data.csv`:** 29.453 baris data, 12 kolom, rentang `2026-08-15 16:30:12` → `17:19:16` (2.616 detik unik, ~49 menit), 3 lajur per lengan. Keempat lengan hadir:

| approach | baris | total crossing |
|---|---:|---:|
| north | 7.589 | 3.183 |
| east | 7.583 | 1.264 |
| west | 7.368 | 1.962 |
| south | 6.913 | 1.272 |

Rincian kelas: motor 6.088, mobil 1.445, truk 108, bus 40 — total 7.681, cocok persis dengan jumlah `vehicle_count`. Konsistensi kolom terjaga.

**Kalibrasi counting line** terdokumentasi di `COUNTING_LINES` + `ARAH_MASUK` (bagian 6/6C `vehicle_counter.py`), lengkap dengan angka ujinya:

| Lengan | Status | Bukti |
|---|---|---|
| south | ✅ terverifikasi | 67/67 crossing menuju stop line; 104 crossing / 180 detik = 34,7/menit |
| west | ✅ terverifikasi | Optical flow per kotak uji, sumbu jalan +11°, garis dipasang +101° |
| east | ❓ garis oke, koridor belum | Digambar dari frame CCTV_2; identitas koridor (Diponegoro vs Magelang) belum diadu dengan bearing SUMO |
| north | ❌ belum dikalibrasi | Masih default `(0.10,0.65,0.90,0.65)`; kamera memotret badan simpang, bukan ruas lurus |

Bukti kalibrasi dan investigasi tersimpan di `cv/_arsip/` (gitignored kecuali README): `BUKTI_pita_atas_CCTV4_vs_CCTV2.jpg`, `CATATAN-sync-cctv1.md`, `clockmap/`, `crop_check/` (25 gambar bukti), `keping_sync/` (72 potongan video), plus tiga CSV historis.

**Caveat yang masih berlaku:** east dan north membaca **video yang sama** (`CCTV_2.mp4`). Terkonfirmasi ulang dari output live: `densityIndex` north dan east identik sampai digit terakhir (`6.521093166666667`). Yang membedakan keduanya hanya kolom volume. `queue_*` dan `density_index` east **tidak boleh** diklaim sebagai pengukuran lengan timur.

**Pipeline produksi baru:** `cv/process_uploaded_video.py` (622 baris) memproses satu video ad-hoc → Supabase per window 5 detik + video anotasi (kotak + garis merah) ke Hugging Face, dan mem-POST `/api/v1/traffic/notify` tiap window. `cv/reprocess_all.py` (303 baris, **masih untracked**) mengantre semua video yang belum punya anotasi. Bukti eksekusi nyata di tabel `cvProcessingJobs`: 4 job `completed` (21–22 Agustus, masing-masing 2–3 jam), 2 `failed` dengan pesan yang jujur ("approach salah pilih (utara), dibetulkan ke timur").

**Status: ✅** (dengan satu lengan belum terkalibrasi dan satu lengan belum terverifikasi identitasnya)

---

### SUMO & Simulasi

`simulation/network/simpang4_pingit.net.xml.gz` **ada** dan itu satu-satunya network di repo — tidak ada regresi ke `simpang4.net.xml.gz`. `run_intersection.py` memuatnya secara eksplisit.

**Kontrol fase manual: terbukti jalan.** Dijalankan langsung saat audit:

```
Traffic light ID: SIMPANG_CENTER
Fase sekarang: 0
State RYG: GGGggrrrrrGGGggrrrrr
Setelah setPhase(0): 0
OK — koneksi TraCI, step simulasi, dan kontrol fase manual semua jalan
```

**`snapshot_dashboard_data.py` ada** (124 baris) dan `outputs/approach_snapshot.json` sudah dihasilkan — tapi tanggalnya **12 Agustus**, dari `randomTrips` demo, bukan dari data CV. Angkanya (`densityVehPerKm`, `avgSpeedKmh`) tidak punya padanan di CSV CV. Snapshot ini **artefak Minggu 1 yang sudah usang**, jangan dipakai sebagai bukti integrasi.

**Yang menggantikannya: `simulation/replay_from_csv.py` (534 baris, baru sejak 17 Agustus).** Ini jawaban nyata untuk "demand SUMO ikut deteksi asli". Dijalankan penuh saat audit:

```
Baris CSV terbaca : 29453
Durasi simulasi   : 2945 detik (49.1 menit)
Kendaraan diminta : 7681
Sebaran belok     : kanan 1890 (24.6%), kiri 1960 (25.5%), lurus 3831 (49.9%)
TLS               : SIMPANG_CENTER

lengan     diminta   berangkat   tertahan   selisih       %
north         3183         820       2363     -2363   25.8%
south         1272         856        416      -416   67.3%
east          1264         721        543      -543   57.0%
west          1962         759       1203     -1203   38.7%
TOTAL         7681        3156       4525     -4525   41.1%
```

Ini **berhasil sekaligus mengungkap masalah besar**: hanya 41,1% demand yang benar-benar masuk jaringan. 4.525 kendaraan tertahan sebagai *pending* karena program sinyal bawaan network tidak mampu melepas arus sebesar itu. Statistik SUMO: `WaitingTime 129,86` `TimeLoss 199,57` `DepartDelay 606,08` detik. Selama angka ini belum diperbaiki, **tidak ada baseline yang sah** untuk mengklaim perbaikan apa pun dari optimasi sinyal — pembanding "sebelum" nya sendiri belum valid.

Catatan penting: `replay_from_csv.py` membaca CSV **langsung**, bukan lewat `TrafficState`. Jadi tahap 2 pipeline sebenarnya **dilangkahi**, bukan dilewati.

**Scenario Generator: TIDAK ADA.** Pencarian `scenario|heuristic` di seluruh kode proyek (di luar `.venv`) hanya kena `docs/`, `CLAUDE.md`, dan `backend/app/schemas/recommendation.py`. Folder `backend/app/simulation/scenearios/` ada (perhatikan typo namanya) tapi isinya cuma `.gitkeep`.

**Decision Engine rule-based: TIDAK ADA.** Yang ada cuma `backend/app/services/recommendation_service.py` — 51 baris yang mengembalikan objek hardcoded (`recommended_green_seconds=40`, `confidence=0.75`, `source="pending"`). Tidak ada satu pun input dari `TrafficState` maupun `ScenarioResult`.

Skrip pendukung lain: `check_tls_coverage.py` (13 baris), `flatten_roundabout.py` (82 baris), `test_traci.py` (24 baris).

**Status: 🔄**

---

### Backend FastAPI

**46 file Python** di `backend/` (di luar `.venv`), naik dari 22 file per 17 Agustus.

**Route yang benar-benar terdaftar** — diverifikasi dari `app.openapi()`, bukan dari daftar file:

```
GET   /
GET   /health
GET   /api/v1/traffic/state
POST  /api/v1/traffic/notify
WS    /api/v1/traffic/ws
POST  /api/v1/cctv/upload
GET   /api/v1/cctv/videos/{video_id}/stream
```

⚠️ **`main.py` hanya memanggil `include_router()` untuk `traffic` dan `cctv`.** Empat file route lain **ada tapi tidak pernah terpasang** — kodenya mati:

| File | Baris | Status |
|---|---:|---|
| `routes/signal.py` | 32 | tidak terdaftar; `signal_service` mengembalikan `get_demo_status()` hardcoded |
| `routes/recommendation.py` | 24 | tidak terdaftar; service-nya hardcoded, `source="pending"` |
| `routes/forecast.py` | 17 | tidak terdaftar; `forecast_service` mengembalikan 8 `ForecastPoint` hardcoded |
| `routes/health.py` | 14 | tidak terdaftar (duplikat `/health` di `main.py`) |
| `routes/history.py` | 0 | **file kosong** |
| `routes/simulation.py` | 0 | **file kosong** |

**Data asli vs stub:** `/api/v1/traffic/state` **asli** — `TrafficService` → `TrafficStateBuilder` (779 baris) → CSV CV. Dijalankan saat audit, keluar window `17:19:15–17:19:20` dengan empat lengan terisi. `/api/v1/cctv/*` juga asli (upload → Hugging Face → trigger subprocess CV → Supabase). Sisanya stub.

**Database: PostgreSQL lewat Supabase**, bukan SQLAlchemy lokal. `app/services/supabase_client.py` + `app/db/database.py` (shim kompatibilitas), dua repository (`intersection`, `traffic_state`), `app/db/seed.py`. Model SQLAlchemy (`app/db/models/`, `app/db/base.py`) sempat dibuat lalu **dihapus** saat pindah ke Supabase client.

Isi database nyata (dicek langsung):

| tabel | baris |
|---|---:|
| intersections | 1 |
| approaches | 4 |
| trafficStates | 5.315 |
| trafficApproachStates | 5.314 |
| cameras | 4 |
| cameraVideos | 8 (4 asli + 4 anotasi) |
| signalStatuses | 1 |
| recommendations | 1 |
| forecasts / forecastPredictions | 1 / 2 |

**Migrasi/schema SQL:** tidak ada file migrasi (tidak ada Alembic, tidak ada `supabase/migrations/`). Yang ada `docs/database.md` — 1.557 baris, 20 tabel dengan DDL lengkap, tapi berupa **dokumen**, bukan migrasi yang bisa dijalankan. Schema di Supabase dibuat manual.

**WebSocket: ada dan real.** `app/services/ws_manager.py` (46 baris) + endpoint `/api/v1/traffic/ws`. Ini pengganti sadar untuk Supabase Realtime yang terbukti tidak mem-broadcast `postgres_changes` di project ini. Alurnya event-driven: CV mem-POST `/notify` tiap window → backend broadcast → dashboard fetch ulang. Bukan polling.

**`.env` dan `.env.example` dua-duanya ada.** `.env.example` lengkap (Supabase + Hugging Face). Tapi `config.py` mewajibkan `supabase_url`, `supabase_service_role_key`, `hf_token`, `hf_repo_id` **tanpa default** — jadi backend gagal start di mesin yang belum mengisi `.env`. `database_url` masih dideklarasikan tapi sudah tidak dipakai.

**Hasil test** (`backend/.venv/Scripts/python.exe -m pytest tests/ -v`):

```
27 passed, 1 failed, 4 warnings in 58.52s
```

Satu-satunya kegagalan — `tests/test_traffic_state_repository.py::test_save_traffic_state`:

```
postgrest.exceptions.APIError: {'code': '23502',
  'message': 'null value in column "approach" of relation
              "trafficApproachStates" violates not-null constraint'}
```

`TrafficStateRepository.save_state()` memakai `approach_state.model_dump(exclude={"approach"})`, sementara tabelnya menuntut kolom `approach` NOT NULL (kolom itu sengaja ada di samping `approachId` — lihat `docs/database.md` §2.10). **Jalur simpan TrafficState dari backend ke database sedang rusak.** Yang mengisi 5.314 baris di Supabase adalah `cv/supabase_writer.py`, bukan repository ini.

**Status: 🔄**

---

### Frontend Dashboard

**Build lulus bersih:** `npm run build` → exit 0, TypeScript selesai tanpa error, 11 route ter-generate (`/`, `/dashboard`, `/cctv`, `/login`, `/register`, `/account`, `/settings`, `/api/cameras`, `/api/cameras/[id]`, `/_not-found`, middleware proxy). Next.js 16.3.0 + React 19.2.8 + Tailwind 4.

**Tidak ada lagi `mockData`.** `frontend/src/lib/mockData` sudah tidak ada; `page.tsx` mengambil dari `@/lib/supabaseData` (321 baris) yang menembak Supabase langsung: `intersections`, `trafficStates`, `trafficApproachStates`, `signalStatuses`, `recommendations`, `forecasts`, `forecastPredictions`, `cameras`, `cameraVideos`. Kata "mock" yang tersisa cuma penanda `signal.source === "mock"` untuk fallback simulasi sinyal (`useTrafficSimulaton.ts`) — itu memang disengaja dan ditampilkan sebagai badge "Simulated" ke pengguna.

**21 komponen** di `frontend/src/components/` (13 di root, 3 di `account/`, 8 di `settings/`), plus 1 hook, 4 helper di `lib/`, 1 file types.

**Koneksi ke backend:** ada tiga jalur berbeda, dan ini perlu diluruskan.
- **WebSocket** → `${NEXT_PUBLIC_API_URL}/api/v1/traffic/ws` dengan auto-reconnect 3 detik (`page.tsx`).
- **REST ke backend** → `/api/v1/cctv/upload` dan `/videos/{id}/stream` dari `cctv/page.tsx` dan `CameraFeedPanel.tsx`.
- **Data dashboard** → **langsung ke Supabase**, bukan lewat backend.

Konsekuensinya: `GET /api/v1/traffic/state` — satu-satunya endpoint backend yang menyajikan `TrafficState` asli — **tidak pernah dipanggil frontend**. Backend dan frontend membangun `TrafficState` dari dua jalur terpisah yang bisa berbeda hasilnya.

⚠️ **Blocker terbesar untuk demo:** dari 5.314 baris `trafficApproachStates`, distribusi jumlah approach per `trafficState` adalah `{1: 5314}` — **setiap window cuma punya satu lengan**. Sebarannya south 1.561 / north 1.351 / west 1.328 / east 1.074: keempat lengan ada datanya, tapi tidak pernah dalam window yang sama, karena tiap video diproses di waktu wall-clock yang berbeda. `fetchTrafficState()` mengambil window terbaru → dashboard hanya bisa menggambar **satu lengan**. `StatsRow`, `DigitalTwinPanel`, dan penjumlahan `vehicleClassCounts` semuanya mengasumsikan empat lengan.

**Status: 🔄**

---

### Forecasting LSTM

Sesuai keputusan roadmap, ini **di luar scope aktif** — dinilai sebagai bukti laporan, bukan sebagai fitur.

**Model tersimpan:** ada. `forecasting/outputs/pems04/sensor_1_10/best_model.pth` dan `sensor_1_20/best_model.pth`. TMU tidak menyimpan `.pth` tapi menyimpan prediksi dan metrik lengkap. Brisbane hanya `processed/` + `test/` — konsisten dengan status "tidak pernah dilatih".

**Metrik evaluasi tersimpan:**
- PeMS04 (`evaluation/overall_metrics.json`): **R² 0,879**, MAE 0,197, RMSE 0,367 — MAE/RMSE dalam **satuan terskala**, bukan kendaraan/jam. MAPE 142,6% (tidak dapat dipakai).
- TMU (`metrics/metrics.json`): speed MAE 2,04 / MAPE **2,09%**; vehicle_count MAE 27,87 / MAPE 25,6%; `queue_proxy` MAPE **1.008.321.136%** — pembagian mendekati nol, jangan dikutip.

**`forecasting/scripts/yolo/` ada dan berkembang pesat: 12 skrip**, naik dari 5 per 17 Agustus. Tambahan sejak itu: `05_baseline`, `06_error_analysis`, `07_sequence_length_experiment`, `08_forecast_horizon_experiment`, `09_hyperparameter_experiment`, `10_train_final_model`, `11_final_error_analysis`, `12_feature_sensor_diagnostic`. Ini eksperimen yang serius dan terstruktur.

⚠️ **Tapi input-nya tidak ada.** `01_inspect_yolo.py` dan `02_preprocess_yolo.py` membaca `forecasting/data/smarttwin_traffic_data.csv`. Isi `forecasting/data/` sekarang: `Brisbane.csv`, `PEMS04.npz`, `TMU.csv` — **tidak ada** file itu. Skripnya tidak menunjuk ke `cv/output/smarttwin_traffic_data.csv` yang benar. Nama file-nya sudah dibetulkan dari `_copy` (temuan 17 Agustus), tapi **path-nya belum**.

**`forecasting/outputs/yolo/` masih belum ada sama sekali.** Jadi ke-12 skrip itu belum pernah menghasilkan artefak yang bisa diperiksa maupun diulang di repo ini.

**Status: 🔄** (PeMS04 & TMU ✅ sebagai bukti laporan; jalur YOLO ❌ belum bisa dijalankan)

---

## Status Pipeline End-to-End

| Tahap | Komponen | Status | Catatan |
|-------|----------|--------|---------|
| 1 | Video → CV deteksi | ✅ | 29.453 baris CSV crossing, 4 lengan, 49 menit. 4 job Supabase `completed` 21–22 Agt. north belum dikalibrasi, east belum tervalidasi koridornya |
| 2 | CV deteksi → TrafficState | 🔄 | **Dua builder yang tidak sepakat.** Versi `simulation/` **crash** (`AttributeError: 'str' object has no attribute 'value'`); versi backend melaporkan antrean 5× lebih besar |
| 3 | TrafficState → SUMO demand | 🔄 | `replay_from_csv.py` jalan — tapi dari **CSV langsung**, melangkahi TrafficState. Jalur resmi (`SumoController.set_traffic_state`) masih `TODO` + `print()` |
| 4 | SUMO → simulasi berjalan | ✅ | 2.945 detik, TLS `SIMPANG_CENTER`, `setPhase()` terbukti. **Caveat berat:** cuma 41,1% kendaraan berangkat |
| 5 | Simulasi → Scenario Generator | ❌ | Nol baris kode. `backend/app/simulation/scenearios/` cuma `.gitkeep` (namanya juga typo) |
| 6 | Scenario → Decision Engine rule-based | ❌ | Hanya `recommendation_service.py` 51 baris hardcoded, `source="pending"`. Tidak membaca TrafficState maupun ScenarioResult |
| 7 | Decision Engine → API backend | 🔄 | `routes/recommendation.py` ada tapi **tidak di-`include_router`** di `main.py` — endpoint-nya tidak pernah hidup |
| 8 | API backend → Frontend dashboard | 🔄 | WebSocket + CCTV: ✅ nyata. Data dashboard: frontend baca Supabase langsung, `/api/v1/traffic/state` tak pernah dipanggil. **Tiap window DB cuma punya 1 lengan** |

**Pipeline nyambung sampai tahap: 4 dari 8** — dan itu pun lewat jalan pintas (CSV → SUMO langsung, bukan CSV → TrafficState → SUMO), dengan hanya 41% demand yang terwujud. Putus total di tahap 5.

Ada pipeline **kedua** yang justru nyambung penuh dan tidak ada di rencana: **upload video di web → Hugging Face → subprocess CV → Supabase → WebSocket → dashboard**. Itu 5 tahap yang benar-benar utuh, cuma bukan tahap yang dijanjikan roadmap.

---

## Commit Sejak 17 Agustus

37 commit sejak 17 Agustus; **52 commit** total sejak proyek mulai 15 Agustus.

| Hash | Tanggal | Penulis | Pesan |
|---|---|---|---|
| `72d5261` | 22 Agt | yulimuliadinah | modified backend dan database |
| `c45bcab` | 22 Agt | yulimuliadinah | modified semua backend agar sesuai dengan supabase |
| `1715a5e` | 22 Agt | Rahmat Isma | Merge branch 'main' |
| `575c4d1` | 22 Agt | Rahmat Isma | membuat mekanisme mengupload CCTV(Video) secara bersamaan |
| `41f2827` | 22 Agt | yulimuliadinah | update readme backend |
| `64bcb60` | 21 Agt | Rahmat Isma | ganti Supabase Realtime ke WebSocket sendiri, bersihin file sampah |
| `60795d5` | 21 Agt | Rahmat Isma | mengintegrasikan yolo ke CCTV |
| `51f9b36` | 21 Agt | Santi Melvira | feat: perbaikan |
| `29b147c` | 21 Agt | yulimuliadinah | build database and try some test... supabase client or sqlalchemy |
| `a11d3c1` | 21 Agt | Rahmat Isma | membuat mekanisme CCTV bisa tampil |
| `3ab090e` | 21 Agt | Santi Melvira | Merge branch 'main' |
| `acf0e3a` | 21 Agt | Santi Melvira | feat: add settings |
| `8f1b021` | 21 Agt | yulimuliadinah | build database |
| `58a2925` | 21 Agt | yulimuliadinah | build database |
| `84a6fb0` | 21 Agt | Rahmat Isma | update |
| `7272132` | 21 Agt | Santi Melvira | feat: addskeleton |
| `073ee22` | 21 Agt | Santi Melvira | feat: add |
| `cd2c0e3` | 21 Agt | yulimuliadinah | update database backend dan frontend |
| `5d3847d` | 21 Agt | yulimuliadinah | build databases |
| `eda7a43` | 21 Agt | Santi Melvira | feat: add camerapanel dari page cctv |
| `1b48d95` | 21 Agt | Santi Melvira | feat: edit page sidebar |
| `9561cb2` | 21 Agt | Santi Melvira | feat: edit page cctv |
| `60f2597` | 21 Agt | Santi Melvira | feat: add new database.md |
| `1e3fd82` | 20 Agt | yulimuliadinah | tambahin sql di database.md |
| `22afbd1` | 20 Agt | yulimuliadinah | nambah database.md |
| `ef95837` | 20 Agt | yulimuliadinah | lanjut traffic state builder sama backend |
| `7a7fc54` | 20 Agt | Santi Melvira | feat: add CCTV monitoring page |
| `c992751` | 20 Agt | yulimuliadinah | update traffic skill builder |
| `fe8376f` | 20 Agt | yulimuliadinah | modified traffic state buildeer |
| `db33771` | 19 Agt | yulimuliadinah | modifies backend and frontend |
| `d3a1f06` | 19 Agt | yulimuliadinah | samaain variabel dan fitur be-fe-cv dan build traffic state builder |
| `a36639c` | 18 Agt | yulimuliadinah | nambah feature sensor diagnostic yolo |
| `9f9a54c` | 17 Agt | Rahmat Isma | feat(simulation): Traffic State Builder — CSV per-detik jadi TrafficState per window |
| `c094be1` | 17 Agt | Rahmat Isma | perbaiki field ApproachState yang salah klaim satuan dan wajib tanpa data |
| `88ae3d3` | 17 Agt | yulimuliadinah | update training lstm with new data yolo |
| `4d2860b` | 17 Agt | yulimuliadinah | training lstm with new vs yolo data |
| `e2769d2` | 17 Agt | Rahmat Isma | docs(roadmap): tambah checkpoint keputusan PPO — MVP dulu, gerbang 26 Agustus |

**Yang perlu diperhatikan dari pola commit ini:**

- **Ada anggota tim keempat yang tidak ada di daftar tiga orang: `Santi Melvira`** (11 commit, semua frontend). Kalau ini Melpi dengan nama git yang berbeda, artinya pemegang track CV sedang mengerjakan frontend — dan track CV kehilangan pemiliknya justru saat north belum dikalibrasi.
- Rahmat mengerjakan **CV + CCTV integration**, bukan SUMO. Commit SUMO terakhir dari siapa pun adalah `9f9a54c` — **17 Agustus, lima hari lalu**. Track simulasi berhenti persis di titik yang paling menentukan nilai kompetisi.
- Tidak ada satu pun commit yang menyentuh Scenario Generator atau Decision Engine.
- **9 hari kerja tersisa, dan pekerjaan tahap 5–6 belum dimulai.**

---

## Temuan Baru (Tidak Ada di Roadmap)

Semua ini pekerjaan nyata yang sudah selesai tapi belum tercatat di `docs/roadmap.md`:

**Pipeline CCTV web (paling besar, ~1.200 baris) — tidak ada sama sekali di rencana**
- `cv/process_uploaded_video.py` (622) — proses 1 video → Supabase per 5 detik + video anotasi H.264 lewat imageio-ffmpeg
- `cv/reprocess_all.py` (303) — **untracked**, antrean batch semua video yang belum diproses
- `cv/supabase_writer.py` (214), `cv/hf_writer.py` (67)
- `backend/app/api/routes/cctv.py` (355) — upload streaming, proxy stream, cache video di disk
- `backend/app/services/cctv_service.py` (181), `cv_trigger_service.py` (193), `hf_storage_service.py` (89)
- Hugging Face Hub sebagai object storage video — **tidak ada di stack teknologi roadmap**

**WebSocket realtime buatan sendiri**
- `backend/app/services/ws_manager.py` (46) + `/api/v1/traffic/ws` + `POST /notify`
- Diputuskan setelah Supabase Realtime terbukti tidak mem-broadcast `postgres_changes` di project ini. Keputusan arsitektur yang belum tercatat di mana pun kecuali komentar kode.

**Replay demand CSV → SUMO**
- `simulation/replay_from_csv.py` (534) + `outputs/replay_demand.rou.xml` (7.681 kendaraan)
- Roadmap menandai item B ("Generator demand CV → SUMO") sebagai **0%**, padahal sudah jalan. Perlu dinaikkan.

**Dua Traffic State Builder, bukan satu**
- `simulation/traffic_state_builder.py` (478) — window 5 **menit**, queue di-max
- `backend/app/pipeline/traffic_state_builder.py` (779) — window 5 **detik**, queue di-sum
- Roadmap menandai item A sebagai "25% (skema saja, logika agregasi 0%)" — jauh dari kondisi sebenarnya, tapi sekaligus menyembunyikan bahwa keduanya saling bertentangan.

**Skema database 20 tabel**
- `docs/database.md` (1.557 baris) — DDL, ERD, index, mapping ke data contract, fase MVP
- Roadmap tidak menyebut adanya desain database sama sekali.

**7 halaman frontend + 21 komponen yang tidak direncanakan**
- Auth (`/login`, `/register`), `/account` + 3 komponen, `/settings` + 8 komponen (AI, Appearance, CCTV, Notification, Profile, Security, Traffic), `/cctv` monitoring
- Route handler Next.js `/api/cameras` + `/api/cameras/[id]`, middleware proxy (`src/proxy.ts`)
- Roadmap tidak pernah menyebut autentikasi maupun halaman pengaturan.

**7 eksperimen LSTM YOLO tambahan** — `05`–`12` di `forecasting/scripts/yolo/`, termasuk baseline, error analysis, dan tiga eksperimen hyperparameter/sequence/horizon.

**Infrastruktur & dokumen lain**
- `backend/docs/traffic-state-builder.md`, `backend/docs/data-contract.md` (salinan kedua dari `docs/data-contract.md` — sumber kebenaran jadi ganda)
- `frontend/CLAUDE.md` + `frontend/AGENTS.md`, `.vscode/settings.json`
- 7 file test backend baru (`test_supabase_connection`, `test_database_tables`, `test_traffic_service`, `test_traffic_state_builder`, `test_traffic_state_repository`, `test_sumo_adapter`, `test_database_connection`)
- venv CUDA terpisah di luar repo (`E:/KMIPN 2026/venv-cuda`) yang di-hardcode di `cv_trigger_service.py` dengan fallback CPU

**`docker/` masih kosong** — cuma `.gitkeep` + `README.md`. Sama seperti 17 Agustus.

---

## Risiko Kritis Saat Ini

**1. Database tidak pernah memuat empat lengan dalam satu window — dashboard tidak bisa didemokan utuh**
`{1: 5314}` — setiap `trafficState` cuma punya satu approach, karena tiap video diproses di waktu wall-clock berbeda dan `process_uploaded_video.py` memakai `datetime.now()` sebagai timestamp window, bukan jam rekaman. Empat lengan tidak akan pernah bertemu di window yang sama, berapa kali pun video diproses ulang. Ini bukan bug yang muncul di produksi — ini konsekuensi desain yang harus diputuskan ulang. **Tanpa perbaikan ini, demo hari-H menampilkan simpang dengan satu lengan.**

**2. Dua Traffic State Builder yang tidak sepakat, dan yang satu rusak**
`simulation/traffic_state_builder.py` crash begitu dijalankan:
```
AttributeError: 'str' object has no attribute 'value'   (baris 352)
```
Penyebabnya `backend/app/schemas/traffic.py` mengubah `approach` dari `Approach` (Enum) jadi `str` — persis skenario yang dicegah oleh keputusan "impor skema dari backend supaya cuma ada satu definisi". Mekanismenya bekerja (impornya gagal, bukan diam-diam salah), tapi tidak ada yang memperbaikinya.
Lebih berbahaya: kedua builder menghitung antrean dengan cara berbeda. Diuji pada window south `16:31:00–16:31:05` yang sama:

| | Hasil |
|---|---:|
| Cara backend (`.sum()` seluruh baris window) | **15** |
| Cara simulation (sum antar lajur, max antar detik) | **3** |

Data mentahnya 3 kendaraan antre yang sama, terlihat selama 5 detik berturut-turut. Backend menjumlahkan kehadiran yang sama lima kali. **Angka antrean yang tampil di dashboard sekarang bisa 5× lebih besar dari kenyataan** — dan antrean adalah metrik utama yang dipakai untuk membenarkan rekomendasi sinyal.

**3. Tahap 5 dan 6 belum dimulai, tersisa 9 hari**
Scenario Generator dan Decision Engine adalah **inti klaim "optimasi sinyal adaptif"**. Nol baris kode untuk keduanya. Tanpa keduanya, yang bisa ditunjukkan hanyalah dashboard monitoring — dan itu tidak menjawab judul proyek. Roadmap menjadwalkannya di Fase 2 (22–25 Agustus, yaitu **mulai hari ini**) dan Fase 3.

**4. Baseline simulasi belum sah — 41,1% demand tidak pernah masuk jaringan**
4.525 dari 7.681 kendaraan tertahan di mulut lengan. `DepartDelay` rata-rata 606 detik. Setiap klaim "rekomendasi kami menurunkan delay X%" akan dibandingkan terhadap baseline yang **sendirinya belum valid** — juri yang teliti akan menemukan ini. Perlu diselidiki apakah penyebabnya program TLS default network, kapasitas lengan, atau volume north yang memang belum terkalibrasi (3.183 crossing, tertinggi, dan justru lengan yang garisnya masih default).

**5. Empat route backend jadi kode mati, dan jalur simpan TrafficState rusak**
`signal`, `recommendation`, `forecast`, `health` tidak pernah di-`include_router` — sudah ditulis, tidak pernah bisa dipanggil. `history.py` dan `simulation.py` file kosong. Sementara itu `test_traffic_state_repository` gagal karena `model_dump(exclude={"approach"})` melanggar constraint NOT NULL: **backend tidak bisa menulis TrafficState ke database**. Yang mengisi 5.314 baris itu `cv/supabase_writer.py`, jalur yang sama sekali berbeda. Artinya ada dua jalur tulis dan hanya satu yang berfungsi.

**Risiko sekunder yang perlu dicatat tapi belum kritis:** `docs/data-contract.md` (snake_case, `Approach` sebagai `Literal`) sudah **tidak cocok** dengan `backend/app/schemas/traffic.py` (camelCase, `approach: str`) yang jadi implementasi nyata — plus ada salinan ketiga di `backend/docs/data-contract.md`. Kontrak yang seharusnya jadi sumber kebenaran antar-anggota tim kini menggambarkan sistem yang tidak ada.

---

## Yang Harus Diselesaikan Minggu Ini (22–25 Agustus)

Diurutkan dari yang paling menentukan hasil kompetisi. Empat hari, jadi ini sudah dipangkas ke yang benar-benar wajib.

### Prioritas 1 — Satukan Traffic State Builder (½ hari, Rahmat + Yuli bersama)
Tidak boleh ada dua. Pilih satu, hapus yang lain, dan pastikan **semantik antreannya yang benar** (max antar detik, bukan sum) — versi `simulation/` yang benar di sini, versi backend yang salah. Perbaiki `AttributeError` di baris 352 sekaligus. Sinkronkan `docs/data-contract.md` dengan skema yang benar-benar dipakai, dan hapus salinan `backend/docs/data-contract.md` supaya sumber kebenarannya tunggal lagi. **Kerjakan ini duluan** — semua angka di dashboard dan semua keputusan Decision Engine bergantung padanya.

### Prioritas 2 — Perbaiki window supaya memuat empat lengan (1 hari, Rahmat)
Ganti `datetime.now()` di `process_uploaded_video.py` dengan timestamp rekaman (jalur yang sudah terbukti di `vehicle_counter.py` lewat `sync_report.json`), lalu bereskan `TrafficStateRepository.save_state()` yang melanggar constraint `approach` NOT NULL. Target yang bisa diperiksa: `distribusi jumlah approach per trafficState` berubah dari `{1: N}` jadi `{4: N}`. Setelah itu tulis ulang 5.314 baris yang ada — atau kosongkan dan isi ulang dari CSV, mana yang lebih cepat.

### Prioritas 3 — Scenario Generator + Decision Engine rule-based (2 hari, Rahmat)
Ini yang menentukan apakah proyek ini digital twin atau dashboard. Bentuk paling sederhana yang tetap jujur:
- **Scenario Generator**: dari satu `TrafficState`, hasilkan 3–5 kandidat pembagian green time (misal proporsional terhadap volume per lengan, ±20% dari fixed-time), jalankan tiap kandidat lewat `replay_from_csv.py` yang sudah ada, panen `avg delay` / `avg queue` / `throughput` jadi `ScenarioResult`.
- **Decision Engine**: pilih skenario dengan delay terendah, keluarkan `SignalRecommendation` dengan `engine="rule-based"`, dan **isi `reason` dari angka yang nyata**, bukan kalimat template seperti sekarang.

Infrastrukturnya sudah ada — `replay_from_csv.py` sudah bisa menjalankan SUMO headless dan melaporkan angka. Yang kurang cuma loop di atasnya.

### Prioritas 4 — Selidiki 41,1% (½ hari, Rahmat, boleh paralel dengan P3)
Sebelum P3 dipakai untuk mengklaim perbaikan apa pun, cari tahu kenapa 4.525 kendaraan tertahan. Tiga tersangka, cek berurutan: (a) program TLS default network terlalu pendek, (b) `departLane="best"` + kapasitas mulut lengan, (c) volume north 3.183 memang kelebihan karena garisnya masih default. Kalau (c), kalibrasi north naik jadi prioritas — dan itu pekerjaan CV, bukan simulasi.

### Prioritas 5 — Pasang route yang sudah ada + arahkan frontend ke backend (½ hari, Yuli)
Tambahkan empat `include_router()` yang hilang di `main.py`, isi atau hapus `history.py`/`simulation.py` yang kosong. Lalu ganti `fetchTrafficState()` di `supabaseData.ts` supaya memanggil `GET /api/v1/traffic/state`, bukan Supabase langsung — supaya hanya ada **satu** jalur pembentukan TrafficState di sistem ini, bukan dua yang bisa berbeda hasilnya. Begitu Decision Engine jadi, `RecommendationPanel` tinggal disambungkan.

### Yang sebaiknya TIDAK dikerjakan minggu ini
- **`forecasting/scripts/yolo/`** — 12 skrip yang input-nya bahkan tidak ada di disk. Perbaiki path-nya jadi `cv/output/smarttwin_traffic_data.csv` (satu baris, 5 menit) supaya tidak jadi utang, lalu tinggalkan sampai setelah 26 Agustus. LSTM sudah di luar scope aktif dan PeMS04/TMU sudah cukup sebagai bukti laporan.
- **`docker/`** — masih kosong dan memang tidak dibutuhkan untuk demo lokal.
- **Halaman `/settings` dan `/account`** — sudah 11 komponen untuk fitur yang tidak dinilai juri. Cukup.
- **PPO** — gerbang keputusannya 26 Agustus, dan dari kondisi hari ini jawabannya sudah bisa ditebak. Jangan buka lebih awal.

### Satu hal administratif
`cv/reprocess_all.py` (303 baris) **masih untracked**, dan ada 9 file termodifikasi yang belum di-commit. Kalau laptop yang memegangnya bermasalah, pekerjaan itu hilang. Commit hari ini.

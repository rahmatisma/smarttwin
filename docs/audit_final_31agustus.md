# AUDIT MENYELURUH FINAL — 31 Agustus 2026

**Metodologi:** audit read-only, dijalankan langsung terhadap kode di HEAD (`abed968`, dicek 31 Agustus malam / 1 September dini hari), termasuk query langsung ke database Supabase produksi (`cjxsuodiivriifetvrir`), `pytest` sungguhan, `git log`/`git diff` atas commit asli, dan satu kali run offline nyata dari Scenario Generator + Decision Engine. Tidak ada perbaikan kode yang dilakukan selama audit ini.

> ⚠️ **Koreksi premis di awal.** Prompt audit ini merujuk "roadmap.md, terakhir disinkronkan 22 Agustus". Dua hal perlu diluruskan: (1) `roadmap.md` **sudah dihapus 28 Agustus** (commit `9387c13`) karena isinya bertentangan dengan dokumen lain — digantikan oleh `docs/STATUS-DAN-SISA-KERJA.md`. (2) Dokumen pengganti itu sendiri **terakhir diperbarui 29 Agustus malam**, bukan 22 Agustus — jadi actually sudah ada 1 siklus audit-ulang formal antara 22 Agustus dan hari ini yang statusnya sudah jauh lebih maju dari asumsi awal prompt. Audit ini mem-verifikasi ulang state per 31 Agustus terhadap dokumen 29 Agustus itu, bukan terhadap roadmap 22 Agustus yang sudah tidak ada.

---

## 1. Ringkasan eksekutif

**Bisa didemoin end-to-end dari browser sekarang? SEBAGIAN, dengan satu regresi baru yang harus diperbaiki sebelum rekaman.**

Rantai CV → Traffic State → Supabase → Scenario Generator (SUMO) → Decision Engine → dashboard **terbukti hidup dan menghasilkan angka nyata** (lihat bagian 2 & 4). Tapi **dini hari 31 Agustus (01:53–01:56), dua commit revert** (`8f066c7`, `abed968`, oleh Yuli) menghapus total 2 perbaikan dashboard yang sebelumnya sudah selesai dan terverifikasi — salah satunya membuat panel Digital Twin kembali auto-start SUMO dan memakai polling gambar 2fps yang patah-patah, persis bug yang sudah diperbaiki 29 Agustus. Build frontend **tetap hijau** (13/13 route, terverifikasi barusan) — reverts ini tidak merusak build, hanya memunculkan kembali 2 bug perilaku. Detail lengkap di bagian 3 (Frontend) dan bagian 6.

### Tabel bobot per kotak diagram (diperbarui dari `STATUS-DAN-SISA-KERJA.md` 29 Agustus, diverifikasi ulang 31 Agustus)

| # | Kotak diagram | % (29 Agt) | % (31 Agt, verifikasi audit ini) | Perubahan |
|---|---|---:|---:|---|
| 1 | Traffic Monitoring Data | 100% | 100% | Tidak berubah |
| 2 | YOLO + ByteTrack | 60% | 60% | Tidak berubah — 48,7% akurasi tetap berlaku, tidak ada commit CV baru sejak revert P-5 |
| 3 | Traffic State Builder | 90% | 95% | **Naik** — dualitas 2 jalur paralel yang tadinya ambigu sekarang didokumentasikan eksplisit sebagai runtime vs legacy (lihat 2.2) |
| 4 | Virtual Intersection (SUMO) | 100% | 100% | Tidak berubah, network kanonik terverifikasi masih satu-satunya |
| 5 | Realtime Traffic State | 90% | 90% | Tidak berubah |
| 6 | Traffic Forecast (LSTM) | 92% | 92% | Tidak berubah secara fungsi; bukti multi-snapshot diperluas 10→20 (30 Agustus) |
| 7 | Scenario Generator | 90% | 90% | Dikonfirmasi hidup lewat run nyata hari ini (bagian 2.3) |
| 8 | Traffic Simulation | 92% | 92% | Tidak berubah |
| 9 | Performance Analysis (LOS) | 90% | 85% | **Turun** — dikonfirmasi P-3 (LOS per lengan) masih belum dikerjakan DAN validasi PKJI 2023 formal tidak pernah ada (lihat 3.2) |
| 10 | Adaptive Decision Engine (PPO) | 70%/90% | 70%/90% | Tidak berubah — v5 tetap menang 7/seri 2/kalah 0, tetap opt-in |
| 11 | Signal Timing Recommendation | 90% | 90% | Tidak berubah |
| 12 | Dashboard | 92% | **80%** | **Turun — regresi baru** (lihat ringkasan di atas & bagian 3) |

**Keseluruhan: ≈86% harfiah (turun tipis dari ≈87% karena regresi dashboard, ditutupi kenaikan kotak 3).**

**Yang benar-benar bisa ditunjukkan ke juri hari ini, apa adanya:** rantai CCTV → deteksi kendaraan → 4 lengan tersimpan ke Supabase dengan volume/antrean asli → Scenario Generator menjalankan SUMO sungguhan dan menghasilkan 3 kandidat dengan delay/antrean/throughput berbeda → satu kandidat dipilih dan tampil di dashboard dengan badge sumbernya. PPO sudah dilatih dan menang di simulasi SUMO (7/9) tapi belum dipakai produksi. **Sebelum merekam, perbaiki dulu regresi DigitalTwinPanel** (bagian 6) — kalau tidak, panel akan auto-start SUMO tanpa diminta dan videonya patah-patah, persis masalah yang juri tidak akan lihat kalau reverts ini tidak dibatalkan.

---

## 2. Blocker-blocker kritis — dicek satu per satu, dengan bukti

### 2.1. Database 1-lengan per window

> **BERUBAH DARI ASUMSI SEBELUMNYA — blocker ini SUDAH SELESAI, terverifikasi lewat query langsung ke database produksi.**

Query langsung ke Supabase (`project cjxsuodiivriifetvrir`):

```sql
select approach_count, count(*) as num_windows
from (
  select "trafficStateId", count(distinct approach) as approach_count
  from "trafficApproachStates"
  group by "trafficStateId"
) t
group by approach_count;
```

**Hasil: `{"approach_count": 4, "num_windows": 538}` — SATU baris saja.** Seluruh 538 window `trafficStates` yang ada punya persis 4 approach (2.152 baris `trafficApproachStates` = 538 × 4, cocok persis). Tidak ada satu pun window 1-lengan di database saat ini.

**Soal timestamp rekaman vs `datetime.now()`:** ada 2 jalur berbeda, dan keduanya benar untuk konteksnya masing-masing:
- **Jalur produksi utama** (`cv/vehicle_counter_pingit.py`, 4 kamera): memanggil `muat_peta_jam()` yang membaca `sync_report.json` dan **gagal keras** kalau video tidak tercatat di situ — komentar di kode eksplisit: *"GAGAL KERAS kalau videonya tidak tercatat di sync_report.json — supaya jam laptop tidak pernah menyamar jadi jam rekaman"* (`cv/vehicle_counter_pingit.py:1392-1403`). Ini memakai timestamp rekaman asli.
- **`cv/process_uploaded_video.py`** (jalur ad-hoc upload 1-video dari halaman CCTV, BUKAN jalur 4-kamera produksi): sengaja pakai `datetime.now(timezone.utc)` — didokumentasikan eksplisit di docstring baris 9-11: *"tidak menyentuh sync_report.json / jam rekaman -> timestamp window pakai wall-clock ... supaya dashboard terasa 'baru saja terdeteksi'"*. Ini keputusan desain, bukan bug — video upload ad-hoc memang tidak punya entri sync_report.

### 2.2. Traffic State Builder ganda

> **BERUBAH DARI ASUMSI SEBELUMNYA — sudah didisambiguasi 30 Agustus, bukan lagi dua jalur paralel yang ambigu.**

Commit `737b7ec` (30 Agustus) menambah komentar eksplisit di `backend/app/pipeline/traffic_state_builder.py`:

> *"JALUR RUNTIME AKTIF. Builder ini membaca trafficLaneMetrics di Supabase dan menulis agregasi trafficApproachStates ... `simulation/traffic_state_builder.py` adalah alat offline/legacy CSV → JSON dan tidak dipakai oleh backend, API, atau scenario worker produksi."*

`simulation/traffic_state_builder.py` juga diberi header serupa: *"JALUR OFFLINE/LEGACY, BUKAN RUNTIME PRODUKSI ... Jalur aktif adalah cv_csv_bridge.py (CSV → Supabase), lalu backend/app/pipeline/traffic_state_builder.py (Supabase → TrafficState). Scenario worker dan API tidak membaca output JSON script ini."*

Kedua file memang masih ada di repo (satu untuk replay CSV lama, satu untuk runtime), tapi **hierarkinya sudah jelas dan didokumentasikan** — bukan lagi ambiguitas yang berisiko selisih 5x tanpa disadari. Tidak perlu dibandingkan lagi angka keduanya karena hanya satu yang benar-benar dipakai produksi.

### 2.3. Scenario Generator + Decision Engine rule-based — dijalankan nyata hari ini

> **Terverifikasi hidup, bukan hardcoded.** Dijalankan offline (tanpa tulis ke Supabase) lewat `simulation/scenario_worker.py::evaluate_state()`, yang didokumentasikan eksplisit *"fungsi ini tidak menyentuh cache/database"*. SUMO sungguhan dipanggil (`simpang4_pingit.net.xml.gz`, 90 langkah simulasi per kandidat).

**Output nyata (3 kandidat dibandingkan, snapshot TrafficState sintetis):**

| candidateId | green (s) | delay (s) | antrean (m) | throughput | LOS |
|---|---:|---:|---:|---:|---|
| baseline | 60 | 16,25 | 70,0 | 6 | B |
| aggressive | 60 | 16,25 | 70,0 | 6 | B |
| **balanced (menang)** | **38** | **15,68** | **56,0** | **8** | **B** |

Rekomendasi yang dihasilkan: `recommendedPhase="north"`, `recommendedGreenSeconds=38`, `source="scenario-generator"`, `expectedDelayReductionPercent=3,51`. Ini konsisten dengan `select_best_scenario()` di `simulation/scenario_generator.py` (bobot 50% delay / 50% antrean, dinormalisasi ke nilai terburuk batch — didokumentasikan sebagai heuristik proyek, bukan formula HCM, sejak commit `737b7ec`).

`recommendation.py`, `signal.py` **terdaftar dan aktif** di `main.py` (`app.include_router(signal_router)` baris 155, `app.include_router(recommendation_router)` baris 159) — dikonfirmasi lewat `pytest backend/tests -q` **92 passed, 0 failed** (dijalankan langsung, lihat bagian 3.3).

### 2.4. Baseline demand 41,1%

> **BERUBAH DARI ASUMSI SEBELUMNYA — premis ini tidak ditemukan di kode/dokumen manapun.**

Pencarian menyeluruh (`grep -ri "41,1\|41.1%\|baseline.*demand"` di seluruh `docs/`, `simulation/`, dan `git log --all` untuk pesan commit yang menyebut baseline/demand) hanya menemukan **satu** kecocokan angka: `docs/hasil-validasi-akurasi-cv.md:31` — itu adalah **akurasi deteksi CV** untuk sampel Barat/CCTV_3 kondisi sepi (41,1%), **bukan** angka terkait demand SUMO sama sekali. `simulation/replay_from_csv.py` (dicek: tidak ada import Supabase, murni lokal CSV→SUMO) tidak menghasilkan angka persentase serupa di dokumentasi manapun.

**Kesimpulan: kemungkinan besar salah ingat dari angka akurasi CV 41,1% (Barat, sepi) yang kebetulan mirip formatnya**, bukan metrik SUMO yang pernah ada di repo ini. Tidak ada yang perlu "dijalankan ulang" karena skrip/metriknya tidak pernah ada.

### 2.5. Route mati

Dicek langsung ke `backend/app/main.py`:

| Route file | Baris kode | Terdaftar di `main.py`? |
|---|---:|---|
| `signal.py` | 27 | ✅ baris 155 |
| `recommendation.py` | 66 | ✅ baris 159 |
| `simulation.py` | 84 | ✅ baris 163 |
| `forecast.py` | 183 | ✅ baris 178, **kondisional** — dibungkus `try/except` (baris 55-71) supaya kegagalan model forecast tidak mematikan seluruh backend. Diverifikasi barusan: import berhasil bersih (`OK: forecast router imports cleanly`) |
| `digital_twin.py` | — | ✅ baris 166 |
| `history.py` | **0 baris — file benar-benar kosong** | ❌ **Tidak pernah diimpor di mana pun** (`grep` untuk `history_router`/`routes.history` di seluruh `backend/`: nol hasil) |

`history.py` kosong dan tidak terdaftar **sesuai keputusan sadar** yang sudah didokumentasikan di `STATUS-DAN-SISA-KERJA.md` bagian 5: *"Halaman History — Di luar scope demo, data mock boleh dibiarkan"*. Bukan bug, bukan pekerjaan terlupa.

---

## 3. Status per modul (evidence-based)

### 3.1. CV pipeline

- **Kalibrasi `north`**: ada 2 hal yang perlu dipisah. (a) **Bug key-matching sudah diperbaiki** — `LAJUR_PER_LENGAN` sempat pakai key `"utara"` padahal `nama_lengan` CCTV_2 sungguhan adalah `"simpang_tengah"`, sehingga north diam-diam jatuh ke default 1-lajur. Diperbaiki commit `5b2c18e` (25 Agt). (b) **Proxy-nya sendiri tidak berubah** — CCTV_2 secara fisik memantau `simpang_tengah` (tengah persimpangan), bukan kamera utara khusus; ini `northDataNote` yang sudah didokumentasikan sebagai keterbatasan sadar, bukan resolved sepenuhnya kalau dibaca sebagai "utara sungguhan".
- **Identitas koridor `east` (Diponegoro vs Magelang)**: **tertutup lewat bearing independen**, bukan cuma klaim. `simulation/verify_corridor_bearing.py` menghitung bearing dari geometri edge OSM (independen dari kalibrasi manual) dan mengonfirmasi Diponegoro→east (74,5°–93,0°), Magelang→north (351,8°–6,3°) — cocok dengan `CROSS_LABEL_MAP` di `cv_csv_bridge.py:59-64`. Ditambahkan commit `700140c` (24 Agt).
  > Catatan: memori proyek "Dua kandidat garis east sudah gagal" merujuk masalah **berbeda** (kemurnian geometri garis hitung CCTV_4, 16 Agustus) — sudah diverifikasi tidak terkait dengan identitas koridor ini.
- **Volume final per lengan** (dihitung langsung dari `cv/output/crossing_simpang.csv`, 2.152 baris, 15 Agt 16:30:10–17:19:15, ~49 menit): **Timur (Diponegoro) 1.132**, **Utara (Magelang) 1.234**, **Selatan 573**, **Barat 1.505** crossing. Angka ini belum pernah dikutip persis di dokumen manapun — dihitung ulang langsung dari data mentah untuk audit ini.
- **Akurasi CV 48,7% masih berlaku.** Tidak ada commit yang menyentuh logika akurasi/CV sejak revert P-5 (29 Agustus) kecuali `ef98482` (perubahan path `.env`, 6 baris, tidak menyentuh logika). `git diff` antara kode sekarang dan `git show 9387c13:cv/vehicle_counter_pingit.py` (baseline pre-P-5) untuk commit revert `8f70726` **kosong** — revert-nya presisi. Divergensi yang ada sekarang murni fitur S-5 (`--sumber` RTSP-ready, commit `57530c2`), bukan regresi P-5.

### 3.2. SUMO/Digital Twin

- **20 commit** menyentuh `simulation/`, `decision_engine/`, atau `backend/app/simulation/` sejak 29 Agustus 21:00 — termasuk seluruh rantai perbaikan Bug E–P PPO (`a87f48f`→`7c62f2a`) dan konsolidasi venv.
- **TLS control jalan** — dikonfirmasi via run nyata di bagian 2.3 (SUMO benar-benar disimulasikan, bukan angka statis).
- **Network kanonik**: `simulation/network/` hanya berisi `simpang4_pingit.net.xml.gz` (+ `.sumocfg`, `tls_safe.add.xml`) — tidak ada file network lain yang muncul kembali sejak network Bandung lama dihapus (`8687e4c`). Tidak ada regresi.
- **Validasi PKJI 2023 — TIDAK PERNAH ADA sebagai studi formal.** `grep -ri PKJI` di seluruh repo hanya mengenai 4 file (`frontend/src/components/StatsRow.tsx`, `cv/vehicle_counter_pingit.py`, `cv/CATATAN.md`, `cv/vehicle_counter.py`), semuanya komentar informal soal ambang kepadatan visual (mis. *"LOS resmi PKJI"* di komentar `StatsRow.tsx:27`, bukan hasil hitungan). Tidak ada dokumen capacity/degree-of-saturation/LOS yang membandingkan ke standar PKJI, dan tidak ada cross-check ke penelitian "Simpang Pingit" manapun ditemukan di repo. **Ini item yang secara eksplisit dicoret dari roadmap 22 Agustus** ("Untuk membuka ~9 od, yang harus dihapus: validasi PKJI 2023 (3 od) ...") — jadi statusnya konsisten: sengaja tidak dikerjakan, bukan lupa.
- **LOS yang ada** dihitung `calculate_los(avg_delay_s)` (`simulation/scenario_generator.py:121`) dari **delay rata-rata seluruh simpang**, bukan per lengan. P-3 (LOS per lengan) **masih belum dikerjakan** — dikonfirmasi langsung dari kode, fungsi masih menerima satu skalar.

### 3.3. Backend

- **101 file Python** (di luar `.venv`/`__pycache__`), naik dari 22 di awal (17 Agustus).
- **`pytest backend/tests -q` → 92 passed, 0 failed**, dijalankan langsung untuk audit ini (bukan dikutip dari dokumen lama). Termasuk `test_save_traffic_state` (bagian dari `test_traffic_state_repository.py`, 15 test, semua lulus).
- **`pytest simulation/tests -q` (dengan `SUMO_HOME` di-set) → 15 passed, 0 failed**, juga dijalankan langsung.
- **Checkpoint PPO ter-commit**: `decision_engine/models/smarttwin_ppo.zip` ada di `git ls-files`, ukuran **197.471 byte**, dikonfirmasi ini adalah checkpoint **v5** (bukan v1 basi) lewat commit `7c62f2a` ("...promosikan checkpoint 60k jadi model default") dan `smarttwin_ppo_v5.training.json` yang menyatakan `modelTotalTimesteps: 60000`.

### 3.4. Frontend

- **Build hijau**: `npm run build` sukses, 13 route, 0 error TypeScript — dikonfirmasi langsung.
- **Tidak ada mockData aktif**: pencarian string `"mock"` di seluruh `frontend/src` menghasilkan 9 kecocokan, seluruhnya adalah nilai literal `source: "mock"` untuk state fallback/offline `SignalStatus` (label status, bukan data palsu) plus satu komentar kode. Tidak ada array data hardcode di komponen manapun yang aktif.
- **4 lengan ditampilkan sekaligus dengan data asli**: `page.tsx` mengambil data lewat `fetchTrafficState`/`fetchSignalStatus`/`fetchRecommendation`/`fetchForecast` dari `lib/supabaseData.ts`. `DigitalTwinPanel.tsx` merender 4 approach lewat `byApproach`/`queueOf` (baris 401-426). `CameraFeedPanel`, `RecommendationPanel`, `StatsRow`, `ForecastChart` semuanya konsumer props/fetch murni, tanpa data mock internal.

> ⚠️ **TEMUAN KRITIS — regresi baru, terjadi 31 Agustus 01:53–01:56, belum diperbaiki.**
>
> Dua commit revert di ujung HEAD (`8f066c7` membalik `ca609cc`, `abed968` membalik `5e4fa5e`) **menghapus total dua perbaikan yang sebelumnya sudah selesai dan terverifikasi**. Dikonfirmasi lewat `git diff 5e4fa5e~1 HEAD -- frontend/src/components/DigitalTwinPanel.tsx` yang menghasilkan **nol baris beda** — file itu sekarang byte-identik dengan kondisi SEBELUM perbaikan 29 Agustus.
>
> **Yang kembali rusak:**
> 1. `DigitalTwinPanel.tsx` **auto-start SUMO** begitu melihat data 4-lengan (`useEffect` baris 340-376), padahal backend cuma punya 1 slot SUMO — panel `/digitaltwin` bisa menunjukkan "Running" walau user tidak pernah menekan Start.
> 2. `DigitalTwinPanel.tsx` **kembali polling gambar 500ms (2fps, patah-patah)** lewat `<img src=".../simulation/frame?v=...">` (baris 486) — endpoint MJPEG `.../stream` (10fps) yang lebih mulus tidak lagi dipakai.
> 3. `traffic.py`: kasus khusus `simpang4-pingit` tanpa histori (return list kosong, bukan 404) **hilang** — bisa memicu 404 yang merembet ke fallback forecast.
> 4. `RecommendationPanel.tsx`: state eksplisit "Rekomendasi belum tersedia" **hilang**, kembali ke spinner loading tanpa batas kalau rekomendasi tidak pernah datang.
> 5. `SharedSignalPanels.tsx`: grace period loading 2,5 detik **hilang**.
> 6. `CameraFeedPanel.tsx`: kembali ke satu jam master global — menggeser scrubber 1 CCTV **menarik semua kamera lain** ke timestamp yang sama (bug cross-camera time bleed yang sudah pernah diperbaiki, sekarang kembali).
>
> Build tetap hijau karena ini regresi *perilaku*, bukan regresi *kompilasi* — tidak akan terdeteksi lewat `npm run build` atau `pytest`, hanya lewat pemakaian manual di browser.

**Independen dari revert di atas** — dicek langsung ke kode `digitaltwinview.tsx` untuk rencana perbaikan P-1e (`docs/rencana-perbaikan-digital-twin-scenario.md`):

| Masalah P-1e | Status sekarang | Bukti |
|---|---|---|
| Masalah 1 — backend reuse controller lama saat skenario ganti | ✅ **Sudah diperbaiki**, tidak terdampak revert | `simulation_service.py:372-374` — kondisi restart sudah termasuk `self.controller.scenario != request.scenario`, commit `1cf0124` (terpisah dari revert) |
| Masalah 2 — dropdown skenario nyangkut "Loading..." | ❌ **Masih belum diperbaiki** | `digitaltwinview.tsx:702-715` — `onChange` masih hanya `setRecommendationLoading(true)`, **tidak pernah memanggil** `handleStartSimulation()`. Kalau simulasi sedang "running" dan skenario diganti, panel Rekomendasi akan nyangkut loading — reproducible sekarang juga |
| Masalah 3 — kartu Queue Length/Traffic Flow kosong | ❌ **Masih belum diperbaiki** | `digitaltwinview.tsx:642-654` — masih hardcode `value="-"` `change="Data belum tersedia"` |

### 3.5. LSTM

- **Tidak ada perubahan arsitektural sejak 29 Agustus.** Satu commit relevan: `737b7ec` (30 Agt) — retrain dicoba dengan split kronologis 60/15/25, tapi MAE memburuk (2,0440 vs naive 2,0720), sehingga **tim sengaja kembali ke checkpoint lama** (split 70/15/15, MAE 1,6528 vs naive 2,2973). Bukti dampak operasional diperluas dari 10 → **20 snapshot**: delay membaik 20/20, antrean 17/20, throughput 19/20, ketiganya bersamaan 17/20.
- **R² PeMS04 ≈0,8786** dan **MAPE TMU** (speed 2,09%, vehicle_count 25,6%) masih terdokumentasi di `forecasting/README.md:359-361` sebagai klaim tertulis.
  > ⚠️ **Temuan baru, di luar cakupan pertanyaan asli**: file bukti mentah untuk PeMS04/TMU/Brisbane (`.pth`, plot evaluasi, `evaluation_summary.json`, `.npy` proses) **sudah dihapus dari repo sejak 25 Agustus** (commit `355fabc`) — kemungkinan karena ukuran file besar (`X_train.npy` PeMS04 sampai 42MB). CLAUDE.md masih menyatakan file-file ini "kept as evidence ... committed with git add -f", tapi itu **sudah tidak akurat untuk kondisi repo saat ini**. Angka-angkanya bertahan sebagai teks di `forecasting/README.md`, tapi tidak ada lagi plot/JSON mentah PeMS04 atau TMU yang bisa dilampirkan langsung ke slide — hanya `forecasting/outputs/lstm/plots/training_validation_loss.png` dan versi per-approach-nya yang tersisa (keduanya untuk model utama, bukan PeMS04/TMU).
- **`forecasting/outputs/yolo/` tidak ada sama sekali** — path LSTM-YOLO belum pernah diisi, konsisten dengan status "belum training" untuk jalur itu.

### 3.6. PPO

**v5 tetap berlaku, tidak ada perkembangan baru sejak 30 Agustus malam** — dikonfirmasi ulang hari ini:
- `docs/hasil-evaluasi-ppo-v5.md` ada, angka headline **menang 7, seri 2, kalah 0** dari 9 perbandingan (3 metrik × 3 seed) dikonfirmasi verbatim.
- Antrean: −46,4% s/d −50,6% (menang 3/3). Waktu tunggu: −60,2% s/d −63,2% (menang 3/3). Throughput: +2,18% (menang) di seed 1000, seri (di bawah ambang) di 2 seed lain.
- `decision_engine/engine_factory.py:19` — tetap `os.getenv("SMARTTWIN_DECISION_ENGINE", "rule-based")`, default rule-based, PPO tetap **opt-in**.
- Bug P (fairness antar-lengan di kondisi ekstrem) tetap diterima sebagai keterbatasan terdokumentasi, tidak dikejar lebih lanjut — konsisten dengan keputusan 30 Agustus.

---

## 4. Uji alur demo end-to-end

`docs/sop-demo-end-to-end.md` sudah ada dan lengkap (9 langkah + checklist H-1) — **jangan tulis SOP baru, ikuti yang ada.** Ringkasan urutan nyala + estimasi waktu:

| # | Langkah | Perintah | Estimasi | Wajib disiapkan sebelum |
|---|---|---|---|---|
| 1 | Ingest CSV CV terbaru | `.venv\Scripts\python.exe run_ingest.py` | <1 menit | CSV CV sudah final |
| 2 | Jalankan backend | `uvicorn app.main:app --host 127.0.0.1 --port 8000` (terminal terbuka) | instan | `.env` root berisi kredensial Supabase benar |
| 3 | Smoke test cache | `scenario_worker.py --once --full-cycle` | ~1-2 menit (3 kandidat SUMO) | Tabel `liveScenarioCache` sudah dibuat |
| 4 | Verifikasi `/recommendation` | `Invoke-RestMethod ... /recommendation` | instan | Langkah 3 sukses (`source=scenario-generator`) |
| 5 | Worker terus-menerus | `scenario_worker.py --full-cycle --interval 60` (**BIARKAN TERBUKA sepanjang demo**) | live | — |
| 6 | Verifikasi fallback aman | manual, opsional | 2 menit | — |
| 7 | Run SUMO penuh + simpan metrik | `run_tls_simulation.py` | beberapa menit | — |
| — | Buka frontend | `npm run dev` / build produksi | instan | **Perbaiki dulu regresi DigitalTwinPanel (bagian 3.4/6) sebelum ini dibuka ke juri** |

**Titik putus paling berisiko, sudah didokumentasikan di SOP sendiri:** kalau `scenario_worker.py --full-cycle` mati/berhenti, backend menganggap cache basi setelah **120 detik** dan **diam-diam** jatuh ke rule-based murni — tanpa error yang terlihat di layar. Kotak 7-8-9 (Scenario Generator, SUMO, Performance Analysis) lenyap dari alur tanpa disadari operator demo. **Mitigasi:** sorot badge "Diuji simulasi SUMO" di panel Rekomendasi sebagai bukti hidup, dan jangan biarkan terminal worker tertutup.

**Temuan tambahan (di luar SOP, kecil tapi nyata):** `cv/process_uploaded_video.py:102` — `BACKEND_URL` default ke `http://127.0.0.1:8001`, sedangkan **seluruh bagian lain sistem** (`cv_trigger_service.py:74`, `frontend/src/app/page.tsx:296`, `lib/supabaseData.ts:23`, SOP demo) memakai port **8000**. Ini best-effort call (kegagalannya di-`except` diam-diam, data tetap aman ke Supabase), tapi kalau `BACKEND_URL` tidak di-set eksplisit saat demo pakai jalur upload CCTV ad-hoc, notifikasi WebSocket live-update ke dashboard tidak akan terkirim — data tetap masuk tapi dashboard perlu di-refresh manual.

---

## 5. Angka-angka kunci untuk slide

| Kategori | Angka | Sumber |
|---|---|---|
| Volume per lengan | Timur 1.132, Utara 1.234, Selatan 573, Barat 1.505 crossing (~49 menit rekaman) | `cv/output/crossing_simpang.csv`, dihitung ulang untuk audit ini |
| Akurasi deteksi CV | Rata-rata **48,7%** (rentang 22,2%–96,1%, 8 sampel) | `docs/hasil-validasi-akurasi-cv.md` — tidak berubah sejak 29 Agustus |
| mAP / MOTA / IDF1 | **Tidak pernah diukur** — keputusan sadar, butuh anotasi ground truth di luar scope 16 hari | `STATUS-DAN-SISA-KERJA.md` bagian 5 |
| Scenario Generator (live run hari ini) | Baseline/Aggressive: delay 16,25s, antrean 70m, throughput 6, LOS B. **Balanced (menang)**: delay 15,68s, antrean 56m, throughput 8, LOS B | Run offline nyata, bagian 2.3 |
| Validasi PKJI (capacity/DS/LOS) | **Tidak ada** — dicoret sengaja dari scope sejak awal | Konfirmasi `grep -ri PKJI` seluruh repo, bagian 3.2 |
| LSTM PeMS04 | R² ≈0,8786 (klaim tertulis; file bukti mentah sudah dihapus dari repo 25 Agustus) | `forecasting/README.md:360` |
| LSTM TMU | MAPE speed 2,09%; vehicle_count 25,6% (**jangan pakai MAPE queue_proxy — rusak, 1.008.321.136% karena pembagian nyaris nol**) | `forecasting/README.md`, CLAUDE.md |
| Dampak forecast (20 snapshot, 1 sesi rekaman) | Delay membaik 20/20, antrean 17/20, throughput 19/20, ketiganya bersamaan 17/20 | `docs/hasil-studi-forecast-multi-snapshot.md`, diperbarui 30 Agustus |
| PPO v5 vs rule-based (3 seed × 3 metrik) | **Menang 7, seri 2, kalah 0.** Antrean −46,4% s/d −50,6%, tunggu −60,2% s/d −63,2%, throughput +2,18%/seri | `docs/hasil-evaluasi-ppo-v5.md` |
| Test backend | **92 passed, 0 failed** (dijalankan langsung untuk audit ini) | `pytest backend/tests -q` |
| Test simulation | **15 passed, 0 failed** (dijalankan langsung, perlu `SUMO_HOME`) | `pytest simulation/tests -q` |
| Build frontend | 13/13 route, 0 error TypeScript | `npm run build`, dijalankan langsung |
| Effort teknis | **247 commit** total (mulai 10 Agustus); file Python: backend 101, cv 163, simulation 66, decision_engine 90, forecasting 35; frontend 56 file; 23 dokumen markdown di `docs/` | `git log --oneline \| wc -l`, `find` per direktori |
| Data produksi tersimpan | 538 window `trafficStates`, 2.152 baris `trafficApproachStates` (100% window punya 4 lengan), 21 video CCTV, 12 job pemrosesan CV | Query langsung Supabase |

---

## 6. Risiko sisa & rencana mitigasi demo

| # | Risiko | Tingkat | Mitigasi konkret (bisa dikerjakan sebelum rekam) |
|---|---|---|---|
| 1 | **DigitalTwinPanel auto-start SUMO + polling patah-patah** — regresi baru 31 Agustus dini hari | 🔴 Kritis | Revert-nya-revert: kembalikan perilaku commit `5e4fa5e` (jangan auto-start, pakai `/stream` bukan `/frame`). Ini perbaikan yang SUDAH PERNAH ada di riwayat git — tinggal di-apply lagi, bukan dikerjakan dari nol |
| 2 | RecommendationPanel bisa nyangkut loading tanpa batas kalau rekomendasi gagal datang | 🟡 Sedang | Sama, kembalikan state eksplisit "Rekomendasi belum tersedia" dari commit `ca609cc` yang ter-revert |
| 3 | CameraFeedPanel: scrubber 1 kamera menarik semua kamera lain | 🟡 Sedang | Sama, kembalikan `persistedCameraTime` per-kamera dari `ca609cc` |
| 4 | Dropdown skenario di `/digitaltwin` nyangkut "Loading..." saat ganti skenario ketika simulasi jalan (Masalah 2, P-1e) | 🟡 Sedang — **hindari saat demo**: jangan ganti dropdown skenario sambil simulasi "Running", matikan dulu baru pilih skenario baru | Perbaikan sudah didesain lengkap di `docs/rencana-perbaikan-digital-twin-scenario.md` (~30 menit kerja), belum diimplementasi |
| 5 | Kartu "Queue Length"/"Traffic Flow" di `/digitaltwin` selalu `"-"` | 🟢 Kecil — kosmetik, tidak menghalangi demo | Kalau ditanya juri: jelaskan datanya real-time dari SUMO tapi panel belum disambungkan, arahkan ke panel Rekomendasi yang datanya lengkap |
| 6 | Worker `scenario_worker.py` mati → cache basi 120 detik → diam-diam fallback rule-based tanpa error terlihat | 🔴 Kritis kalau tidak disadari | Buka terminal worker di layar terpisah yang terlihat operator selama demo; sorot badge "Diuji simulasi SUMO" sebagai bukti hidup |
| 7 | Notifikasi live-update dashboard gagal diam-diam kalau `BACKEND_URL` default (8001) tidak cocok port backend asli (8000) saat pakai jalur upload CCTV ad-hoc | 🟢 Kecil | Set `BACKEND_URL=http://127.0.0.1:8000` eksplisit di environment sebelum demo upload video, atau hindari jalur upload ad-hoc saat demo (pakai jalur 4-kamera produksi yang tidak terpengaruh) |
| 8 | Akurasi CV 48,7% — kalau juri bandingkan langsung ke video, gap-nya kelihatan di kondisi padat | 🟡 Sudah terdokumentasi jujur | Pakai kalimat siap-jawab di `STATUS-DAN-SISA-KERJA.md` bagian 7 — sudah teruji, jangan generalisasi dari sampel terbaik |
| 9 | PPO belum aktif default — kalau juri tanya kenapa tidak dipakai padahal menang 7/9 | 🟢 Sudah ada jawaban jujur | Kalimat siap-jawab soal Bug P sudah tersedia di `STATUS-DAN-SISA-KERJA.md` bagian 7 |
| 10 | Validasi PKJI 2023 tidak ada — kalau juri tanya soal capacity/DS resmi | 🟡 Sedang | Jawab jujur: item ini sengaja dicoret dari scope 16 hari sejak awal untuk fokus ke MVP kredibel (Traffic State Builder, CV→SUMO, baseline sinyal asli); LOS yang ditampilkan tetap pakai ambang HCM 2000 |

---

## 7. Aset yang sudah tersedia untuk PPT

| Aset | Path | Catatan |
|---|---|---|
| Plot training/validation loss LSTM (gabungan) | `forecasting/outputs/lstm/plots/training_validation_loss.png` | Satu-satunya plot LSTM yang tersisa di repo |
| Plot training/validation loss LSTM (per-approach) | `forecasting/outputs/lstm/per_approach/plots/training_validation_loss.png` | — |
| ⚠️ Plot/JSON evaluasi PeMS04, TMU, Brisbane | **Tidak ada** — dihapus commit `355fabc` (25 Agustus) | Angka masih ada sebagai teks di `forecasting/README.md`, tapi tidak ada visual untuk ditempel langsung ke slide — perlu digambar ulang dari data teks kalau mau ditampilkan |
| Dokumen bukti hasil uji (siap dikutip) | `docs/hasil-validasi-akurasi-cv.md`, `docs/hasil-evaluasi-ppo-v5.md`, `docs/hasil-studi-forecast-multi-snapshot.md`, `docs/hasil-validasi-multisnapshot-multiseed.md`, `docs/hasil-kalibrasi-kandidat-agresif.md`, `docs/hasil-run-antrean-25-agustus.md` | Semuanya berisi angka mentah + metodologi, bukan cuma kesimpulan |
| Data mentah CV | `cv/output/crossing_simpang.csv` (2.152 baris) | Sumber angka volume per lengan di bagian 5 |
| Diagram arsitektur / screenshot dashboard | **Tidak ditemukan** di `docs/` (tidak ada `.png`/`.svg`/`.drawio`) maupun `frontend/public/` | **Perlu diambil manual sebelum presentasi** — build frontend sekarang hijau jadi screenshot bisa diambil langsung, tapi **selesaikan dulu perbaikan risiko #1 di bagian 6** supaya screenshot tidak menangkap panel yang auto-start tanpa diminta |
| `docs/penjelasan-progres-per-modul.md` | — | Berisi kalimat siap-pakai per modul untuk narasi laporan, sudah disiapkan tim 26 Agustus |

---

*Audit ini adalah snapshot read-only per commit `abed968`. Tidak ada perbaikan kode yang dilakukan. Untuk menindaklanjuti temuan bagian 6 #1-4, ikuti rencana yang sudah ada di `docs/rencana-perbaikan-digital-twin-scenario.md` (untuk #4) dan riwayat git commit `5e4fa5e`/`ca609cc` (untuk #1-3, tinggal re-apply perubahan yang sudah pernah benar sebelum di-revert).*

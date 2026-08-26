# Pembagian Tugas Tahap Akhir — H-5 (26–31 Agustus 2026)

Disusun dari audit progres per modul malam 25 Agustus (lihat rekap commit di `pembagian-tugas-24-agustus.md` dan desain LSTM di `rencana-lstm-forecast.md`), **diperbarui menyeluruh 26 Agustus siang** setelah scan ulang seluruh modul (CV, forecasting, backend, decision_engine, simulation, frontend) — lihat bagian 6 & 7 untuk temuan baru. Skor kesiapan MVP keseluruhan sekarang **jauh lebih tinggi dari 72%** — hampir semua blocker besar (model LSTM tidak ada, Recommendation Panel putus, rotasi lampu tidak hidup) sudah tertutup hari ini. Sisa kerjaan intinya cuma satu: **sambungkan pipa yang sudah ada satu sama lain** (lihat bagian 6), bukan bangun dari nol lagi.

**Prinsip pembagian:** tetap di jalur masing-masing yang sudah terbukti malam ini (Rahmat = backend/CV/simulasi, Yuli = LSTM, Melpi = frontend) — bukan dirombak, biar tidak ada waktu terbuang re-onboarding ke area baru.

---

## 0. Keputusan tim — SUDAH DISEPAKATI 25 Agustus malam

1. **Format model LSTM: PyTorch.** Yuli pegang penyesuaian `realtime_forecast_service.py` supaya baca `.pt` (bukan `.keras`). Training pipeline PyTorch yang sudah jalan (5 detik resample, horizon 60s→15s) tidak perlu ditulis ulang.
2. **Scenario Generator: dibangun versi RINGAN dulu, PPO jadi upaya paralel/bonus.** Bukan "terima simplifikasi" dan bukan "all-in PPO" — jalan tengah: bangun kotak 7 (Scenario Generator ringan, 3 kandidat), loop 8-9 (simulasi pendek per kandidat), dan LOS di kotak 9, dengan aturan seleksi sederhana menggantikan kotak 10 (PPO) buat SEKARANG. Detail di 1.5. PPO tetap diusahakan Rahmat secara paralel di RunPod (lihat 1.6) — kalau berhasil sebelum 31 Agustus, tinggal ditukar karena interface-nya sudah disiapkan sama bentuknya (lihat catatan arsitektur di 1.6).
3. **CV antrean (Fase 2 LSTM): jadi dikerjakan** oleh Rahmat (lihat 1.2).

---

## 1. Rahmat — Backend, CV, Integrasi Simulasi

### 1.1 [SELESAI 25 Agustus] Commit fix regresi `sumo_controller.py`
- [x] Commit fix `SUMO_BIN_DIR` yang sempat terhapus tanpa sengaja di commit LSTM Yuli — commit `26e4d48` (25 Agustus 06:35 WIB)
- [x] Jalankan `run_tls_simulation.py` sekali penuh buat mastiin simulasi beneran jalan lagi, bukan cuma lolos import — **`STATUS: SUCCESS`, exit 0, `simulations` id 7** (25 Agustus 11:28 UTC). Rantai penuh terlewati: TrafficState → Rule-Based Engine (green 60s) → Phase Mapping → TLS Controller → SUMO (300 step, 65 kendaraan) → Metrics → Supabase
- [x] **Blocker yang ketemu saat mengerjakan ini:** `backend/.venv` tidak punya `traci` sama sekali, jadi `sumo_controller.py` gagal dengan "TraCI belum tersedia di environment backend". Akar yang lebih dalam: `backend/requirements.txt` cuma mencantumkan `traci`, padahal `SUMO_BIN_DIR` mencari binary di `sys.prefix/Lib/site-packages/sumo/bin` — itu paket **`eclipse-sumo`** yang tidak terdaftar, jadi impor lolos tapi `sumo.exe` tidak ada. Dipasang `eclipse-sumo`/`traci`/`sumolib` 1.27.1 (disamakan dengan `simulation/.venv`) dan requirements sudah dilengkapi

> Catatan verifikasi: run simulasi ini sengaja dipastikan terjadi **setelah** commit `26e4d48`, karena inti butir keduanya adalah membuktikan simulasi jalan lagi PASCA-perbaikan. Run terakhir sebelumnya (`simulations` id 6, 25 Agustus 02:47 WIB) jatuh ~4 jam sebelum fix, jadi tidak sah dipakai sebagai bukti.

### 1.2 [SELESAI 25 Agustus, Rahmat] Logika antrean CV (Fase 2 LSTM)
- [x] Desain ulang definisi "antrean" buat pendekatan zona (bukan crossing lama) — `hitung_antrean()` di `cv/vehicle_counter_pingit.py`: 3 syarat (di dalam zona + geser < `ANTREAN_GERAK_RASIO_MAKS` + diam ≥ `ANTREAN_MIN_FRAME_DIAM` frame berturut-turut), titik acuan roda (y2) konsisten dengan `hitung_kendaraan_di_zona`
- [x] Implementasi logika deteksi kendaraan berhenti + kelompokkan lajur pakai PCA (bukan sumbu-x mentah, zona diagonal CCTV_1/CCTV_4 butuh itu) — sempat ada 2 bug nyata ketauan lewat review kode manual sebelum full run (pembagian lajur salah axis, key lengan `simpang_tengah` tidak cocok), sudah diperbaiki + tervalidasi
- [x] Full run 4 kamera × 49 menit (43,4 menit rekaman) dijalankan Rahmat di PC ber-GPU dengan CUDA + `--tanpa-tampilan` — **538 jendela per kamera, nol error**. Estimasi awal ~5 jam, aktualnya **2,4 jam** (run pertama dengan tampilan 3,7 jam; GPU cuma terpakai ~25%, hambatannya CPU untuk encode 4 video anotasi)
- [x] Hasilkan CSV baru dengan `queueLengthVeh`/`queueLengthMEst` yang bukan nol lagi — `snapshot_zona.csv` 10.452 baris, **71% baris punya queue > 0**. Rata-rata per lengan: selatan 6,56 / barat 2,80 / timur 0,92 / simpang_tengah 0,70 kendaraan
- [x] `ingest()` dijalankan, **terverifikasi langsung ke Supabase**: 538 window ter-ingest, rentang `16:30:10`–`17:19:15` (rentang penuh rekaman), `queueLengthVeh`/`queueLengthMEst` bervariasi dan masuk akal, bukan konstanta
- [x] CSV siap buat Yuli — sudah disalin ke `forecasting/data/` sebagai snapshot beku, dan `data_gabungan.csv` (538 baris, 4 fitur berisi semua) sudah dihasilkan
- [x] Yuli sudah tahu — commit `e44fbda` (26 Agustus, "training ulang lstm utk dpt 4 fitur") membuktikan dia sudah retrain pakai 4 fitur (`FEATURES` di `forecast_service.py`/`train.py` sekarang `vehicleCount`, `queueLengthVeh`, `queueLengthMEst`, `densityIndex`, cocok skema `TrafficState`)

> **Bukti logikanya benar secara fisik, bukan sekadar mengeluarkan angka:** rasio antre (queue ÷ kehadiran zona) = badan simpang **34%** (kendaraan melintas), lengan pendekat **43–77%** (kendaraan menunggu merah). Kalau logikanya asal, keempatnya akan mirip. Detail lengkap + keterbatasan yang diketahui ada di `docs/hasil-run-antrean-25-agustus.md`.
>
> **Belum selesai dari rantai ini (bukan bagian 1.2, tapi jangan hilang):** Yuli masih perlu instal `scikit-learn` dan retrain 4 fitur. Dan ada temuan yang memengaruhi kualitas model — **24% deret latih tercemar lompatan waktu palsu** karena rekaman punya 15 lubang dan `create_sequences()` tidak sadar timestamp. Lihat bagian 5.1 di `docs/hasil-run-antrean-25-agustus.md`.

### 1.3 [SELESAI 25 Agustus] Satukan metrik simulasi
- [x] `run_simulation.py` sudah punya `averageWaitingTimeSeconds`, throughput per-approach — tapi terpisah dari `run_tls_simulation.py` yang dipakai live
- [x] Pindahkan/sambungkan logika metrik itu ke `run_tls_simulation.py`, atau minimal ke `SimulationResultWriter`, biar hasil simulasi live juga punya delay/queue/throughput, bukan cuma step count & posisi kendaraan — `runSimulation()` sekarang menghitung `throughputVeh`, `queueLengthVeh` (puncak kendaraan berhenti, definisi "halting" bawaan SUMO), dan `averageWaitingTimeSeconds` (pola sama dengan `run_simulation.py`), lalu `SimulationResultWriter.saveMetrics()` (method baru) menulisnya ke tabel `simulationMetrics`. **Diverifikasi lewat run sungguhan** (`simulations` id 8), dicek langsung ke database: 3 baris tersimpan (`throughputVeh=54 vehicles`, `queueLengthVeh=9 vehicles`, `averageWaitingTimeSeconds=24.6 seconds`)
- [x] **Bonus temuan sambil mengerjakan ini:** skema `simulationMetrics` di `docs/database.md` (tabel lebar dengan kolom `delaySeconds`/`queueLengthVeh`/dst + `simulationRunId`) **tidak cocok dengan skema live** (diverifikasi lewat PostgREST OpenAPI: skema aslinya pola key-value generik — `simulationId`, `metricName`, `metricValue`, `unit`). `saveMetrics()` ditulis mengikuti skema live, bukan dokumen — dicatat di docstring method itu supaya tidak ada yang menulis ulang berdasar dokumen yang keliru
- [x] **Bug tambahan yang ditemukan & diperbaiki di fungsi yang sama:** `arrivedVehicles`/`departedVehicles` di `runSimulation()` sebelumnya DITIMPA tiap step (`=`), bukan diakumulasi (`+=`) — `getArrivedNumber()`/`getDepartedNumber()` TraCI itu hitungan per-step, jadi nilai akhirnya cuma dari step terakhir, bukan total sepanjang simulasi. Kalau tidak diperbaiki, `throughputVeh` yang baru disambungkan ini hampir selalu bernilai 0

### 1.4 [SELESAI 26 Agustus — TERNYATA BUKAN P2] Bersihkan sisa kode basi
- [x] **Bukan kode basi — bug nyata di jalur produksi.** `decision_engine/run_decision.py` manggil `engine.decide(...)` yang sudah dihapus saat `rule_based_engine.py` di-refactor (`60a4701` → `673cea7`/`355fabc`, jadi `.recommend()` + field camelCase). Rantainya: `run_decision.py` → `cv/output/signal_decisions.csv` → `feed_to_supabase.py` → tabel `recommendations` → `RecommendationPanel.tsx` (lihat 3.2) — jadi ini jalur live Recommendation Panel, bukan skrip percobaan. Diperbaiki: `.decide()` → `.recommend()`, field snake_case → camelCase (`recommendedPhase`, `recommendedGreenSeconds`, `currentGreenSeconds`, `expectedDelayReductionPercent`). Ditemukan bug kedua sambil jalan: urutan `sys.path.insert` salah (backend baru ditambahkan ke path SETELAH `import rule_based_engine`, padahal modul itu butuh `app.schemas.traffic` saat di-import) — sudah dibalik urutannya. **Diverifikasi jalan penuh**: 538 baris tersimpan ke `signal_decisions.csv`
  > **Update 26 Agustus — diputuskan, bukan ditambal di sini:** hasil run sempat menunjukkan `queue=0` di semua baris preview karena `baca_zona_csv()` tidak membaca kolom `queue_length_veh`/`queue_length_m_est` dari `percobaan_logic_simpang.csv`. Daripada tempel kolom + ganti sumber CSV, diputuskan `run_decision.py`/`feed_to_supabase.py`/tabel `recommendations` ditinggalkan sebagai jalur legacy — Recommendation Panel dipindah baca `POST /recommendation` yang sudah baca antrean asli live dari Supabase. Detail di 3.2. `run_decision.py` tetap dibiarkan tidak-crash (fix `.decide()` di atas) buat jaga-jaga kalau masih dipakai buat sesuatu yang lain, tapi bukan lagi jalur kritis demo.
- [x] `backend/tests/test_simulation_service.py` diisi 6 smoke test (instansiasi, `status()`, `get_simulation_state()`, `stop()` tanpa SUMO jalan, `_create_adapter()` cakup 4 approach, `_get_config_file()` nunjuk ke `simpang4_pingit.sumocfg`) — semua PASS, tidak butuh SUMO/TraCI beneran jalan

### 1.5 [SELESAI 26 Agustus] Scenario Generator ringan + LOS
Mengisi gap yang ketauan pas cocokkan kode ke diagram arsitektur asli (`data-contract.md` / proposal). Bukan Scenario Generator penuh — versi yang realistis buat 6 hari:
- [x] **Generator kandidat (kotak 7):** `simulation/scenario_generator.py::generate_candidate_plans()` — 3 varian durasi hijau per keputusan, approach sama dari `RuleBasedEngine` — (a) apa adanya, (b) +20% ke lengan tersibuk (dijepit ke `MAX_GREEN_SECONDS`), (c) ditarik ke arah minimum (lebih merata)
- [x] **Loop simulasi pendek (kotak 8):** `simulate_candidate()` — tiap kandidat jalan lewat `runSimulation()` yang sudah ada di `run_tls_simulation.py` (di-refactor supaya `step_limit` jadi parameter, bukan konstanta modul) — TIDAK diduplikasi. `SHORT_SIM_STEPS=90` (di tengah rentang 60-120 detik yang diminta)
- [x] **Satukan Performance Analysis (kotak 9):** delay/queue/throughput dihitung ULANG per kandidat lewat `simulate_candidate()`, bukan cuma 1x jalan
- [x] **Tambah LOS (kotak 9):** `calculate_los()` — standar HCM 2000 simpang bersinyal (A ≤10s ... F >80s)
- [x] **Aturan seleksi (ganti kotak 10):** `select_best_scenario()` — normalisasi delay+queue ke kandidat terburuk di batch, skor gabungan 50/50, pilih minimum. Deterministik (dites 2x hasil sama)
- [x] **Interface swappable buat PPO:** `ScenarioEngine.recommend(state, currentGreenSeconds, currentPhase) -> Recommendation` — bentuk PERSIS `RuleBasedEngine.recommend()`. `run_tls_simulation.py::createDecision()` cukup ganti `RuleBasedEngine()` → `ScenarioEngine(...)`, sisa alur (apply TLS, run 300 detik, simpan ke Supabase) tidak berubah sama sekali
  > **Catatan scope:** cuma disambungkan ke `run_tls_simulation.py` (jalur batch/simulasi), **BUKAN** ke `recommendation_service.py` (endpoint live `/recommendation` yang dipanggil dashboard tiap 5 detik) — menjalankan 3 simulasi SUMO per HTTP request akan jauh terlalu berat buat endpoint live. `RuleBasedEngine` tetap dipakai `recommendation_service.py` apa adanya.
- [x] **Diverifikasi end-to-end sungguhan** (bukan cuma unit test): `python run_tls_simulation.py` — `STATUS: SUCCESS`, `simulations` id 9. 8 unit test murni (`backend/tests/test_scenario_generator.py`, tanpa SUMO) semua lolos. Contoh output nyata satu run: baseline & aggressive kebetulan sama (baseline sudah di `MAX_GREEN_SECONDS`, +20% otomatis kejepit balik), `balanced` (38s) menang karena queue jauh lebih pendek (35m vs 42m) walau delay sedikit lebih tinggi (14.05s vs 13.58s) — `expectedDelayReductionPercent` jujur dilaporkan 0.0 (bukan diklaim turun), karena raw delay memang tidak turun, yang menang itu skor gabungan
- [ ] **Angka +20% belum ada landasan teknis** — cuma ilustratif dari dokumen ini sendiri, bukan hasil kalibrasi/formula lalu lintas (mis. Webster's formula) buat Simpang Pingit. Dipertahankan atas persetujuan sadar (26 Agustus) sebagai skenario pembanding demo, BUKAN hasil optimasi — tulis jujur begini di laporan teknis, jangan diklaim terkalibrasi

### 1.6 [P2 — bonus paralel, non-blocking] PPO di RunPod
Diusahakan Rahmat di luar jalur utama, TIDAK boleh mengganggu 1.1-1.5. Kalau sampai 31 Agustus belum berhasil, sistem tetap jalan penuh pakai 1.5 — bukan kegagalan, itu memang rencananya dari awal.
- [ ] Time-box: kasih diri sendiri maksimal ~2 hari buat lihat tanda-tanda belajar (reward naik, bukan datar/acak). Kalau di hari ke-2 belum ada sinyal positif, stop, jangan tunggu sampai mepet tenggat
- [ ] Cek dulu spesifikasi RunPod yang dipakai: berapa vCPU, bukan cuma GPU-nya — SUMO jalan di CPU, GPU cuma bantu di bagian neural network PPO-nya, bukan simulasinya
- [ ] Kalau berhasil: `PPOEngine` harus punya method `.recommend(state, currentGreenSeconds, currentPhase)` persis sama bentuknya dengan `RuleBasedEngine`/hasil 1.5, biar tinggal ditukar tanpa ubah kode lain

### 1.7 [SELESAI 26 Agustus] Rekomendasi 4-lengan + siklus lampu yang benar-benar hidup
Muncul dari koreksi arah setelah 1.5: yang dimaksud user itu **bukan** "pilih 1 lengan pemenang" tapi rotasi tetap (barat→selatan→timur→utara→barat) dengan durasi tiap lengan dihitung adaptif, dan panel dashboard harus menunjukkan siklus itu **benar-benar berjalan** (countdown live), bukan snapshot statis.
- [x] `RuleBasedEngine.recommend_cycle()` (baru) — hitung durasi utk KE-4 lengan sekaligus, reuse `calculate_demand_score()`/`calculate_green_time()` yang sudah ada, tidak ada rumus baru
- [x] `SignalService` dirombak jadi jam "lazy tick" — satu lengan aktif, countdown wall-clock nyata, pindah otomatis begitu waktunya habis, cache satu `CyclePlan` penuh yang dipakai BARENG oleh `/signal/status` (fase aktif+berikutnya) dan `/recommendation` (panel 4 kotak) — dulu dua endpoint ini hitung sendiri-sendiri dan bisa beda angka utk lengan yang sama, sekarang satu sumber
- [x] `GET /signal/status` sekarang live (dulu selalu balik ke data demo statis "Semua Fase"/"ALL" karena tidak pernah ada yang nge-`POST` ke situ)
- [x] Frontend: `RecommendationPanel.tsx` dapat layout silang 4 lengan (meniru bentuk simpang), kotak yang lagi aktif disorot & countdown live sinkron dengan `SignalStatusPanel`; `SignalStatusPanel.tsx` dapat countdown lokal per detik + kartu "Siklus Selanjutnya"
- [x] **3 bug tersembunyi ketauan & diperbaiki sekaligus** (root cause sama semua: dua tempat hitung sendiri-sendiri, harusnya satu sumber): `activeRecommendation`/`activeSignal` di `page.tsx` masih bergantung ke `selectedIntersection` yang di-hardcode `"all"` (peninggalan desain lama "4 simpang", sudah digantikan `selectedApproach`) — dua fungsi `getAggregatedRecommendation()`/`getAggregatedSignal()` yang isinya teks hardcode "N/A"/"Semua Fase" dihapus total
- [x] Video CCTV (`CameraFeedPanel.tsx`) ditambah `autoPlay`/`loop` sesuai permintaan — sebelumnya harus diklik manual dan tidak mengulang begitu habis
- [x] Diverifikasi lewat browser sungguhan berkali-kali (bukan cuma TestClient) sampai semua panel sinkron — 14 test baru (`test_rule_based_engine_cycle.py`, `test_signal_service.py`)
- [ ] **Belum:** menerapkan siklus 4-lengan ini ke SUMO live (`run_tls_simulation.py`/`sumo_controller.py`) — itu butuh `traci.trafficlight.setProgramLogic()` (program TLS custom 4 fase), beda API dari `setPhase()`/`setPhaseDuration()` yang dipakai sekarang. Dashboard sudah menunjukkan rotasi yang benar, tapi simulasi SUMO belum benar-benar menjalankan rotasi yang sama

---

## 2. Yuli — LSTM (dedicated, per kesepakatan 25 Agustus)

### 2.1 [P0 — keputusan dulu, baru kerja] Selesaikan mismatch format model
Pilih salah satu, diskusikan dengan Rahmat karena dia yang pegang `realtime_forecast_service.py`:
- **Opsi A:** Ubah `realtime_forecast_service.py` buat load PyTorch (`torch.load`) alih-alih Keras — kerjaan backend, tapi model training Yuli tidak perlu diubah
- **Opsi B:** Ubah `train.py` balik ke TensorFlow/Keras biar cocok sama serving yang sudah ada — kerjaan Yuli doang, tidak perlu sentuh backend

Rekomendasi: **Opsi A** — script training PyTorch Yuli sudah jalan & teruji (5 detik resample, horizon 60s→15s sudah cocok rencana sesi lampu), sayang kalau ditulis ulang. Lebih murah ubah satu service backend daripada tulis ulang training pipeline yang sudah benar.

### 2.2 [SELESAI 26 Agustus pagi] Selesaikan training & commit hasil
- [x] ~~Latih pakai 2 fitur asli dulu~~ — **dilewati**, Yuli langsung latih 4 fitur (lihat 2.3). Tidak masalah, cuma dicatat biar tidak dikira lupa
- [x] **Blocker lama sudah tertutup** — commit `5d2e594` "commit model" (26 Agustus 06:51 WIB, ~1 jam setelah audit sebelumnya) memakai `git add -f` (`.gitignore` diubah 1 baris) dan benar-benar membawa `traffic_lstm.pt` (221.653 bytes), `scaler.json`, `metadata.json`, plus `predictions.csv`/`training_history.json`/plot loss. **Diverifikasi ulang siang ini**, filenya ada di disk & ke-track git, `modelExists`/`scalerExists`/`metadataExists` semua `true` di `/api/forecast/health`
- [ ] Update `forecasting/README.md` bagian status — **masih belum dikerjakan**. README saat ini masih mendeskripsikan desain lama 4 dataset terpisah (`scripts/tmu/`, `scripts/pems04/`, `scripts/brisbane/`, `scripts/yolo/`), tidak cocok dengan struktur asli sekarang (`forecasting/scripts/lstm/` satu pipeline gabungan). P2 — dokumentasi saja, tidak blocking

### 2.3 [SELESAI 26 Agustus siang, dengan 1 bug ketauan+diperbaiki] Retrain 4 fitur
- [x] Model sudah beneran jalan — diverifikasi lewat prediksi sungguhan (`POST /api/forecast` pakai 12 baris asli dari `data_gabungan.csv`), hasilnya prediksi 12 langkah ke depan (60 detik) yang masuk akal, bukan cuma health check kosong
- [x] **Bug ditemukan & diperbaiki saat verifikasi:** `backend/app/services/forecast_service.py:26` masih hardcode `OUTPUT_TIMESTEPS = 3` (model versi lama, horizon 15 detik) — model hasil retrain terbaru (`metadata.json::outputSteps`) sebenarnya 12 (horizon 60 detik). Mismatch ini bikin `load_state_dict()` gagal total dengan `size mismatch for fc.weight: [48,64] vs [12,64]`, jadi `POST /api/forecast` selalu 500 walau file model-nya sudah ada. Diubah jadi `OUTPUT_TIMESTEPS = 12`, semua tempat lain (docstring, `forecastHorizonSeconds`, dst) otomatis ikut karena semua turunan dari konstanta ini, tidak ada hardcode ganda
- [x] **Temuan tambahan (bukan blocker, tapi catat):** `torch` sekarang ternyata SUDAH terinstal di `backend/.venv` (`torch-2.13.0+cpu`) — tapi **tidak tercantum** di `backend/requirements.txt`. Kemungkinan diinstal manual di suatu titik. Perlu ditambahkan ke `requirements.txt` supaya environment baru manapun (termasuk demo di laptop lain) bisa `pip install -r requirements.txt` dan langsung dapat forecast jalan, bukan gagal diam-diam
- [x] **Kode mati ketauan sekalian:** `backend/app/models/lstm_forecast.py` (`LSTMForecaster`) + `backend/tests/test_lstm_forecaster.py` itu modul LAIN dari desain lama (nunjuk ke `forecasting/outputs/yolo/metadata.json` yang tidak pernah ada dan tidak akan pernah ada — arsitektur YOLO-per-dataset sudah ditinggalkan). Test ini SELALU gagal di `pytest -q` (FileNotFoundError) dan kelihatan seperti "LSTM masih rusak" padahal LSTM yang aktif (`forecast_service.py`) sudah jalan. Aman dihapus, tapi belum dihapus — tanya dulu ke tim sebelum dihapus permanen
- [ ] Update tabel status fitur di `rencana-lstm-forecast.md` bagian 2 — **masih belum dikerjakan**, tabel di bagian 2 dokumen itu masih menulis `queueLengthVeh`/`queueLengthMEst` sebagai "⚠️ SELALU 0", padahal data asli sudah ada sejak 25 Agustus DAN model sudah dilatih dengan data itu

### 2.4 [DINAIKKAN KE P0 — fokus utama 26 Agustus sore/malam] Sambungkan forecast ke Decision Engine
**Perubahan prioritas 26 Agustus:** item ini sebelumnya P2 "kalau sempat" — sekarang jadi fokus utama, karena dua prasyaratnya (model LSTM jalan di 2.2/2.3, siklus lampu live di 1.7) baru saja selesai hari ini, dan tim ingin pipa penuhnya benar-benar tersambung, bukan cuma tiap potongan jalan sendiri-sendiri. Detail desain & pembagian kerja lengkap ada di **bagian 6** di bawah — ringkasannya di sini:
- [ ] Belum ada kode yang menyambungkan hasil forecast ke `RuleBasedEngine.recommend()`/`recommend_cycle()` — desain pola opsional (`forecast: ForecastResult | None`) sudah dibahas di `rencana-lstm-forecast.md` bagian 8, tinggal diimplementasikan
- [ ] Keputusan desain yang perlu diambil dulu (lihat bagian 6.2): forecast dipakai di jalur SIKLUS LAMPU LIVE (`SignalService`, tiap transisi fase) atau di jalur BATCH SIMULASI (`ScenarioEngine`), atau dua-duanya — trade-off kecepatan vs risiko forecast yang belum tervalidasi akurasinya
- [ ] Kalau tidak sempat sebelum 31 Agustus: dokumentasikan sebagai keterbatasan yang jujur, jangan diklaim terintegrasi kalau belum — **lihat catatan validitas di bagian 6.3**, forecast belum tentu memperbaiki hasil kalau akurasinya belum terbukti buat simpang ini spesifik

---

## 3. Melpi — Frontend

### 3.1 [P0 — cepat, blocker deploy] Perbaiki build produksi yang gagal
- [x] `npm run build` gagal di `/settings` — error `useSearchParams() should be wrapped in a suspense boundary`
- [x] Fix: bungkus komponen yang pakai `useSearchParams()` dengan `<Suspense>` boundary (pola standar Next.js App Router) — **dikerjakan Rahmat, bukan Melpi**, commit `e3f7d61` (25 Agustus)
- [x] Verifikasi `npm run build` sukses penuh setelah fix, bukan cuma halaman itu doang — pesan commit mencatat "13/13 route ter-generate". Rahmat juga sekalian benerin crash `DigitalTwinPanel` & `ForecastChart` yang juga bikin build gagal (commit `4bc7a6c`)

### 3.2 [SELESAI 26 Agustus] Keputusan sumber data Recommendation Panel
- [x] **Diputuskan: pindah ke `POST /recommendation` (jalur backend API), bukan tabel Supabase langsung.** Dikerjakan langsung sambil investigasi item 1.4 (lihat catatan di 1.4 soal `run_decision.py`) — ternyata dua-duanya nyambung: `run_decision.py` yang dipatch di 1.4 cuma memberi makan tabel `recommendations` yang sekarang ditinggalkan.
- [x] Alasan: tabel `recommendations` diisi lewat `run_decision.py` + `feed_to_supabase.py`, skrip batch offline yang harus dijalankan manual dan gampang basi (baru saja ketauan rusak total karena bug `.decide()`, lihat 1.4). `POST /recommendation` (`RecommendationService`) baca `TrafficState` **live** dari Supabase — sumber yang sama yang terus diisi ingest CV — lalu jalankan `RuleBasedEngine.recommend()` saat itu juga. Dites langsung: hasil sudah membawa antrean asli (`"queue=5 kendaraan"`, bukan 0) tanpa perlu proses batch terpisah.
- [x] Implementasi: `frontend/src/lib/supabaseData.ts::fetchRecommendation()` diganti dari query Supabase langsung jadi `fetch(...)` ke `${API_BASE_URL}/recommendation` (pola yang sama dengan `useTrafficSimulaton.ts`/`digitaltwinview.tsx`, CORS sudah mengizinkan `localhost:3000`). `npm run build` sukses 13/13 route.
- [x] **Diverifikasi penuh lewat browser sungguhan** (26 Agustus) — 3 bug ketauan & diperbaiki di `backend/app/main.py` + `backend/app/services/recommendation_service.py`:
  1. **Private Network Access**: Chrome menolak total preflight OPTIONS ke `127.0.0.1` dari `localhost:3000` karena `CORSMiddleware` belum diset `allow_private_network=True` — semua request browser gagal ("blocked by CORS policy") walau server sendiri sudah benar. Ditambahkan `allow_private_network=True`.
  2. **Crash 500 untuk intersection mock**: 3 dari 4 intersection di frontend (`ALL_INTERSECTIONS`) cuma data dummy demo, tidak ada di database — `RecommendationService.get_recommendation()` sebelumnya tidak menangkap `TrafficServiceError` untuk `intersectionId` yang tidak dikenal, jadi 500.
  3. **`httpx.RemoteProtocolError: Server disconnected` sesekali dari koneksi Supabase** — cukup sering terjadi (45x dalam sesi tes singkat), dan karena bug lama FastAPI/Starlette (`ServerErrorMiddleware` di luar `CORSMiddleware`, jadi response 500 kehilangan header CORS), tiap kali ini kejadian browser melaporkannya sebagai CORS error yang membingungkan, bukan error 500 biasa. `get_recommendation()` sekarang menangkap semua exception (bukan cuma `TrafficServiceError`) dan jatuh ke fallback yang sama seperti "belum ada data".
  - Hasil setelah fix: 231 request `/recommendation` sukses, 0 gagal, meski `RemoteProtocolError` masih terjadi 45x di baliknya (sekarang teredam, tidak bocor ke browser).

### 3.3 [P2] Rapikan detail kecil
- [ ] Digital Twin: state awal (`signalStatuses`) hardcode 32s/18s sebelum data live masuk — kasih indikator visual "memuat..." biar tidak kelihatan seperti data asli
- [x] ~~`CameraFeedPanel.tsx` masih ada `console.log` development di `onTimeUpdate`~~ — dicek 26 Agustus, sudah tidak ada `console.log` di file itu sama sekali. Sudah beres (mungkin lewat commit lain), tidak perlu dikerjakan lagi
- [ ] **Baru (26 Agustus):** kartu "memuat..." di 3.3 baris pertama sekarang lebih relevan lagi — `SignalStatusPanel`/`RecommendationPanel` baru dibangun (1.7) untuk kondisi live, tapi belum ada state loading eksplisit pas pertama kali dashboard dibuka sebelum poll pertama selesai (sekilas bisa kelihatan seperti data lama sebelum data live masuk)

---

## 4. Yang TIDAK perlu dikerjakan (biar tidak buang waktu H-6)

- **Scenario Generator versi PENUH** (bukan yang ringan di 1.5) — jangan generate skenario dalam jumlah besar/kompleks, cukup 3 kandidat sesuai 1.5
- **Halaman History** — sudah diputuskan di luar scope demo, data mock-nya boleh dibiarkan
- **Auth (login/register/account)** kecuali bagian yang mematahkan build (`/settings`, lihat 3.1) — sisanya sudah diputuskan tidak prioritas
- **PPO di luar jam yang dialokasikan Rahmat sendiri (1.6)** — Yuli dan Melpi TIDAK perlu ikut bantu PPO, fokus di jalur masing-masing. Kalau Rahmat kehabisan waktu di 1.6, itu sudah di-time-box, bukan alasan geser prioritas 1.1-1.5

---

## 5. Checklist sinkronisasi tim (isi pas rapat, bukan solo)

- [x] Format model LSTM: **PyTorch** disepakati (item 2.1)
- [x] Scenario Generator: **versi ringan dibangun (1.5), PPO paralel non-blocking (1.6)** disepakati
- [ ] Sudah sepakat siapa yang dokumentasikan keputusan Recommendation Panel (item 3.2) ke laporan teknis?
- [x] Rahmat sudah commit fix `sumo_controller.py` (item 1.1)? — **sudah** (`26e4d48`), dan simulasinya sudah diverifikasi jalan pasca-fix (`simulations` id 7)
- [ ] Rahmat sudah time-box PPO (item 1.6) — jangan biarkan tanpa batas waktu jelas
- [x] **Baru:** model LSTM Yuli sudah di-commit (`5d2e594`) dan sudah diverifikasi jalan (2.2/2.3) — sudah sepakat forecast → decision engine (2.4/bagian 6) jadi fokus 26 Agustus sore, menggantikan prioritas P2 lama
- [ ] **Baru:** siapa yang jalankan `run_ingest.py` (CV → Supabase) secara rutin sebelum demo — sekarang manual, tidak ada scheduler (lihat bagian 7.2). Perlu SOP jelas siapa & kapan, supaya data di dashboard demo tidak basi
- [ ] **Baru:** `backend/app/models/lstm_forecast.py` + `backend/tests/test_lstm_forecaster.py` (kode mati, lihat 2.3) — sudah sepakat boleh dihapus?

---

## 6. Integrasi Pipa Penuh — fokus 26 Agustus sore/malam

Ditulis setelah scan menyeluruh siang ini. Ini menjawab arahan: TrafficState live → LSTM → Scenario Generator → Traffic Simulation → Performance Analysis → Decision Engine (rule-based dulu) → Recommendation.

### 6.1 Peta status tiap kotak (per 26 Agustus siang)

| Kotak (diagram arsitektur) | Status | Kode |
|---|---|---|
| 1-3. CV → Traffic State | **Hidup, tapi bukan realtime streaming** — proses video REKAMAN (43 menit), hasilnya di-ingest MANUAL ke Supabase | `cv/vehicle_counter_pingit.py` → `run_ingest.py` (lihat 7.1-7.2) |
| 4-5. Virtual Intersection / Realtime Traffic State | **Hidup** — `TrafficStateBuilder` baca Supabase, dipakai `/recommendation` & `/signal/status` tiap poll | `backend/app/pipeline/traffic_state_builder.py` |
| 6. Traffic Forecast (LSTM) | **Model jalan** (diverifikasi 26 Agustus siang, lihat 2.2/2.3) — TAPI **berdiri sendiri**, tidak dipanggil siapa pun untuk pengambilan keputusan | `backend/app/services/forecast_service.py`, endpoint `POST /api/forecast` |
| 7-9. Scenario Generator + Simulasi + Performance Analysis (LOS) | **Jalan, terbukti (1.5)** — TAPI cuma di jalur batch manual (`run_tls_simulation.py`), tidak nempel ke dashboard live sama sekali | `simulation/scenario_generator.py` |
| 10. Decision Engine | **Hidup** — `RuleBasedEngine` (live, `/recommendation` & `/signal/status`) DAN `ScenarioEngine` (batch). PPO belum ada (1.6) | `decision_engine/rule_based_engine.py` |
| 11. Signal Timing Recommendation | **Hidup & live** — siklus 4 lengan beneran berputar (1.7) | `SignalService`, `RecommendationService` |
| 12. Dashboard | **Hidup**, sinkron dengan 11 | `frontend/src/components/RecommendationPanel.tsx`, `SignalStatusPanel.tsx` |

**Kesimpulan:** rantai **1→5→10→11→12 sudah nyambung penuh dan live**. Yang **belum nyambung**: kotak 6 (LSTM) ke kotak 10 (Decision Engine), dan kotak 7-9 (Scenario Generator+LOS) ke kotak 11-12 (cuma nempel ke jalur batch `run_tls_simulation.py`, bukan dashboard).

### 6.2 Rencana sambungkan LSTM → Decision Engine (item 2.4, P0 baru)

Dua pertanyaan desain yang perlu diputuskan tim dulu (bukan cuma kerjaan solo):

**A. Forecast dipakai di jalur mana?**
- **Opsi 1 — Siklus lampu live (`SignalService`):** tiap kali fase pindah, sebelum panggil `recommend_cycle()` pakai `TrafficState` SEKARANG, tambahkan langkah panggil `POST /api/forecast` dulu (butuh 12 baris histori terakhir), pakai HASIL PREDIKSI sebagai input `recommend_cycle()` alih-alih data sekarang. Lebih "sesuai visi" (antisipatif), tapi tiap transisi fase jadi butuh 1 panggilan forecast tambahan (masih cepat, LSTM bukan simulasi berat)
- **Opsi 2 — Cuma di Scenario Generator (batch):** `ScenarioEngine` pakai forecast buat memilih baseline sebelum generate 3 kandidat, tapi siklus live (`SignalService`) tetap reaktif seperti sekarang. Risiko lebih rendah (tidak menyentuh jalur live yang sudah stabil), tapi manfaatnya kurang kelihatan di demo dashboard
- **Rekomendasi:** mulai dari Opsi 2 dulu (risiko rendah, `ScenarioEngine` sudah punya slot alami buat ini di `generate_candidate_plans()`), baru kalau waktu masih ada pindah ke Opsi 1

**B. Bagaimana kalau forecast gagal/tidak tersedia?**
Sama seperti pola fallback yang sudah dipakai di seluruh proyek ini (`RecommendationService`, `SignalService`) — forecast yang gagal HARUS jatuh ke data `TrafficState` sekarang, bukan bikin request gagal. Pola `forecast: ForecastResult | None` yang sudah didesain di `rencana-lstm-forecast.md` bagian 8 sudah benar arahnya, tinggal diimplementasikan dengan try/except yang sama gayanya dengan kode lain di proyek ini.

### 6.3 Peringatan jujur — forecast belum tentu bikin "lebih valid"

Dicatat di sini supaya tidak lupa pas nulis laporan teknis (sudah dibahas user & Claude siang ini): mengantisipasi kondisi ke depan itu SECARA KONSEP lebih canggih dari reaktif — tapi cuma valid kalau forecast-nya akurat, dan itu **belum terbukti** untuk Simpang Pingit spesifik:
- Data training cuma ~538 baris (~45 menit) — kecil untuk time-series
- `queueLengthVeh`/`queueLengthMEst` (2 dari 4 fitur) baru punya data antrean ASLI sejak 25 Agustus (item 1.2) — sebelumnya selalu 0, jadi model belajar dari data yang sangat baru/sedikit khusus utk fitur ini
- Kalau forecast-nya meleset, rekomendasi bisa JADI LEBIH BURUK daripada pakai data real-time apa adanya

**Jangan klaim "forecast bikin sistem lebih akurat"** tanpa validasi terpisah (bandingkan hasil rekomendasi pakai forecast vs tanpa forecast, pakai metrik yang sama seperti 1.5/LOS). Kalau tidak sempat validasi sebelum 31 Agustus, tulis di laporan sebagai "diintegrasikan secara arsitektur, validasi akurasi prediksi untuk keputusan sinyal adalah kerja lanjutan" — jujur, bukan diklaim selesai.

### 6.4 Pembagian kerja bagian ini

| Siapa | Kerjaan |
|---|---|
| Rahmat | Implementasi 6.2 (pilih Opsi 1/2, sambungkan kode), rapikan `backend/requirements.txt` (tambah `torch`, lihat 2.3), putuskan nasib `lstm_forecast.py` mati (2.3) |
| Yuli | Update dokumentasi (`forecasting/README.md`, tabel fitur `rencana-lstm-forecast.md` — 2.2/2.3), kalau ada waktu: evaluasi akurasi forecast di data baru (buat bahan keputusan 6.3) |
| Melpi | Beres-beres UI kecil yang sudah didelegasikan (3.3), TIDAK perlu ikut bagian 6 ini — tetap di jalur frontend |

---

## 7. Temuan audit CV (26 Agustus) — belum pernah tercatat di dokumen manapun

### 7.1 "Realtime" itu maksudnya apa, sebenarnya

Penting buat jujur ke juri: CV **TIDAK** memproses siaran langsung (RTSP/live feed). `vehicle_counter_pingit.py` membaca file `.mp4` REKAMAN 43 menit yang sudah ada di `cv/videos/`. Tidak ditemukan kode RTSP/streaming di mana pun di repo. Jadi "integrasi realtime Traffic State" yang benar sekarang artinya: **CV diproses offline dari rekaman → hasil di-ingest ke Supabase → backend baca Supabase "seolah-olah" live** (lewat `videoTimeRef` yang mensimulasikan posisi video, lihat `fetchTrafficState()` di `supabaseData.ts`). Bukan pipeline live kamera sungguhan. Ini bukan masalah buat demo (memang begitu desainnya dari awal, disepakati di roadmap), tapi jangan sampai kepeleset bilang "realtime CCTV" ke juri kalau ditanya detail.

### 7.2 Ingest CV → Supabase itu manual, tidak ada scheduler

`run_ingest.py` (root repo) harus dijalankan manual oleh seseorang setiap kali ada hasil CV baru. Tidak ada cron/APScheduler di seluruh repo. Kalau video/CSV baru diproses tapi lupa jalankan `run_ingest.py`, dashboard akan menampilkan data lama tanpa ada tanda peringatan. **Perlu SOP jelas** — siapa yang jalankan, kapan, terutama H-1 sebelum demo.

### 7.3 Kabar baik: identitas koridor `east` sudah tertutup

`docs/roadmap.md` (per 17 Agustus) mencatat ini sebagai risiko besar yang menggantung ("kalau ternyata Magelang, east dan north menghitung lengan yang sama dua kali"). **Sudah diverifikasi dan ditutup** lewat commit `700140c` (24 Agustus) — `simulation/verify_corridor_bearing.py` mengroskek bearing OSM vs klasifikasi CV secara independen: **Jl. Diponegoro = timur, Jl. Magelang = utara**, cocok dengan kode. `docs/roadmap.md` sendiri belum diupdate untuk menghapus tanda risiko ini — perlu dirapikan supaya tidak membingungkan pembaca dokumen nanti (roadmap.md itu sendiri sudah basi sejak 17 Agustus, banyak checklist di situ yang sudah selesai tapi belum dicentang).

### 7.4 Belum jelas: kalibrasi `north`

`roadmap.md` (17 Agustus) mencatat counting line `north` masih pakai nilai default, belum dikalibrasi, padahal menyumbang volume tertinggi. Tidak ditemukan commit lanjutan yang secara eksplisit menyebut kalibrasi ulang `north`. **Tapi** pendekatan CV sendiri sudah berubah sejak saat itu (dari counting-line murni ke pendekatan zona + PCA lane-grouping di `vehicle_counter_pingit.py`, item 1.2) — jadi belum tentu keterangan lama ini masih relevan apa adanya. **Perlu dicek ulang oleh yang pegang CV**, jangan diasumsikan salah satu (masih bermasalah / sudah otomatis terselesaikan oleh pendekatan baru).

### 7.5 Tidak ada validasi akurasi deteksi

Tidak ditemukan ground truth, precision/recall, atau mAP yang pernah dihitung untuk deteksi/tracking YOLO+ByteTrack di repo manapun. Validasi yang ada sejauh ini murni sanity-check aritmetika (rasio antre wajar secara fisik, lihat 1.2) — bukan pengukuran akurasi formal terhadap data berlabel. Kalau juri tanya "seberapa akurat deteksinya", jawaban jujurnya sekarang adalah "belum diukur formal, validasi tidak langsung lewat konsistensi fisik data" — bukan angka mAP/precision tertentu. `docs/roadmap.md` sempat merencanakan anotasi CVAT + mAP/MOTA/IDF1 (Fase 3) tapi ini eksplisit ada di daftar "boleh dikorbankan" kalau waktu mepet (lihat rencana kontingensi di roadmap.md) — jadi ini keputusan yang SUDAH diambil sadar, bukan kelupaan.

### 7.6 `hitung_antrean()` — keterbatasan yang didokumentasikan sendiri di kode (bukan bug tersembunyi)

Dicatat langsung sebagai docstring di `vehicle_counter_pingit.py` (25 Agustus): (1) ID-switch ByteTrack saat antrean padat bisa menurunkan `queue_length_veh` secara sistematis justru saat kondisi paling macet — kebalikan dari yang diinginkan; (2) state tracking antrean tidak dibersihkan kalau track_id hilang total (leak kecil, tidak masalah untuk rekaman 49 menit, tapi perlu dibersihkan untuk rekaman berjam-jam). Kedua-duanya trade-off sadar, bukan sesuatu yang "belum sempat" — aman dibawakan ke laporan sebagai keterbatasan yang diketahui.

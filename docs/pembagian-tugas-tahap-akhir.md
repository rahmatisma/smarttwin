# Pembagian Tugas Tahap Akhir — H-5 (26–31 Agustus 2026)

Disusun dari audit progres per modul malam 25 Agustus (lihat rekap commit di `pembagian-tugas-24-agustus.md` dan desain LSTM di `rencana-lstm-forecast.md`), **diperbarui menyeluruh 26 Agustus siang** setelah scan ulang seluruh modul (CV, forecasting, backend, decision_engine, simulation, frontend) — lihat bagian 6 & 7 untuk temuan baru. Skor kesiapan MVP keseluruhan sekarang **jauh lebih tinggi dari 72%** — hampir semua blocker besar (model LSTM tidak ada, Recommendation Panel putus, rotasi lampu tidak hidup) sudah tertutup hari ini. Sisa kerjaan intinya cuma satu: **sambungkan pipa yang sudah ada satu sama lain** (lihat bagian 6), bukan bangun dari nol lagi.

**Update 26 Agustus malam:** Yuli menutup item 2.4 sendiri (commit `d5ec395` "train per approach" + `3c6ee4c` "integrasikan forecast LSTM per-approach ke decision engine dan SUMO") — satu-satunya kotak yang masih "berdiri sendiri" di bagian 6.1 (LSTM → Decision Engine) sekarang tersambung, di jalur live MAUPUN batch sekaligus (lihat 2.4 & 6.1 versi baru). Diverifikasi ulang oleh Rahmat 26 Agustus malam: `pytest -q` di `backend/` 52 passed (naik dari 46), test forecast client di `simulation/` 8 passed (pakai `backend/.venv`, lihat catatan lingkungan di 2.4).

**Prinsip pembagian:** tetap di jalur masing-masing yang sudah terbukti malam ini (Rahmat = backend/CV/simulasi, Yuli = LSTM, Melpi = frontend) — bukan dirombak, biar tidak ada waktu terbuang re-onboarding ke area baru.

**Update 27 Agustus:** satu pengecualian — item 1.5 (Scenario Generator + Traffic Simulator + Performance Analysis) pindah dari solo Rahmat ke tim, karena Rahmat tidak bisa lanjut pegang bagian itu. Lihat catatan di 1.5 dan dokumen serah terima `docs/rencana-scenario-generator.md`.

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

### 1.5 [SELESAI 26 Agustus, KEPEMILIKAN PINDAH 27 Agustus] Scenario Generator ringan + LOS
Mengisi gap yang ketauan pas cocokkan kode ke diagram arsitektur asli (`data-contract.md` / proposal). Bukan Scenario Generator penuh — versi yang realistis buat 6 hari:

> **Update 27 Agustus:** versi dasar item ini SUDAH selesai & terverifikasi (checklist di bawah tetap berlaku apa adanya). Tapi Rahmat sekarang tidak bisa lanjut pegang bagian ini, jadi kepemilikan **dipindah ke tim** (bukan solo Rahmat lagi) untuk kerjaan lanjutannya (lihat 4.1-4.3). Dokumen serah terima lengkap — arsitektur, cara kerja, batasan yang sengaja ada, dan 3 opsi desain buat sambungkan ke dashboard live — ada di **`docs/rencana-scenario-generator.md`** (pola sama seperti `rencana-lstm-forecast.md` punya Yuli). Baca dokumen itu dulu sebelum mulai kerja di bagian ini, supaya tidak reverse-engineer dari kode dari nol.
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
- [ ] **Masih belum:** menerapkan siklus 4-lengan PENUH (`CyclePlan`/`recommend_cycle()`) ke SUMO live — `run_tls_simulation.py`/`ScenarioEngine` masih memanggil `RuleBasedEngine.recommend()` (satu lengan pemenang per run), bukan `recommend_cycle()`. Dashboard sudah menunjukkan rotasi 4-lengan yang benar, simulasi SUMO belum
- [x] **Update 26 Agustus malam (Yuli, commit `3c6ee4c`):** sub-masalah yang berdekatan sudah dibereskan sekalian — sebelumnya `run_tls_simulation.py` mengandalkan program TLS *actuated* bawaan net file dengan `approachToPhase` yang index-nya (0/1/2/3) tidak cocok index fase hijau program itu (yang diselingi fase kuning). Sekarang ada program eksplisit `simulation/network/tls_safe.add.xml` (`programID="safe-yellow"`, 8 fase: 4 hijau 39s + 4 kuning 4s, index hijau south=0/east=2/north=4/west=6), diaktifkan via `traci.trafficlight.setProgram(tlsId, "safe-yellow")` di `startSumo()`, dan `approachToPhase` diperbaiki cocok index barunya. Ini memperbaiki dasar sebelum "siklus penuh" di atas bisa dibangun — bukan pengganti item itu

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
- [x] Update `forecasting/README.md` bagian status — **sudah dikerjakan Yuli 26 Agustus malam** (bagian dari `d5ec395` + `3c6ee4c`, total >1500 baris diagram-ulang) — sekarang mendeskripsikan pipeline aktual yang berjalan (training vs runtime terpisah, model agregat + model per-approach, alur live DAN batch lengkap dengan nama file), bukan lagi desain lama 4 dataset terpisah

### 2.3 [SELESAI 26 Agustus siang, dengan 1 bug ketauan+diperbaiki] Retrain 4 fitur
- [x] Model sudah beneran jalan — diverifikasi lewat prediksi sungguhan (`POST /api/forecast` pakai 12 baris asli dari `data_gabungan.csv`), hasilnya prediksi 12 langkah ke depan (60 detik) yang masuk akal, bukan cuma health check kosong
- [x] **Bug ditemukan & diperbaiki saat verifikasi:** `backend/app/services/forecast_service.py:26` masih hardcode `OUTPUT_TIMESTEPS = 3` (model versi lama, horizon 15 detik) — model hasil retrain terbaru (`metadata.json::outputSteps`) sebenarnya 12 (horizon 60 detik). Mismatch ini bikin `load_state_dict()` gagal total dengan `size mismatch for fc.weight: [48,64] vs [12,64]`, jadi `POST /api/forecast` selalu 500 walau file model-nya sudah ada. Diubah jadi `OUTPUT_TIMESTEPS = 12`, semua tempat lain (docstring, `forecastHorizonSeconds`, dst) otomatis ikut karena semua turunan dari konstanta ini, tidak ada hardcode ganda
- [x] `torch==2.13.0` sudah tercantum di `backend/requirements.txt`, sehingga environment backend baru dapat memasang dependency serving LSTM secara reproducible
- [x] Kode mati `backend/app/models/lstm_forecast.py` + `backend/tests/test_lstm_forecaster.py` sudah dihapus 26 Agustus setelah dipastikan tidak diimpor kode produksi; loader aktif tetap `forecast_service.py`
- [x] Update tabel status fitur di `rencana-lstm-forecast.md` bagian 2 — **sudah dikerjakan Yuli 26 Agustus malam** (bagian dari commit `d5ec395`), status `queueLengthVeh`/`queueLengthMEst` diganti dari "⚠️ SELALU 0" jadi "✅ Data estimasi CV asli, bervariasi, sudah dipakai training"

### 2.4 [SELESAI 26 Agustus malam, dikerjakan Yuli] Sambungkan forecast ke Decision Engine
**Perubahan prioritas 26 Agustus:** item ini sebelumnya P2 "kalau sempat", dinaikkan ke P0 siang ini, dan **ditutup malam ini juga** — lebih cepat dari perkiraan. Dikerjakan Yuli sendiri lewat 2 commit (`d5ec395` "train per approach", `3c6ee4c` "integrasikan forecast LSTM per-approach ke decision engine dan SUMO"), bukan Rahmat seperti rencana pembagian kerja awal di bagian 6.4 (lihat catatan di situ) — masuk akal karena forecast tetap di domain LSTM Yuli. Diverifikasi ulang Rahmat malam ini: `pytest -q` di `backend/` 52 passed (naik dari 46 sebelum commit ini), tidak ada regresi.

- [x] **Model baru: shared LSTM per-approach** (`forecasting/scripts/lstm/per_approach/`) — beda dari model agregat lama (`forecast_service.py`), model ini satu jaringan dengan encoding one-hot approach (4 fitur traffic + 4 one-hot = 8 input), dilatih atas gabungan data ke-4 lengan sekaligus. Artefak: `forecasting/outputs/lstm/per_approach/traffic_lstm_per_approach.pt` (226KB) + `scaler.json` + `metadata.json`, di-commit dengan `git add -f` (pola sama seperti model agregat, lihat `CLAUDE.md`)
- [x] **Serving baru:** `backend/app/services/per_approach_forecast_service.py` (`PerApproachForecastService`) — ambil 12 `TrafficState` berurutan tepat berinterval 5 detik dari histori, prediksi 12 langkah (60 detik) ke depan untuk ke-4 lengan sekaligus dalam satu forward pass
- [x] **Endpoint `POST /api/forecast/approaches` diperbarui** — sekarang coba model per-approach dulu, kalau gagal (artefak belum ada / histori kurang dari 12 baris lengkap) baru fallback ke alokasi model agregat lama (`forecastSource: "aggregate-recent-share-fallback"`), field `fallbackUsed`/`fallbackReason` melaporkan jujur yang mana yang benar-benar dipakai
- [x] **Tersambung ke decision engine, dua-duanya (Opsi 1 DAN Opsi 2 di 6.2 lama, bukan cuma salah satu):**
  - `RuleBasedEngine.recommend()`/`recommend_cycle()` (`decision_engine/rule_based_engine.py`) dapat parameter opsional baru `forecast: dict | None`, `forecastWeight: float = 0.5` + method baru `apply_forecast()` — blend `TrafficState` sekarang dengan horizon forecast TERAKHIR (langkah ke-12, +60 detik) pakai bobot linear per fitur (`volume`, `queueLengthVeh`, `queueLengthMEst`, `densityIndex`, plus skala proporsional untuk breakdown per-kelas kendaraan). Tanpa forecast, perilaku identik dengan sebelumnya (parameter opsional, `source` tetap `"rule-based"`); dengan forecast, `source` jadi `"rule-based+forecast"` — gampang dibedakan di data
  - **Jalur live (Opsi 1):** `SignalService._recompute_cycle_plan()` sekarang ambil 24 `TrafficState` terakhir, panggil `PerApproachForecastService.predict_records()`, teruskan hasilnya ke `recommend_cycle(forecast=..., forecastWeight=0.3)` tiap kali fase pindah. Forecast gagal (histori kurang, model belum ada, dll) → tangkap exception, jatuh ke `forecast=None` (pola fallback yang sama dipakai di semua service lain di proyek ini) — dites eksplisit (`test_recompute_cycle_plan_falls_back_when_forecast_fails`)
  - `RecommendationService.get_recommendation()` juga dapat perlakuan sama (`limit=1` → `limit=24` biar cukup histori, forecast diteruskan ke `engine.recommend(forecast=..., forecastWeight=0.3)`)
  - **Jalur batch (Opsi 2):** `simulation/forecast_client.py` (baru) — `ForecastClient` narik histori dari `GET /api/v1/traffic/{id}` lewat backend, susun 12 record, panggil `POST /api/forecast/approaches`, validasi bentuknya (12 horizon, 4 approach tiap horizon), balikin `None` kalau gagal di titik mana pun (bukan exception mentah — biar SUMO tetap bisa jalan tanpa forecast). `run_tls_simulation.py::loadForecast()` panggil ini sebelum `createDecision()`, dikontrol lewat env var `FORECAST_ENABLED`/`FORECAST_WEIGHT` (default aktif, bobot 0.3). `ScenarioEngine.recommend()` (`simulation/scenario_generator.py`) juga dapat parameter `forecast`/`forecastWeight`, diteruskan ke `RuleBasedEngine` internalnya sebelum generate 3 kandidat — jadi baseline yang dibandingkan Scenario Generator sudah mempertimbangkan forecast, bukan cuma `TrafficState` sesaat
  - Hasil simulasi (`saveSimulationResult()`) sekarang mencatat `forecastApplied`/`forecastWeight`/`forecastFallbackUsed`/`forecastSource` ke `simulationMetrics` — bisa diaudit run mana yang benar-benar pakai forecast vs fallback
- [x] **Bobot forecast sengaja kecil (0.3), bukan 0.5:** keputusan konservatif — 70% state aktual, 30% forecast — konsisten dengan peringatan validitas yang sudah ditulis di bagian 6.3 lama (data training kecil, model belum divalidasi khusus buat simpang ini). Tidak all-in ke prediksi
- [x] **Diverifikasi (dikoreksi 26 Agustus malam, audit ulang):** 4 test baru di `backend/tests/test_forecast_decision_integration.py` (file baru — termasuk `test_forecast_can_change_rule_based_priority`, bukti forecast BENERAN bisa mengubah lengan yang direkomendasikan, dan `test_runtime_density_is_normalized_like_training_data`, bukti eksplisit `densityIndex` dari record Supabase dibagi `ZONE_CAPACITY=33` sebelum masuk model — cocok normalisasi waktu training) + 2 test baru di `test_signal_service.py` (total 6 test backend baru, cocok kenaikan 46→52 di `pytest -q`) + 8 test baru di `simulation/tests/test_forecast_client.py` — semua lolos, diverifikasi ulang langsung ke kode satu-per-satu (bukan cuma baca commit message), termasuk memastikan parameter `forecast`/`forecastWeight` benar-benar diteruskan di setiap hop (`loadForecast()` → `createDecision()` → `ScenarioEngine.recommend()` → `RuleBasedEngine.recommend()`), bukan parameter mati
- [ ] **Belum ada studi "dengan forecast vs tanpa forecast"** — sesuai peringatan 6.3 lama, forecast SUDAH tersambung secara arsitektur tapi belum ada perbandingan terpisah yang mengukur apakah rekomendasi hasil blending forecast benar-benar lebih baik (delay/queue/LOS lebih rendah) dibanding tanpa forecast. Kalau sempat sebelum 31 Agustus, jadi bahan kuat buat laporan teknis; kalau tidak, tulis jujur sebagai kerja lanjutan (lihat 6.3 versi baru untuk detail angka evaluasi model)
- [ ] **Catatan lingkungan (bukan bug):** `simulation/.venv` tidak punya `supabase`, jadi `pytest tests/test_forecast_client.py` di venv itu gagal 1 dari 8 test (`ModuleNotFoundError: No module named 'supabase'` saat `run_tls_simulation.py` diimpor). Sama seperti pola yang sudah didokumentasikan di item 1.5 — jalankan pakai `backend/.venv` (yang punya `supabase`) untuk test itu, bukan regresi

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
- [ ] Digital Twin: state awal (`signalStatuses`) hardcode 32s/18s sebelum data live masuk — kasih indikator visual "memuat..." biar tidak kelihatan seperti data asli. **Masih belum, dicek ulang 27 Agustus** — commit `47fff3f` (lihat 3.4) merombak 162 baris `digitaltwinview.tsx` tapi tidak menyentuh hardcode ini (`signalStatuses` baris 44-48 masih `32`/`18` apa adanya)
- [x] ~~`CameraFeedPanel.tsx` masih ada `console.log` development di `onTimeUpdate`~~ — dicek 26 Agustus, sudah tidak ada `console.log` di file itu sama sekali. Sudah beres (mungkin lewat commit lain), tidak perlu dikerjakan lagi
- [ ] **Baru (26 Agustus):** kartu "memuat..." di 3.3 baris pertama sekarang lebih relevan lagi — `SignalStatusPanel`/`RecommendationPanel` baru dibangun (1.7) untuk kondisi live, tapi belum ada state loading eksplisit pas pertama kali dashboard dibuka sebelum poll pertama selesai (sekilas bisa kelihatan seperti data lama sebelum data live masuk)

### 3.4 [REGRESI ditemukan & diperbaiki 27 Agustus] Rombak `SharedSignalPanels` sempat balik ke jam simulasi client-side

Melpi commit `47fff3f` ("perbaikan dahsboard", 26 Agustus 23:51) menggabungkan `RecommendationPanel`+`SignalStatusPanel` jadi satu komponen baru `SharedSignalPanels.tsx`, supaya kedua panel share satu sumber fase/countdown (niatnya benar — hindari drift antar panel). **Tapi implementasinya membangun jam simulasi SENDIRI di browser** (`visualPhase`/`visualPhaseState`/`visualRemaining`, state machine lokal yang menebak sendiri kapan fase pindah), bukan menurunkan dari data server — ini persis kebalikan dari yang sudah dibangun susah payah di item 1.7 ("jam harus jalan di SERVER, bukan disimulasikan per-browser"). Ditemukan Rahmat 27 Agustus pas audit menyeluruh, diperbaiki hari yang sama:

- [x] **Bug 1 — sumber data salah:** `SignalStatusPanel.tsx` versi commit itu sama sekali tidak lagi membaca `signal.currentPhase`/`remainingSeconds`/`phases`/`nextPhase` dari backend untuk tampilan fase/countdown aktifnya — semuanya diganti simulasi lokal yang cuma di-seed sekali dari data server lalu jalan sendiri. **Efek nyata:** kalau `RuleBasedEngine` merevisi durasi fase aktif di tengah jalan (misal karena data forecast baru masuk), server tahu tapi browser tidak — user melihat angka yang sudah basi sampai NAMA fase-nya berganti
- [x] **Bug 2 — durasi kuning tidak cocok:** simulasi lokal hardcode kuning **5 detik**, padahal `SignalService::YELLOW_SECONDS` di backend itu **4 detik** — dua sumber kebenaran beda angka untuk hal yang sama
- [x] **Perbaikan:** `SharedSignalPanels.tsx` ditulis ulang — `sharedVisualPhase`/`sharedVisualPhaseState`/`sharedVisualRemaining` sekarang diturunkan LANGSUNG dari `activeSignal.currentPhase`/`remainingSeconds` (data server asli), dengan countdown per-detik yang cuma menghaluskan tampilan DI ANTARA dua poll (resync penuh tiap kali `page.tsx` poll ulang tiap 5 detik) — pola yang sama persis dengan yang sudah terbukti benar sebelumnya di item 1.7, bukan pola baru. Status GREEN/YELLOW diturunkan dari `remainingSeconds <= YELLOW_SECONDS` (data server), bukan ditebak sendiri. Konstanta kuning diseragamkan jadi **4 detik** di 3 file frontend (`SharedSignalPanels.tsx`, `RecommendationPanel.tsx`, `SignalStatusPanel.tsx`) dengan komentar eksplisit "harus sama dengan backend" di tiap file, plus 3 titik hitungan `+5`/`?5:` yang tadinya hardcode di `RecommendationPanel.tsx`/`SignalStatusPanel.tsx` (perhitungan waktu tunggu lengan lain & progress siklus) ikut dikoreksi ke 4
- [x] **Diverifikasi:** `npm run build` sukses (13/13 route ter-generate, tidak ada error TypeScript baru)
- [ ] **Belum:** verifikasi manual lewat browser sungguhan (bandingkan angka dashboard vs `GET /signal/status` langsung) — perbaikan ini baru dites lewat build, belum lewat browser hidup seperti verifikasi item 1.7 sebelumnya
- [ ] **Perlu disampaikan ke Melpi:** kalau mau tambah fitur visual baru di panel sinyal ke depannya, jangan bikin state/timer baru yang jalan sendiri di `useEffect` — selalu turunkan dari prop `signal`/`recommendation` yang datang dari poll backend. Itu prinsip yang sudah disepakati sejak item 1.7 tapi belum tertulis eksplisit sebagai aturan sebelum sesi ini

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
- [x] **Update 26 Agustus malam:** forecast → decision engine (2.4/bagian 6) **sudah selesai** dikerjakan Yuli (`d5ec395`, `3c6ee4c`) — kotak 6 di diagram arsitektur tidak lagi berdiri sendiri
- [ ] **Baru:** siapa yang jalankan `run_ingest.py` (CV → Supabase) secara rutin sebelum demo — sekarang manual, tidak ada scheduler (lihat bagian 7.2). Perlu SOP jelas siapa & kapan, supaya data di dashboard demo tidak basi
- [x] `backend/app/models/lstm_forecast.py` + `backend/tests/test_lstm_forecaster.py` (kode mati, lihat 2.3) sudah dihapus
- [ ] **Baru:** belum ada studi "dengan forecast vs tanpa forecast" yang membandingkan kualitas rekomendasi (lihat 6.3) — kalau ada waktu sebelum 31 Agustus, siapa yang mengerjakan?

---

## 6. Integrasi Pipa Penuh — fokus 26 Agustus sore/malam

Ditulis setelah scan menyeluruh siang ini, **diperbarui 26 Agustus malam** setelah Yuli menutup item 2.4 (lihat detail lengkap di 2.4 di atas). Ini menjawab arahan: TrafficState live → LSTM → Scenario Generator → Traffic Simulation → Performance Analysis → Decision Engine (rule-based dulu) → Recommendation.

### 6.1 Peta status tiap kotak (per 26 Agustus malam)

| Kotak (diagram arsitektur) | Status | Kode |
|---|---|---|
| 1-3. CV → Traffic State | **Hidup, tapi bukan realtime streaming** — proses video REKAMAN (43 menit), hasilnya di-ingest MANUAL ke Supabase | `cv/vehicle_counter_pingit.py` → `run_ingest.py` (lihat 7.1-7.2) |
| 4-5. Virtual Intersection / Realtime Traffic State | **Hidup** — `TrafficStateBuilder` baca Supabase, dipakai `/recommendation` & `/signal/status` tiap poll | `backend/app/pipeline/traffic_state_builder.py` |
| 6. Traffic Forecast (LSTM) | **Hidup DAN tersambung** — model per-approach baru (`per_approach_forecast_service.py`) dipanggil langsung oleh kotak 10, di jalur live maupun batch (lihat 2.4) | `backend/app/services/per_approach_forecast_service.py`, endpoint `POST /api/forecast/approaches` |
| 7-9. Scenario Generator + Simulasi + Performance Analysis (LOS) | **Jalan (1.5), dan sekarang baseline-nya juga mempertimbangkan forecast** (2.4, jalur batch) — tapi masih cuma di `run_tls_simulation.py`, tidak nempel ke dashboard live | `simulation/scenario_generator.py`, `simulation/forecast_client.py` |
| 10. Decision Engine | **Hidup, dan sekarang forecast-aware** — `RuleBasedEngine.recommend()`/`recommend_cycle()` terima parameter `forecast` opsional (dipakai `SignalService`, `RecommendationService`, DAN `ScenarioEngine`). PPO belum ada (1.6) | `decision_engine/rule_based_engine.py` |
| 11. Signal Timing Recommendation | **Hidup & live**, sekarang blend 70% state aktual + 30% forecast 60 detik ke depan | `SignalService`, `RecommendationService` |
| 12. Dashboard | **Hidup**, sinkron dengan 11 | `frontend/src/components/RecommendationPanel.tsx`, `SignalStatusPanel.tsx` |

**Kesimpulan:** rantai **1→5→6→10→11→12 sekarang nyambung penuh dan live** — kotak 6 (LSTM) yang sebelumnya "berdiri sendiri" sudah masuk ke kotak 10 di jalur live maupun batch. Yang **masih belum nyambung**: kotak 7-9 (Scenario Generator+LOS) ke kotak 11-12 (cuma nempel ke jalur batch `run_tls_simulation.py`, bukan dashboard — tetap seperti keputusan sadar di 1.5, bukan berubah), dan siklus 4-lengan penuh (`CyclePlan`) belum diterapkan ke SUMO live (lihat sisa item terbuka di 1.7).

### 6.2 [SELESAI 26 Agustus malam] Sambungkan LSTM → Decision Engine — apa yang benar-benar dikerjakan

Dokumen versi siang tadi menyusun 2 opsi desain dan merekomendasikan mulai dari Opsi 2 (risiko rendah, batch dulu). **Yang benar-benar terjadi: Yuli mengerjakan DUA-DUANYA sekaligus**, bukan cuma salah satu:

- **Opsi 1 (jalur live, `SignalService`/`RecommendationService`)** — diimplementasi. Tiap transisi fase / tiap `POST /recommendation`, service ambil 24 `TrafficState` terakhir, panggil model forecast, hasilnya di-blend (bobot 0.3) ke input `recommend_cycle()`/`recommend()`.
- **Opsi 2 (jalur batch, `ScenarioEngine`)** — diimplementasi juga, lewat `simulation/forecast_client.py` yang baru + `run_tls_simulation.py::loadForecast()`.

Pertanyaan B (bagaimana kalau forecast gagal) dijawab dengan pola fallback yang sama gayanya dengan seluruh proyek ini di kedua jalur: exception ditangkap, jatuh ke `forecast=None`, `source` tetap `"rule-based"` (bukan `"rule-based+forecast"`) — dites eksplisit di kedua jalur. Detail teknis lengkap (nama file, nama fungsi, cakupan test) ada di item **2.4** di atas, tidak diulang di sini.

### 6.3 Peringatan jujur — forecast belum tentu bikin "lebih valid" (diperbarui dengan angka evaluasi nyata)

Peringatan versi siang tadi (data kecil, 2 fitur antrean baru) sudah **sebagian tertutup** — `queueLengthVeh`/`queueLengthMEst` sudah punya data asli sejak 25 Agustus DAN dipakai training (lihat 2.3). Tapi peringatan intinya (forecast belum tentu memperbaiki hasil) **masih berlaku**, sekarang dengan angka evaluasi nyata dari `forecasting/outputs/lstm/per_approach/metadata.json` (dicek Rahmat 26 Agustus malam):

- **Model mengalahkan naive baseline** (prediksi = ulangi nilai terakhir) di ke-4 lengan — MAE gabungan 1.65 vs baseline 2.30, dan `beatsNaiveBaseline: true` di west/south/east/north. Ini sinyal positif nyata, bukan cuma "modelnya jalan"
- **TAPI test set-nya sangat kecil: cuma 16 sequence total (4 per lengan)** dari 1044 sequence training — `beatsNaiveBaseline` di angka sekecil ini belum bisa diklaim signifikan secara statistik, cuma indikasi arah yang benar
- MAE/RMSE di file metadata ini dalam **satuan asli** (kendaraan, meter) — bukan satuan ternormalisasi seperti catatan PeMS04 di `CLAUDE.md`. Misal `queueLengthMEst` MAE 4.22m dari rentang data 0-41m — cukup masuk akal untuk laporan
- Data training tetap kecil untuk time-series (~538 baris mentah, ~45 menit, satu sesi rekaman) — keterbatasan generalisasi yang sama seperti dibahas di `rencana-lstm-forecast.md`/`CLAUDE.md`
- **Mitigasi yang sudah diambil (bukan diabaikan):** bobot forecast sengaja dikecilkan ke 0.3 (70% tetap state aktual), justru karena ketidakpastian ini — keputusan desain yang konsisten dengan peringatan ini, bukan bertentangan

**Masih berlaku:** belum ada studi terpisah yang membandingkan hasil rekomendasi PAKAI forecast vs TANPA forecast pada metrik yang sama (delay/queue/LOS). Kalau sempat sebelum 31 Agustus, itu jadi bukti kuat buat laporan teknis. Kalau tidak, tulis di laporan sebagai "diintegrasikan secara arsitektur dengan bobot konservatif (30%) karena data training kecil; validasi dampaknya terhadap kualitas rekomendasi adalah kerja lanjutan" — jujur, bukan diklaim terbukti akurat.

### 6.4 Pembagian kerja bagian ini — hasil aktual, bukan rencana

Rencana siang tadi menugaskan implementasi 6.2 ke Rahmat. **Yang terjadi: Yuli mengerjakannya sendiri**, dua-duanya (jalur live dan batch) sekaligus, plus dokumentasi (`forecasting/README.md`, tabel fitur `rencana-lstm-forecast.md`) — lebih menyeluruh dari rencana awal. Wajar karena forecast tetap satu domain dengan LSTM yang sudah dipegang Yuli sejak awal; tidak perlu koordinasi ulang untuk item ini.

| Siapa | Rencana siang tadi | Yang terjadi malam ini |
|---|---|---|
| Rahmat | Implementasi 6.2 | **Tidak jadi mengerjakan ini** — Yuli sudah menutupnya duluan. Kerjaan Rahmat malam ini: verifikasi ulang (`pytest`), audit dokumen ini |
| Yuli | Dokumentasi saja (README/tabel fitur), evaluasi akurasi kalau sempat | **Semuanya**: model baru (per-approach), serving baru, wiring ke `RuleBasedEngine`/`SignalService`/`RecommendationService`/`ScenarioEngine`, `forecast_client.py` baru, dokumentasi, DAN evaluasi akurasi (lihat 6.3) |
| Melpi | Beres-beres UI kecil (3.3), tidak ikut bagian 6 | Tidak berubah — tetap di jalur frontend |

---

## 7. Temuan audit CV (26 Agustus) — belum pernah tercatat di dokumen manapun

### 7.1 "Realtime" itu maksudnya apa, sebenarnya

Penting buat jujur ke juri: CV **TIDAK** memproses siaran langsung (RTSP/live feed). `vehicle_counter_pingit.py` membaca file `.mp4` REKAMAN 43 menit yang sudah ada di `cv/videos/`. Tidak ditemukan kode RTSP/streaming di mana pun di repo. Jadi "integrasi realtime Traffic State" yang benar sekarang artinya: **CV diproses offline dari rekaman → hasil di-ingest ke Supabase → backend baca Supabase "seolah-olah" live** (lewat `videoTimeRef` yang mensimulasikan posisi video, lihat `fetchTrafficState()` di `supabaseData.ts`). Bukan pipeline live kamera sungguhan. Ini bukan masalah buat demo (memang begitu desainnya dari awal, disepakati di roadmap), tapi jangan sampai kepeleset bilang "realtime CCTV" ke juri kalau ditanya detail.

### 7.2 Ingest CV → Supabase itu manual, tidak ada scheduler

`run_ingest.py` (root repo) harus dijalankan manual oleh seseorang setiap kali ada hasil CV baru. Tidak ada cron/APScheduler di seluruh repo. Kalau video/CSV baru diproses tapi lupa jalankan `run_ingest.py`, dashboard akan menampilkan data lama tanpa ada tanda peringatan. **Perlu SOP jelas** — siapa yang jalankan, kapan, terutama H-1 sebelum demo.

### 7.3 Kabar baik: identitas koridor `east` sudah tertutup

`docs/roadmap.md` (per 17 Agustus) mencatat ini sebagai risiko besar yang menggantung ("kalau ternyata Magelang, east dan north menghitung lengan yang sama dua kali"). **Sudah diverifikasi dan ditutup** lewat commit `700140c` (24 Agustus) — `simulation/verify_corridor_bearing.py` mengroskek bearing OSM vs klasifikasi CV secara independen: **Jl. Diponegoro = timur, Jl. Magelang = utara**, cocok dengan kode. `docs/roadmap.md` sendiri belum diupdate untuk menghapus tanda risiko ini — perlu dirapikan supaya tidak membingungkan pembaca dokumen nanti (roadmap.md itu sendiri sudah basi sejak 17 Agustus, banyak checklist di situ yang sudah selesai tapi belum dicentang).

### 7.4 [TERJAWAB 27 Agustus] Kalibrasi `north` — ternyata sudah dikalibrasi, bukan default

`roadmap.md` (17 Agustus) mencatat counting line `north` masih pakai nilai default, belum dikalibrasi, padahal menyumbang volume tertinggi. Tidak ditemukan commit lanjutan yang secara eksplisit menyebut kalibrasi ulang `north`. Dicek langsung ke `cv/vehicle_counter_pingit.py` (bukan cuma cari commit message) — dua temuan menutup kekhawatiran ini:

1. **Zona `simpang_tengah` (proxy `north`, CCTV_2) sudah dikalibrasi manual lewat klik interaktif** (`cv/kalibrasi_zona.py --kamera CCTV_2`), BUKAN nilai default — kode menyimpan riwayat revisi eksplisit (v1 kotak kasar → v2 → v3 baji mengikuti coretan biru di frame asli → v4 SEKARANG, hasil klik interaktif). Garis crossing `MAGELANG`/`DIPONEGORO` di CCTV_2 juga dari alat kalibrasi terpisah (`cv/kalibrasi_crossing.py`), bukan angka default. Ke-4 kamera (bukan cuma north) punya pola riwayat yang sama.
2. **Bug key-matching yang SEBELUMNYA bikin `north` diam-diam jatuh ke default 1 lajur sudah ditemukan & diperbaiki 25 Agustus** — komentar eksplisit di `LAJUR_PER_LENGAN` (baris ~402-420): key harus `simpang_tengah` (bukan `utara`), sebelum diperbaiki key `utara` tidak pernah cocok. Sekarang sudah benar (`simpang_tengah: 2`).

Dua-duanya ada di commit `5b2c18e` (25 Agustus, "feat(cv): tambah deteksi antrean ke vehicle_counter_pingit.py"). **Kesimpulan: klaim "north pakai nilai default" di `roadmap.md` sudah tidak berlaku** — sudah dikalibrasi sama seriusnya dengan 3 lengan lain. Yang TIDAK tertutup oleh temuan ini (beda concern): seberapa AKURAT kalibrasinya secara formal — itu masuk keterbatasan yang lebih luas dan sudah jujur didokumentasikan di 7.5 (nol validasi mAP/precision/recall untuk SEMUA kamera, bukan cuma north), bukan hal baru.

### 7.5 Tidak ada validasi akurasi deteksi

Tidak ditemukan ground truth, precision/recall, atau mAP yang pernah dihitung untuk deteksi/tracking YOLO+ByteTrack di repo manapun. Validasi yang ada sejauh ini murni sanity-check aritmetika (rasio antre wajar secara fisik, lihat 1.2) — bukan pengukuran akurasi formal terhadap data berlabel. Kalau juri tanya "seberapa akurat deteksinya", jawaban jujurnya sekarang adalah "belum diukur formal, validasi tidak langsung lewat konsistensi fisik data" — bukan angka mAP/precision tertentu. `docs/roadmap.md` sempat merencanakan anotasi CVAT + mAP/MOTA/IDF1 (Fase 3) tapi ini eksplisit ada di daftar "boleh dikorbankan" kalau waktu mepet (lihat rencana kontingensi di roadmap.md) — jadi ini keputusan yang SUDAH diambil sadar, bukan kelupaan.

### 7.6 `hitung_antrean()` — keterbatasan yang didokumentasikan sendiri di kode (bukan bug tersembunyi)

Dicatat langsung sebagai docstring di `vehicle_counter_pingit.py` (25 Agustus): (1) ID-switch ByteTrack saat antrean padat bisa menurunkan `queue_length_veh` secara sistematis justru saat kondisi paling macet — kebalikan dari yang diinginkan; (2) state tracking antrean tidak dibersihkan kalau track_id hilang total (leak kecil, tidak masalah untuk rekaman 49 menit, tapi perlu dibersihkan untuk rekaman berjam-jam). Kedua-duanya trade-off sadar, bukan sesuatu yang "belum sempat" — aman dibawakan ke laporan sebagai keterbatasan yang diketahui.

---

## 8. Rencana Integrasi Live — 27 Agustus (H-4)

Dipicu temuan audit 27 Agustus: dashboard live dan jalur simulasi (kotak 4/7/8/9) ternyata **2 pipeline yang tidak pernah bertemu** — 0% keputusan yang tampil di dashboard pernah melalui Scenario Generator/Traffic Simulation/Performance Analysis. Detail lengkap temuan ada di `docs/status-integrasi-diagram-arsitektur.md`. Dua keputusan didiskusikan dengan user (bukan diputuskan sepihak) sebelum pembagian ini ditulis:

1. **Desain unifikasi: Opsi A (cache background job)** — dipilih dari 3 opsi yang dibahas di `docs/rencana-scenario-generator.md` bagian 4.1. Rancangan teknis lengkap ada di dokumen itu, tidak diulang di sini.
2. **Penanggung jawab: dibagi Yuli (backend/simulasi) + Melpi (frontend)** — BUKAN Rahmat, karena sudah dinyatakan tidak bisa pegang bagian ini untuk saat ini.

### 8.1 Pembagian kerja lengkap (integrasi + sisa item lama yang masih terbuka)

| Siapa | Kerjaan | Rujukan |
|---|---|---|
| **Yuli** | `simulation/scenario_worker.py` baru (loop background, panggil `ScenarioEngine.recommend()`, tulis ke tabel cache baru) + endpoint backend baca cache dengan fallback aman ke `RuleBasedEngine` | `rencana-scenario-generator.md` 4.1, "Yuli — backend & simulasi" |
| **Yuli** | Studi validasi "rekomendasi DENGAN forecast vs TANPA forecast" (item 2.4 yang masih terbuka) — sinergi alami dengan kerjaan cache di atas, bisa pakai data yang sama | item 2.4 |
| **Melpi** | Tampilkan indikator `source` (`"scenario-generator"` vs `"rule-based"`) di `RecommendationPanel`/`SignalStatusPanel` setelah backend Yuli siap; opsional: badge LOS/delay kalau ada waktu | `rencana-scenario-generator.md` 4.1, "Melpi — frontend" |
| **Melpi** | Verifikasi manual lewat browser hidup untuk perbaikan regresi `SharedSignalPanels` (item 3.4) — baru lolos `npm run build`, belum dites manual | item 3.4 |
| **Melpi** | 2 item P2 lama yang masih belum: Digital Twin hardcode 32s/18s, indikator loading sebelum poll pertama | item 3.3 |
| **Melpi** | Siklus 4-lengan penuh ke SUMO live (`traci.trafficlight.setProgramLogic()`) — **beda domain dari kerjaan frontend di atas** (Python/TraCI di `simulation/`), lihat catatan risiko di 8.2 | item 1.7, `rencana-scenario-generator.md` 4.2, 8.2 |
| **Rahmat** | PPO (1.6, bonus non-blocking, tidak berubah), kalibrasi kandidat "agresif" +20% kalau ada waktu (P2), SOP/scheduler ingest CV (7.2) | item 1.6, `rencana-scenario-generator.md` 4.3, temuan 7.2 |

### 8.2 Item yang sempat belum dapat pemilik — sudah dijawab 27 Agustus

- **Siklus 4-lengan penuh ke SUMO live** (`traci.trafficlight.setProgramLogic()`, item 1.7 & `rencana-scenario-generator.md` 4.2) — **ditugaskan ke Melpi.** Catatan penting: ini kerjaan Python/TraCI di `simulation/` (bukan frontend/React seperti kerjaan Melpi selama ini) — beda domain dari jalur yang sudah terbukti buat dia. Kalau ternyata butuh ramp-up signifikan buat masuk ke kode SUMO/TraCI, jangan dipaksakan sampai mengorbankan 3.3/3.4 (item frontend yang sudah pasti jadi tanggung jawabnya) — komunikasikan cepat kalau ini ternyata terlalu berat digabung dengan kerjaan frontend-nya.
- ~~Kalibrasi ulang `north`~~ — **selesai, ternyata sudah dikalibrasi** (bukan kerjaan baru). Lihat temuan lengkap di 7.4: sudah dicek langsung ke kode, north (proxy `simpang_tengah`) sudah dikalibrasi lewat alat klik interaktif sejak 25 Agustus (`5b2c18e`), bukan nilai default seperti dikira `roadmap.md` lama. Tidak perlu dikerjakan ulang.

### 8.3 Realita waktu

4 hari tersisa sebelum 31 Agustus (per 27 Agustus). Kerjaan 8.1 untuk Yuli (worker + endpoint cache) itu yang paling berat dari semua item terbuka — kalau ternyata tidak cukup waktu, versi minimal yang tetap bernilai sudah ditulis eksplisit di `rencana-scenario-generator.md` ("Kalau waktu ternyata tidak cukup untuk semua ini..."), jangan dipaksakan versi penuh sampai mengorbankan item lain yang lebih pasti selesai.

### 8.4 Update implementasi Yuli — 27 Agustus

- [x] `simulation/scenario_worker.py` sudah dibuat: loop 60 detik, reuse `ForecastClient` dan `ScenarioEngine`, upsert satu cache per simpang, serta tidak mematikan proses bila satu iterasi gagal.
- [x] Backend sudah membaca `liveScenarioCache` dengan batas kesegaran 120 detik dan fallback aman ke rule-based jika tabel/cache tidak tersedia atau basi. Payload `/recommendation` sekarang juga dapat membawa `avgDelaySeconds`, `avgQueueLengthM`, `los`, dan `candidateId`.
- [x] Skema tabel tersedia di `backend/app/db/live_scenario_cache.sql`; harus dijalankan sekali di Supabase SQL Editor sebelum worker pertama.
- [x] Studi forecast vs tanpa forecast sudah dibuat reproducible lewat `python scenario_worker.py --compare-forecast`; hasil ditulis ke `simulation/outputs/forecast_impact.json` dan memuat delta delay, antrean, dan throughput.
- [x] Unit test cache segar/basi/error dan regression test terkait lulus (21 test terpilih). Full suite lokal: 47 passed; 8 test integrasi Supabase gagal karena akses jaringan sandbox ditolak, bukan kegagalan assertion kode baru.
- [x] Verifikasi end-to-end selesai 27 Agustus: worker `--once` berhasil meng-upsert kandidat `balanced` (22s, delay 13,37s, antrean 35m, throughput 9, LOS B), lalu `POST /recommendation` mengembalikan HTTP 200 dengan `source="scenario-generator"` dan metrik yang sama. Fallback cache basi/error sudah dicakup unit test `test_live_scenario_cache.py`.
- [x] Studi dijalankan 27 Agustus pada satu snapshot yang sama. Dengan forecast: delay **13,37s vs 15,57s** (-2,20s), antrean **35m vs 42m** (-7m), throughput **9 vs 6** (+3), LOS tetap B. Bukti lengkap ada di `docs/hasil-studi-forecast.md` dan data mentah `simulation/outputs/forecast_impact.json`. Ini hasil satu eksperimen, bukan bukti signifikansi statistik atau generalisasi model.

# Status Integrasi vs Diagram Arsitektur — 27 Agustus 2026

Menjawab pertanyaan langsung: **apakah kode SmartTwin sudah mengintegrasikan ke-12 kotak di diagram arsitektur (Traffic Monitoring → CV → Digital Twin Platform → Decision Engine → Dashboard) secara penuh?**

**Metodologi:** tiap kotak dinilai berdasarkan bukti konkret yang sudah diverifikasi (bukan laporan tim, bukan asumsi) — dibaca langsung dari kode per 27 Agustus 2026, dicocokkan ke hasil audit menyeluruh sepanjang 26-27 Agustus (`pembagian-tugas-tahap-akhir.md` bagian 6-7, `rencana-lstm-forecast.md`, `rencana-scenario-generator.md`, `CLAUDE.md`). Persentase ini **penilaian subjektif berdasar bukti**, bukan metrik resmi/terstandar — anggap sebagai estimasi kesiapan, bukan angka pasti.

---

## KOREKSI PENTING (ditambahkan 27 Agustus, setelah laporan awal) — dua jalur yang TIDAK PERNAH ketemu

Persentase per kotak di bagian bawah menilai **apakah komponennya sendiri berfungsi benar** — itu valid, tapi bisa menyesatkan kalau dibaca seolah artinya "pipeline di diagram ini 70-90% mengalir seperti gambarnya". **Kenyataannya tidak.** Dicek langsung ke kode (`grep ScenarioEngine` di seluruh `backend/app/` — nol hasil; `RecommendationService`/`SignalService` dua-duanya instansiasi `RuleBasedEngine()` langsung, bukan `ScenarioEngine`):

- **Jalur LIVE — yang dashboard-mu benar-benar tampilkan:**
  `TrafficState (Supabase) → LSTM forecast → RuleBasedEngine (matematika langsung, TANPA simulasi) → Recommendation/SignalStatus → Dashboard`
  Jalur ini **melompati kotak 4 (SUMO dipakai untuk keputusan), 7 (Scenario Generator), 8 (Traffic Simulation), 9 (Performance Analysis) SELURUHNYA.** Rekomendasi yang muncul di dashboard tidak pernah diuji lewat simulasi SUMO atau dianalisis LOS-nya — murni rumus demand-score.

- **Jalur BATCH — terpisah total, dipicu manual dari terminal (`python run_tls_simulation.py`):**
  `TrafficState → forecast → RuleBasedEngine (baseline) → Scenario Generator (3 kandidat) → Traffic Simulation (SUMO beneran per kandidat) → Performance Analysis (LOS dst.) → pemenang → disimpan ke tabel simulations/simulationMetrics`
  Tabel `simulations`/`simulationMetrics` ini **tidak pernah dibaca balik oleh endpoint manapun yang dashboard pakai** (`/recommendation`, `/signal/status`) — diverifikasi lewat `grep` di seluruh `backend/app/api`+`backend/app/services`, nol referensi balik.

**Artinya:** bukan "kotak 7-9 baru 70-75% nyambung ke live" — yang benar **0% keputusan yang tampil di dashboard pernah melalui simulasi/analisis performa sama sekali.** Dua alur ini berjalan sendiri-sendiri, hasilnya tidak pernah bertemu. Ini bukan salah tim — sudah didokumentasikan sebagai keputusan sadar sejak item 1.5 (3 simulasi SUMO penuh per HTTP request terlalu berat untuk endpoint yang dipoll tiap 5 detik) — tapi kalau ditanya "apakah sudah selaras seperti diagram", jawaban jujurnya **belum, ada 2 pipeline paralel yang tidak saling bicara**, bukan 1 pipeline utuh seperti yang digambar.

Rencana untuk menyatukan dua jalur ini (dengan 3 opsi desain trade-off) sudah ditulis di `docs/rencana-scenario-generator.md` bagian 4.1 — itu **satu-satunya pekerjaan** yang, kalau selesai, benar-benar membuat sistem berjalan SATU alur utuh persis seperti diagram, bukan dua alur terpisah.

---

## Ringkasan per kotak (skor komponen — baca dengan koreksi di atas)

| # | Kotak (diagram) | % | Status singkat |
|---|---|---|---|
| 1 | Traffic Monitoring Data (Image/Video) | **85%** | Jalan penuh, tapi REKAMAN 43 menit, bukan live feed |
| 2 | YOLO + ByteTrack | **80%** | Jalan, tervalidasi tidak langsung — nol validasi akurasi formal |
| 3 | Traffic State Builder | **95%** | Jalan, terverifikasi fisik masuk akal |
| 4 | Virtual Intersection (SUMO Model) | **100%** | Network asli Simpang Pingit, terverifikasi berkali-kali |
| 5 | Realtime Traffic State | **80%** | Live-polling jalan, tapi sumbernya di-ingest manual, tanpa scheduler |
| 6 | Traffic Forecast (LSTM) | **90%** | Terlatih, tervalidasi, DAN sudah tersambung ke Decision Engine |
| 7 | Scenario Generator | **70%** | Jalan & terverifikasi, tapi cuma di jalur batch, belum live |
| 8 | Traffic Simulation | **75%** | Jalan & terverifikasi, sama batasan batch-only |
| 9 | Performance Analysis (Delay/Queue/Throughput/LOS) | **75%** | Ke-4 metrik nyata dihitung, sama batasan batch-only |
| 10 | Adaptive Decision Engine (**PPO**) | **15%*** | PPO literal: belum dimulai. Fungsi kotak: diisi rule-based (disengaja) |
| 11 | Signal Timing Recommendation | **95%** | Live, teruji lewat browser berkali-kali |
| 12 | Dashboard | **85%** | Live & sinkron, 1 regresi baru ketemu+diperbaiki, verifikasi browser belum diulang |

**Rata-rata sederhana (12 kotak, bobot sama): ≈ 78%**

**\*Kotak 10 butuh dibaca dua arah — lihat penjelasan di bawah, jangan pakai angka 15% itu sendirian tanpa konteks.**

---

## Dua cara baca angka keseluruhan — kenapa tidak cuma satu angka

Diagram ini menyebut kotak 10 secara eksplisit sebagai **"Proximal Policy Optimization"** — bukan "Decision Engine" generik. Itu bikin kotak ini beda dari 11 kotak lainnya: PPO **memang belum pernah dikerjakan sama sekali** (bukan "belum selesai", tapi "belum dimulai" — cuma ada `simulation/requirements-rl.txt` berisi 2 nama paket, nol kode RL, nol environment wrapper, lihat `CLAUDE.md`). Tapi tim sudah SECARA SADAR mengisi slot itu dengan `RuleBasedEngine`/`select_best_scenario()` sebagai pengganti sementara — bukan lubang kosong yang dibiarkan, dan interface-nya (`recommend()`) sengaja dibuat bisa langsung ditukar PPO tanpa ubah kode lain (lihat `decision_engine/rule_based_engine.py`, `simulation/scenario_generator.py::ScenarioEngine`).

Jadi ada dua pertanyaan berbeda, dua jawaban berbeda:

| Pertanyaan | Angka kotak 10 | Overall (rata-rata 12 kotak) |
|---|---|---|
| **"Apakah PPO, PERSIS seperti label di diagram, sudah ada?"** | 15% (cuma dependency list) | **≈ 78%** |
| **"Apakah kotak 10 TERISI dan sistem berfungsi end-to-end?"** | 90% (rule-based, disengaja, teruji) | **≈ 90%** |

**Rekomendasi cara jawab ke juri/laporan teknis:** pakai kerangka yang sudah dipakai `CLAUDE.md` — PPO itu eksplisit "out of scope, non-blocking bonus" (item 1.6, di-time-box), bukan kegagalan mengerjakan. Sistem tetap lengkap dan berfungsi penuh tanpa PPO karena rule-based sudah mengisi peran yang sama. Jangan bilang "PPO sudah 90%" (itu ngaco, kodenya tidak ada) — bilang **"kotak 10 terisi rule-based yang teruji dan bisa ditukar PPO kapan saja; PPO sendiri sengaja belum dikerjakan, di luar scope 16 hari"**.

---

## Detail per kotak — bukti dan alasan pengurangan dari 100%

### 1. Traffic Monitoring Data (Image/Video) — 85%
**Bukti jalan:** `cv/vehicle_counter_pingit.py` memproses 4 kamera × 49 menit rekaman, hasil **538 jendela per kamera, nol error** (item 1.2, diverifikasi 25 Agustus).
**Kenapa bukan 100%:** ini REKAMAN `.mp4`, bukan siaran langsung (RTSP/live feed) — tidak ada kode streaming kamera di mana pun di repo (temuan 7.1). Untuk demo ini bukan masalah (memang desain dari awal, disepakati di roadmap), tapi kalau diukur literal terhadap label "Traffic Monitoring" (yang menyiratkan pemantauan langsung), ini bukan pemantauan real-time sungguhan.

### 2. YOLO + ByteTrack — 80%
**Bukti jalan:** deteksi+tracking jalan penuh dalam run 43 menit di atas, plus logika antrean baru (`hitung_antrean()`) tervalidasi FISIK masuk akal (rasio antre badan simpang 34% vs lengan pendekat 43-77% — kalau logikanya asal, keempatnya akan mirip, item 1.2).
**Kenapa bukan 100%:** **nol validasi akurasi formal** — tidak ada ground truth, precision/recall, atau mAP yang pernah dihitung di repo manapun (temuan 7.5). Juga ada keterbatasan yang didokumentasikan sendiri di kode: ID-switch ByteTrack saat antrean padat bisa MENURUNKAN `queue_length_veh` justru saat kondisi paling macet (temuan 7.6). Status kalibrasi `north` juga belum jelas dicek ulang pasca perubahan ke pendekatan zona (temuan 7.4).

### 3. Traffic State Builder — 95%
**Bukti jalan:** dua jalur kerja (`cv_csv_bridge.py` untuk batch CSV→Supabase, `backend/app/pipeline/traffic_state_builder.py` untuk agregasi real-time dari `VehicleDetection`), dua-duanya dipakai konsumen nyata (`/api/v1/traffic/live-csv`, `/recommendation`, `/signal/status`). Data queue/density sudah bervariasi & tervalidasi fisik (di atas).
**Kenapa bukan 100%:** ada dua jalur paralel yang melakukan hal serupa (bukan bug, tapi sedikit duplikasi arsitektur yang bisa membingungkan orang baru).

### 4. Virtual Intersection (SUMO Model) — 100%
**Bukti jalan:** `simulation/network/simpang4_pingit.net.xml.gz` — network ASLI Simpang Pingit Yogyakarta (bukan network contoh SUMO), TLS id `SIMPANG_CENTER`, sudah dipakai berkali-kali di run sungguhan (`simulations` id 7, 8, 9), plus program TLS eksplisit baru (`tls_safe.add.xml`) menggantikan program actuated bawaan yang index fasenya sempat tidak cocok. Tidak ada gap yang diketahui di kotak ini.

### 5. Realtime Traffic State — 80%
**Bukti jalan:** `SignalService`/`RecommendationService` polling Supabase tiap request, `TrafficStateBuilder` membangun `TrafficState` segar setiap dipanggil — mekanismenya genuinely live (bukan cache beku), diverifikasi lewat browser berkali-kali (item 1.7).
**Kenapa bukan 100%:** "realtime" di sini artinya "polling database yang live", BUKAN "kamera live" — data di database itu sendiri berasal dari ingest CV yang **manual**, dijalankan `run_ingest.py` oleh seseorang, **tidak ada scheduler/cron** (temuan 7.2). Kalau lupa dijalankan, dashboard akan tetap "live-polling" tapi terhadap data yang sudah basi, tanpa peringatan apa pun ke pengguna.

### 6. Traffic Forecast (LSTM) — 90%
**Bukti jalan:** model per-approach baru (shared LSTM, one-hot encoding) dan model agregat lama, DUA-DUANYA terlatih & tersimpan (`traffic_lstm_per_approach.pt` 226KB, `traffic_lstm.pt` 221.653 bytes), **dan sudah tersambung ke Decision Engine** di jalur live (`SignalService`, `RecommendationService`) MAUPUN batch (`ScenarioEngine` lewat `forecast_client.py`) — diselesaikan Yuli 26 Agustus malam, diverifikasi ulang langsung ke kode oleh Rahmat 27 Agustus (lihat item 2.4). Model mengalahkan naive baseline di ke-4 pendekat (MAE 1.65 vs 2.30).
**Kenapa bukan 100%:** test set evaluasi kecil (cuma 16 sequence, 4 per pendekat) — sinyal positif tapi belum signifikan secara statistik. Belum ada studi terpisah "hasil rekomendasi DENGAN forecast vs TANPA forecast" yang membuktikan forecast benar-benar memperbaiki kualitas keputusan (baru diintegrasikan secara arsitektur, bobot sengaja dikecilkan ke 0.3 karena ketidakpastian ini).

### 7. Scenario Generator (Generate Timing) — 70%
**Bukti jalan:** `generate_candidate_plans()` — 3 kandidat durasi (baseline/agresif/merata) — jalan & terverifikasi lewat run sungguhan (item 1.5).
**Kenapa bukan 100%:** cuma tersambung ke jalur BATCH (`run_tls_simulation.py`, dijalankan manual), **belum ke dashboard live** — keputusan sadar (3 simulasi SUMO penuh per HTTP request terlalu berat buat endpoint yang dipoll tiap 5 detik), bukan kelupaan, tapi tetap berarti kotak ini belum "hidup" di demo dashboard. Angka +20% untuk kandidat agresif juga ilustratif, belum dikalibrasi formula lalu lintas. Detail rencana lanjutan ada di `docs/rencana-scenario-generator.md` (baru ditulis, kepemilikan pindah ke tim).

### 8. Traffic Simulation (loop "diulang untuk skenario berbeda") — 75%
**Bukti jalan:** `simulate_candidate()` menjalankan sesi TraCI baru per kandidat (persis pola panah loop di diagram — "diulang untuk skenario yang berbeda"), pakai `runSimulation()` yang sama dengan run penuh (tidak diduplikasi), TLS program eksplisit (`safe-yellow`) diterapkan tiap sesi.
**Kenapa bukan 100%:** batasan sama seperti kotak 7 (batch-only). `SHORT_SIM_STEPS=90` juga pilihan arbitrer di tengah rentang yang diminta, bukan hasil kalibrasi presisi.

### 9. Performance Analysis (Delay, Queue Length, Throughput, LOS) — 75%
**Bukti jalan:** KE-EMPAT metrik yang persis disebut diagram semuanya nyata dihitung dari simulasi — `averageWaitingTimeSeconds` (delay), `queueLengthVeh` (queue length, definisi "halting" SUMO), `throughputVeh` (throughput, sempat ada bug akumulasi yang sudah diperbaiki di item 1.3), `calculate_los()` (LOS, standar HCM 2000 A-F). Contoh run nyata: delay 13.58-14.05s, queue 35-42m, LOS masuk akal.
**Kenapa bukan 100%:** batasan sama seperti kotak 7-8 (batch-only, belum nempel dashboard live). Kalau nanti kotak 7-8 disambungkan ke live, kotak 9 otomatis ikut karena satu alur yang sama (`simulate_candidate()` menghitung semuanya sekaligus).

### 10. Adaptive Decision Engine (PPO) — lihat penjelasan dua-arah di atas
Jangan dibaca sebagai satu angka tunggal — baca bagian "Dua cara baca angka keseluruhan" di atas.

### 11. Signal Timing Recommendation — 95%
**Bukti jalan:** `SignalService` (siklus 4-lengan "lazy tick", jam wall-clock nyata, transisi otomatis) + `RecommendationService`, dua-duanya baca satu sumber `CyclePlan` yang sama (tidak ada lagi dua endpoint yang bisa beda angka untuk lengan yang sama — bug ini sudah diperbaiki di item 1.7), diverifikasi lewat browser sungguhan berkali-kali.
**Kenapa bukan 100%:** siklus 4-lengan PENUH belum diterapkan ke SUMO live (masih `setPhase()`/`setPhaseDuration()` satu fase per run, belum `setProgramLogic()` custom) — dashboard sudah benar, simulasi SUMO belum ikut rotasi yang sama persis.

### 12. Dashboard — 85%
**Bukti jalan:** live, polling 5 detik, panel Rekomendasi Sinyal + Status Sinyal + CCTV autoplay/loop + Digital Twin, semuanya terhubung ke data backend asli (bukan dummy) — diverifikasi lewat browser berkali-kali sepanjang 25-26 Agustus.
**Kenapa bukan 100%:** **regresi baru ditemukan 27 Agustus** — commit terbaru (`47fff3f`, Melpi) sempat membangun jam simulasi sendiri di browser untuk panel sinyal (bukan menurunkan dari data server), sudah diperbaiki (`861141e`) tapi **verifikasi ulang lewat browser hidup belum dilakukan** (baru lolos `npm run build`). Plus 2 item P2 kecil yang belum: state awal Digital Twin masih hardcode 32s/18s, dan belum ada indikator loading eksplisit sebelum poll pertama selesai.

---

## Ringkasan yang bisa langsung dipakai

**Kalau ditanya "apakah sudah berjalan selaras/nyambung seperti diagram ini": jawaban jujurnya BELUM.** Bukan cuma "beberapa modul belum nyambung" — lebih tepatnya ada **2 pipeline paralel yang tidak pernah bertemu** (lihat bagian "KOREKSI PENTING" di atas). Yang dashboard tampilkan ke user itu jalur pintas (skip kotak 4/7/8/9), bukan alur penuh yang digambar.

Dua angka yang perlu dipisah, jangan dicampur jadi satu:

| Yang diukur | Angka | Artinya |
|---|---|---|
| **Kelengkapan tiap komponen sendiri-sendiri** (12 kotak dinilai satu-satu) | ≈ 78-90% | Hampir semua kotak, kalau dites TERPISAH, sudah berfungsi dan terverifikasi |
| **Apakah 12 kotak itu benar-benar SATU alur mengalir seperti panah di diagram** | **TIDAK** | Ada percabangan: jalur live (dashboard) skip kotak 4/7/8/9 total; jalur batch (kotak 4/7/8/9) hasilnya tidak pernah sampai ke dashboard |

- **Kotak yang paling butuh kerja lanjutan, dan ini yang PALING PENTING dari semua temuan hari ini:** menyatukan jalur live dan jalur batch supaya keputusan yang tampil di dashboard benar-benar sudah melalui simulasi SUMO + analisis performa (kotak 7-8-9), bukan cuma rumus rule-based langsung. 3 opsi desain buat ini sudah ditulis di `docs/rencana-scenario-generator.md` bagian 4.1.
- **Kalau ditanya spesifik "apakah PPO sudah ada": jawab jujur, belum, dan itu keputusan sadar** (time-boxed, non-blocking, item 1.6) — beda urusan dari poin di atas.
- **Yang paling perlu diverifikasi ulang SEGERA** (bukan karena belum dikerjakan, tapi karena baru saja diperbaiki dan belum dites manual): dashboard live pasca perbaikan regresi jam simulasi (kotak 12).

---

*Rujukan: `docs/data-contract.md` (kontrak antar-modul), `docs/pembagian-tugas-tahap-akhir.md` bagian 6-7 (peta status & temuan audit), `docs/rencana-lstm-forecast.md`, `docs/rencana-scenario-generator.md`, `CLAUDE.md` (status LSTM/PPO).*

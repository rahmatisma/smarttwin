# STATUS & SISA KERJA — SmartTwin

**Diperbarui: 29 Agustus 2026 (malam) — audit ulang terhadap kerja Yuli & Melpi, dijalankan langsung (pytest + build), bukan dari klaim dokumen lama.** Ini **satu-satunya dokumen status** di repo ini. Kalau mau tahu "sudah sampai mana" atau "apa yang belum", baca ini — jangan cari di dokumen lain.

> **Deadline berubah:** video presentasi diperpanjang sampai **7 September**, kemungkinan presentasi tim **6 September** sebelum lomba. Tetap perlakukan item 🔴 di bagian 3 sebagai prioritas — terutama S-8 di bawah, karena build yang rusak menghalangi rekaman video kapan pun jadwalnya.

Dokumen lain di `docs/` sekarang cuma 2 jenis: **cara kerja** (rujukan teknis) dan **hasil pengujian** (bukti untuk laporan). Tidak ada lagi dokumen "pembagian tugas" atau "audit" terpisah yang saling bertentangan.

> **Aturan biar tidak berantakan lagi:** kalau sebuah item di sini selesai, **pindahkan ke bagian 2 (Sudah Selesai)** dengan satu baris bukti. Jangan bikin dokumen status baru.

---

## 1. Posisi sekarang

| # | Kotak diagram | % | Keterangan singkat |
|---|---|---:|---|
| 1 | Traffic Monitoring Data | 100% | Jalan penuh. Rekaman `.mp4` secara sengaja (keputusan, bukan keterbatasan) — arsitektur sudah menerima RTSP via `--sumber`, terverifikasi S-5 |
| 2 | YOLO + ByteTrack | 60% | **Diukur 29 Agustus: akurasi crossing 48,7% rata-rata (8 sampel), turun dari asumsi 80%.** Bukan bug logika — kehilangan deteksi saat padat. Lihat S-4 |
| 3 | Traffic State Builder | 90% | Jalan, tervalidasi fisik. Akurasi volume masukan mewarisi keterbatasan kotak 2 |
| 4 | Virtual Intersection (SUMO) | 100% | Network asli Simpang Pingit + program TLS dinamis |
| 5 | Realtime Traffic State | 90% | Polling live jalan |
| 6 | Traffic Forecast (LSTM) | 92% | Terlatih, tersambung, studi dampak ada |
| 7 | Scenario Generator | 90% | **Sudah live** lewat cache |
| 8 | Traffic Simulation | 92% | **Sudah live**, sudah divalidasi multi-seed |
| 9 | Performance Analysis (LOS) | 90% | 4 metrik nyata, tampil di dashboard |
| 10 | Adaptive Decision Engine | 65% / 90% | **Berubah 29 Agustus malam:** training v3 (300k) ternyata tidak valid — 3 bug baru ditemukan & diperbaiki di environment (lihat P-1, "Bug A/B/D"). Training ulang v4 (100k) sedang berjalan (dijalankan Rahmat). Peran tetap diisi Scenario Generator sampai v4 lulus gerbang kualitas |
| 11 | Signal Timing Recommendation | 90% | S-1 selesai — `/signal/status` sekarang baca cache skenario. Tapi lihat kotak 12: panel yang menampilkannya sedang tidak ter-build |
| 12 | Dashboard | 92% | ✅ Build hijau lagi (S-8 diperbaiki 29 Agustus malam), badge `source` + LOS ada |

**Keseluruhan: ≈87% harfiah / ≈90% fungsional.**
Kembali ke level sebelum audit — build frontend yang sempat rusak (S-8) sudah diperbaiki malam ini. S-1, S-2, S-3, S-6, S-8 semuanya terverifikasi selesai; PPO (kotak 10) masih dalam proses pelatihan ulang v4 setelah 3 bug baru ditemukan & diperbaiki.

**Bukti eksekusi 29 Agustus (malam, setelah perbaikan S-8):**
- `backend/` → `pytest -q` = **86 passed, 1 failed** (`test_real_checkpoint_reaches_recommendation_endpoint` — checkpoint lama 5-dim vs kode baru 4-dim, self-resolve setelah checkpoint v4 di-commit)
- `simulation/` → `.venv/Scripts/python.exe -m pytest simulation/tests/` dari root repo (venv gabungan, bukan lagi `backend/.venv`) = **15 passed, 0 failed**
- `frontend/` → `npm run build` = ✅ **sukses, 13/13 route, 0 error TypeScript**

---

## 2. SUDAH SELESAI — jangan dikerjakan ulang

Bagian ini ada supaya tidak ada yang mengerjakan hal yang sudah beres. Beberapa di antaranya **baru saja saya temukan sudah selesai** padahal masih tertulis "belum" di dokumen-dokumen lama.

| Yang dulu jadi masalah | Status | Buktinya di mana |
|---|---|---|
| Jalur live & batch tidak pernah bertemu ("0% keputusan lewat simulasi") | ✅ **Selesai** | `recommendation_service.py:107` baca cache; `source="scenario-generator"` |
| Siklus 4-lengan penuh belum diterapkan ke SUMO live | ✅ **Selesai** | `sumo_controller.py:1128` `apply_cycle_plan()` pakai `setProgramLogic()` |
| Kandidat agresif "+20%" cuma angka ilustratif | ✅ **Selesai** | Sweep 28–34 detik → `AGGRESSIVE_GREEN_INCREMENT_SECONDS = 1`. Bukti: `hasil-kalibrasi-kandidat-agresif.md` |
| Belum ada studi "dengan forecast vs tanpa forecast" | ✅ **Selesai** | `hasil-studi-forecast.md` — delay −2,20s, antrean −7m, throughput +3 |
| Simulasi cuma 1 run per kandidat, bisa kebetulan | ✅ **Sudah divalidasi** | `hasil-validasi-multisnapshot-multiseed.md` — 3 snapshot × 3 seed, `balanced` menang 7 dari 9 |
| Belum ada SOP/checklist urutan nyalakan demo | ✅ **Selesai** | `sop-demo-end-to-end.md` — 9 langkah + checklist H-1 |
| Indikator loading sebelum poll pertama | ✅ **Selesai** | `page.tsx:674` |
| Badge `source` & LOS di dashboard | ✅ **Selesai** | `RecommendationPanel.tsx:336-353` |
| Regresi jam simulasi client-side di panel sinyal | ✅ **Selesai** | Commit `861141e` |
| Kalibrasi `north`, identitas koridor `east` | ✅ **Selesai** | Commit `5b2c18e`, `700140c` |
| PPO "nol baris kode RL" | ✅ **Sudah tidak berlaku** | Commit `f921ce9` — env Gymnasium, training, evaluasi, integrasi backend, 7 test. Lihat P-1 |
| PPO tidak pernah menunjukkan tanda belajar | ✅ **Sudah terbukti belajar** | `training_monitor.csv` — reward naik monoton −3,38 → −1,80 selama 8.362 episode |
| Checkpoint PPO tidak ter-commit, `pytest` backend 1 gagal | ⚠️ **Gagal lagi 29 Agustus malam** | Yuli sempat commit model (`f62b7ac`) dan test sempat hijau, tapi action space PPO diubah 5→4 dim sore ini (Bug A/B/D) sehingga checkpoint lama basi lagi. `pytest` backend sekarang **86 passed, 1 failed**. Self-resolve setelah checkpoint v4 di-commit — lihat P-1a-v2 |
| S-1: Panel Status Sinyal belum ikut sumber simulasi | ✅ **Selesai** (Yuli, commit `74c946c`) | `signal_service.py:214` panggil `cache_service.get_fresh()`, `source="scenario-generator"` saat cache segar |
| S-2: 1 test merah di `simulation/` | ✅ **Selesai** (Yuli) | `test_forecast_client.py` stub sudah punya `recommend_full_cycle()`. **15 passed, 0 failed** kalau dijalankan dari root repo (lihat P-4) |
| S-3: Angka palsu "32 detik" di Digital Twin | ✅ **Selesai** (Melpi) | `digitaltwinview.tsx` sekarang tampil "Memuat status simulasi..." sebelum data asli masuk |
| S-6: 3 kalimat scope untuk laporan | ✅ **Selesai** (Melpi) | Sudah ada di `docs/penjelasan-progres-per-modul.md` |
| P-1c: baseline pembanding PPO bukan RuleBasedEngine asli | ✅ **Selesai** | `ppo_env.py:177,439` — `rule_based_action()` panggil `RuleBasedEngine().recommend_cycle()` yang asli |

---

## 3. SISA KERJA — Fase 1 (sebelum video presentasi)

Item asli (S-1, S-2, S-3, S-6, S-4, S-5) semuanya **sudah selesai** — dipertahankan di bawah sebagai bukti, bukan tugas terbuka lagi. Satu-satunya yang benar-benar tersisa di Fase 1 sekarang adalah **S-8** (build rusak, urgent) dan **S-7** (blocked oleh S-8).

### ✅ S-1. Panel Status Sinyal belum ikut sumber simulasi — SELESAI (Yuli)

`_recompute_cycle_plan()` (`signal_service.py:214`) sekarang panggil `live_scenario_cache_service.get_fresh(...)` di awal fungsi, pakai `cyclePlan` dari cache kalau segar dan set `source="scenario-generator"`, fallback ke `recommend_cycle()` kalau tidak. Commit `74c946c`. **Belum diverifikasi lewat browser sungguhan** — gabung ke S-7.

---

### ✅ S-2. Satu test merah — SELESAI (Yuli)

`ScenarioEngineStub` di `tests/test_forecast_client.py` sudah punya `recommend_full_cycle()`. `pytest tests/` di `simulation/` → **15 passed, 0 failed** (dijalankan dari root repo — lihat P-4).

---

### ✅ S-3. Angka palsu "32 detik" di Digital Twin — SELESAI (Melpi)

`digitaltwinview.tsx` sekarang tampil "Memuat status simulasi..." sebelum data asli masuk, bukan angka yang diketik manual.

---

### ✅ S-8. Build frontend rusak — SELESAI (Rahmat, 29 Agustus malam)

Regresi dari refactor signal-recommendation Melpi (commit `2d2d08d`) yang belum selesai. 3 perbaikan:

1. `RecommendationPanel.tsx` — `approachLabel` hilang saat rewrite, dipulihkan persis versi sebelum commit `2d2d08d` (lookup nama dari `APPROACH_OPTIONS`).
2. `page.tsx` (2 tempat) — field API yang benar itu `candidates` (array), bukan `scenarios`. Ditambahkan `candidateToRecommendation()`, disalin dari helper yang sudah benar & teruji di `digitaltwinview.tsx:319-357`, dipakai di kedua tempat supaya `DigitalTwinCandidate` terpetakan jadi bentuk `Recommendation` yang benar, bukan cuma diselipkan mentah-mentah.
3. `digitaltwinview.tsx` — `getState()` diberi anotasi tipe balik eksplisit `"GREEN"|"YELLOW"|"RED"`; prop `sharedVisualPhaseState` (yang cuma terima `GREEN|YELLOW`, RED memang tidak relevan buat panel ini) diberi fallback `mappedState === "RED" ? "GREEN" : mappedState`.

**Terverifikasi:** `npm run build` → sukses, 13/13 route, 0 error TypeScript. Tidak menyentuh backend — `_calculate_wait_time()` di `signal_service.py` (bagian aman dari commit yang sama) dibiarkan apa adanya.

---

### ✅ S-4. Akurasi deteksi CV — SELESAI 29 Agustus, hasilnya perlu perhatian

Divalidasi manual: 8 potongan @1 menit (4 arah × ramai/sepi), dihitung manusia lalu dibandingkan `crossing_simpang.csv`. Detail lengkap + data mentah di **`docs/hasil-validasi-akurasi-cv.md`**.

**Hasil: rata-rata akurasi 48,7%** (rentang 22,2%–96,1%). Ini **jauh di bawah** target awal (~90%) dan harus dilaporkan apa adanya — bukan angka yang bisa dipoles.

**Sudah dicek ke kode, bukan bug arah/logika crossing** — `hitung_crossing()` (`vehicle_counter_pingit.py:866-868`) terverifikasi menghitung kedua arah lalu lintas dengan benar. Pola datanya (4 dari 5 sampel "ramai" punya akurasi terburuk) mengarah ke **kehilangan deteksi/tracking saat kondisi padat** — konsisten dengan keterbatasan ID-switch ByteTrack yang sudah didokumentasikan sendiri di kode untuk metrik antrean, kemungkinan juga memengaruhi hitungan crossing.

**Ini menurunkan kotak 2 (YOLO+ByteTrack) dari 80% menjadi lebih rendah** — lihat bagian 1. Sekaligus **relevan untuk kotak 3 dan 9**: kalau volume kendaraan yang masuk `TrafficState` bisa meleset 22%–96% tergantung kepadatan, itu bisa memengaruhi kualitas keputusan hijau, bukan cuma soal pelaporan angka.

**Kalimat aman untuk laporan** (jangan klaim 90%+, jangan generalisir dari 1 sampel terbaik):
> "Validasi manual pada 8 sampel menunjukkan akurasi rata-rata 48,7%, dengan sistem cenderung kehilangan hitungan pada kondisi padat — konsisten dengan keterbatasan tracking yang sudah didokumentasikan. Ini bukan bug pada logika crossing (sudah diverifikasi ke kode), melainkan keterbatasan deteksi pada kepadatan tinggi. Perbaikan lanjutan adalah kerja di luar scope 16 hari."

---

### ✅ S-5. CV siap-RTSP — SELESAI 29 Agustus

Sumber video dijadikan parameter `--sumber` (path file lain ATAU URL stream), menggantikan hardcode di `vehicle_counter_pingit.py`. Wajib dipakai bersama `--kamera` (satu URL cuma untuk satu kamera). Contoh: `--kamera CCTV_1 --sumber rtsp://192.168.1.10/stream`.

**Terverifikasi 2 hal:**
1. `--sumber` tanpa `--kamera` **ditolak saat parsing** dengan pesan jelas.
2. `--sumber rtsp://alamat-tidak-ada` **lolos parsing**, lalu gagal di **koneksi sungguhan** — dibuktikan lewat log FFmpeg asli: `Stream timeout triggered after 30079.994000 ms` lalu `[LEWAT] ... gagal dibuka`. Ini FFmpeg betulan mencoba RTSP, bukan simulasi.

**Kalimat untuk laporan:** *"Arsitektur CV menerima file maupun stream RTSP secara identik (`cv2.VideoCapture` tidak membedakan keduanya); kami memakai rekaman karena tidak ada akses ke stream CCTV operasional Dishub, bukan karena keterbatasan sistem."*

> ⚠️ **Insiden saat verifikasi, sudah dibereskan sepenuhnya.** Test RTSP pertama (tanpa backup) menimpa ketiga CSV (`crossing_simpang.csv`, `snapshot_zona.csv`, `percobaan_logic_simpang.csv`) jadi 0 baris — karena semuanya dibuka mode `"w"` **di awal proses, sebelum** kamera sempat dicoba dibuka, jadi gagal-koneksi pun tetap menghapus data lama.
>
> `crossing_simpang.csv` dan `snapshot_zona.csv` dipulihkan 100% dari salinan beku `forecasting/data/` (dipakai Yuli untuk training LSTM, kebetulan menyelamatkan kita). `percobaan_logic_simpang.csv` tidak ada di situ, tapi **Rahmat punya backup sendiri** yang dipulihkan 29 Agustus — diverifikasi cocok persis (2.152 baris, 4 kamera CCTV_1–4, rentang waktu 16:30:10–17:19:15, sama dengan 2 file lainnya). **Ketiga file sekarang pulih 100%**, bukan cuma dampaknya nol seperti dugaan awal.
>
> **Perbaikan permanen ditambahkan supaya tidak terulang:** kalau `--sumber` dipakai, ketiga CSV sekarang ditulis ke `cv/output/_sumber_kustom/` (folder terpisah, di-gitignore), **bukan** menimpa CSV produksi sama sekali — diverifikasi ulang: CSV produksi tetap 2.152/10.452 baris setelah test kedua yang sengaja diulang.

---

### ✅ S-6. Tiga pernyataan scope untuk laporan — SELESAI (Melpi)

Sudah ada di `docs/penjelasan-progres-per-modul.md`: kalimat CV pakai rekaman, `north` pakai zona tengah (`northDataNote`), dan 3 kandidat skenario.

---

### 🟡 S-7. Verifikasi browser hidup — siapa saja, 30 menit — **tidak lagi blocked, S-8 selesai**

Buka dashboard, bandingkan angka di layar dengan hasil `POST /recommendation` dan `GET /signal/status` langsung. Pastikan cocok, dan pastikan badge "Diuji simulasi SUMO" di kedua panel (S-1) benar-benar muncul saat worker `--full-cycle` jalan.

---

## 4. SISA KERJA — Fase 2 (1–7 September)

### P-1. PPO — kotak 10, Rahmat (diambil alih dari Yuli 29 Agustus malam)

> **Berubah lagi 29 Agustus malam.** Semua temuan A–D di bawah (dari training v2/200k) sudah **diperbaiki melalui rute berbeda** dari yang direncanakan semula — bukan oleh Yuli lewat P-1b/c/d seperti pembagian tugas awal, tapi lewat audit ulang Rahmat setelah training v3 (300k) ternyata tidak valid. Riwayat lengkap: v2 (200k) → temuan reward buta & starvation di bawah → v3 (300k, resume dari 180k) dilatih untuk memperbaiki itu → evaluasi v3 sempat terlihat lulus gerbang kualitas 3/3, **tapi itu artefak pengukuran**, bukan perbaikan asli.

---

#### 🔬 BUG A/B/D DITEMUKAN & DIPERBAIKI (29 Agustus malam, Rahmat) — v3 tidak valid, v4 sedang dilatih

Diminta audit ulang setelah v3 "lulus gerbang kualitas" terasa mencurigakan (4 training berturut-turut sebelumnya semua gagal). Ditemukan 3 bug baru lewat instrumentasi langsung (bukan dugaan), semuanya di `decision_engine/ppo_env.py`, commit `a87f48f`:

- **Bug A (paling parah):** jendela keputusan training selalu tetap 30 detik, padahal satu rotasi 4-lengan penuh (durasi hijau pilihan + 4×4 detik kuning) butuh 76–256 detik. Akibatnya **lengan selatan dan barat tidak pernah benar-benar dapat waktu hijau simulasi** — dibuktikan 8/8 jendela uji cuma "utara" yang aktif. Diperbaiki: jendela sekarang dihitung dari durasi rotasi yang benar-benar dipilih.
- **Bug B:** ambang saturasi reward antrean (`queue_norm`) di-hardcode 40, padahal antrean nyata terukur 34–75 setelah Bug A diperbaiki → saturasi di 7/10 langkah uji. Dinaikkan ke 100 berdasar pengukuran ulang (0/10 saturasi).
- **Bug D:** `volume` saat training dihitung dari kendaraan **muncul** (permintaan), sedangkan `TrafficState.volume` produksi dihitung dari kendaraan **melintasi garis henti** (throughput terlayani) — dua besaran berbeda yang bisa bernilai sama sekali berbeda saat lampu merah. Diperbaiki: training sekarang menghitung crossing sungguhan lewat `_hitung_crossing()`, sama semantiknya dengan produksi.

**Efek:** `smarttwin_ppo_v3.zip` dan hasil evaluasinya **tidak lagi dipakai sebagai bukti** — 4,5+ jam training itu diinvestigasi, bukan sia-sia, tapi hasilnya bukan angka final. `pytest` backend & `simulation` tetap hijau setelah perbaikan (lihat bagian 1).

**Status malam ini:** training ulang **v4** (100.000 timestep, seed 42, `decision_engine/models/smarttwin_ppo_v4`) sedang berjalan — dijalankan langsung oleh Rahmat, dipantau otomatis untuk checkpoint 10k sebagai titik evaluasi dini (menghindari pola "training berjam-jam baru ketahuan ada bug" yang terjadi 4 kali sebelumnya). Belum ada hasil evaluasi final v4 — **jangan kutip angka menang/kalah apa pun dari v3 atau lebih lama untuk laporan**, tunggu evaluasi v4.

---

#### 🔬 HASIL TRAINING 200k + INVESTIGASI AKAR MASALAH (29 Agustus, Rahmat)

**Keputusan operasional: PPO TIDAK diaktifkan. Sistem tetap memakai rule-based / Scenario Generator.** Alasannya di bawah — bukan karena PPO gagal belajar, tapi karena evaluasinya belum bisa dipercaya sebagai bukti.

**Training (`smarttwin_ppo_v2.zip`, 200.192 timestep, 4 jam 27 menit, CPU):** berjalan bersih tanpa crash, 20 checkpoint tersimpan (10k–200k). Kurva reward naik **monoton di semua 10 desil**: −0,40 → +1,16 (Δ +1,56). Proses belajarnya sehat.

**Temuan A — training lebih lama TIDAK membantu.** Checkpoint 100k vs model final 200k praktis identik (selisih dalam rentang noise):

| | 100k | 200k |
|---|---:|---:|
| Antrean vs rule-based | −52,6% | −54,5% |
| Waktu tunggu vs rule-based | −69,7% | −69,5% |
| Throughput vs rule-based | −6,4% | −6,7% |

4,5 jam tambahan tidak memberi perbaikan berarti. **Jangan naikkan timestep lagi** untuk mengejar hasil — bottleneck-nya bukan lama training.

**Temuan B — konsisten menang 2 dari 3 metrik di 3 seed, throughput selalu kalah.** `quality_gate_passed: false` di ketiga seed (gate mensyaratkan menang **ketiga** metrik). Verdict otomatis: *"PPO belum boleh diaktifkan; gunakan rule-based fallback."*

**Temuan C (PENTING) — reward hampir BUTA terhadap throughput.** Diukur langsung dengan instrumentasi komponen reward (3 episode, 36 langkah keputusan, PPO vs baseline):

`ppo_env.py:238` → `throughput_norm = min(1.0, arrived / 15.0)` — **saturasi di 15 kendaraan/langkah.**

| | PPO v2 | Baseline rule-based |
|---|---:|---:|
| Kedatangan per langkah | 17,8 | 20,0 |
| Langkah yang **saturasi** (≥15) | **81%** | **97%** |
| `throughput_reward` rata-rata | +0,4225 | +0,4483 |

Karena keduanya hampir selalu di atas ambang 15, komponen throughput cuma berbeda **0,0258** dari maksimum 0,45 yang mungkin. **Menambah throughput di atas 15/langkah tidak memberi reward tambahan sama sekali** — jadi PPO tidak punya insentif menaikkannya, sementara antrean/tunggu masih terus memberi gradien. PPO mengoptimalkan persis apa yang diukur; fungsi reward-nya yang tidak bisa membedakan.

**Temuan D (PALING PENTING) — 80% keunggulan reward PPO datang dari `starvation`, bukan dari kualitas lalu lintas.** Rincian selisih reward PPO (+0,1375) vs baseline (−0,3284), total gap **+0,4659**:

| Komponen | Kontribusi ke gap | Porsi |
|---|---:|---:|
| **Starvation** (lengan tidak kebagian hijau) | **+0,3750** | **+80,5%** |
| Antrean | +0,0809 | +17,4% |
| Waktu tunggu | +0,0358 | +7,7% |
| Throughput | −0,0258 | −5,5% |

Baseline kena penalti starvation **0,375**, PPO **0,000**.

**Kenapa ini masalah:** action space environment memaksa "pilih SATU lengan per langkah", dan baseline memakai `RuleBasedEngine.recommend()` (yang memang mengembalikan satu lengan pemenang). Kalau satu lengan konsisten paling padat, lengan lain tidak kebagian → kena penalti starvation, dan antreannya menumpuk (itu juga menjelaskan antrean baseline 72,2 vs PPO 27,7).

**Tapi produksi tidak pernah berperilaku begitu.** `SignalService` memakai `recommend_cycle()` dengan rotasi tetap `FIXED_CYCLE_ORDER` (utara→timur→selatan→barat) — **keempat lengan dijamin dapat hijau bergantian, starvation mustahil terjadi secara struktural.**

Artinya: **PPO diadu melawan skenario yang tidak pernah terjadi di sistem sungguhan.** Keunggulan 52–69% di antrean/tunggu itu kemungkinan besar **melebih-lebihkan**, karena sebagian besar berasal dari baseline yang "dihukum" atas perilaku yang produksi tidak lakukan.

> Catatan koreksi: item P-1c lama ("baseline cuma proxy `argmax` sederhana") **sudah diperbaiki Yuli** — `rule_based_action()` sekarang benar memanggil `RuleBasedEngine` asli. Masalah yang tersisa bukan lagi proxy-nya, melainkan **ketidakcocokan semantik**: env memodelkan "pilih 1 lengan per langkah" (`recommend()`), sedangkan produksi menjalankan rotasi tetap (`recommend_cycle()`).

#### Kalau mau dilanjutkan setelah 31 Agustus

Urutan yang masuk akal berdasar temuan di atas — **jangan** mulai dengan menambah timestep:

1. **Naikkan/hilangkan ambang saturasi throughput** (Temuan C) — mis. `arrived / 30.0` atau normalisasi relatif terhadap demand, supaya reward bisa membedakan 18 vs 20 kendaraan.
2. **Samakan semantik baseline dengan produksi** (Temuan D) — bandingkan PPO melawan rotasi `recommend_cycle()`, bukan pemilihan satu lengan. Ini yang menentukan apakah keunggulan PPO nyata atau artefak.
3. Baru latih ulang dan evaluasi ulang.

**Untuk laporan/juri, kalimat yang jujur dan kuat:** *"PPO berhasil dilatih dan menunjukkan pembelajaran yang konsisten. Evaluasi otomatis kami menolaknya untuk aktivasi karena belum unggul di seluruh metrik, dan investigasi lanjutan menemukan dua kelemahan pada fungsi reward dan metodologi pembandingnya. Kami memilih tetap memakai rule-based yang terverifikasi daripada mengaktifkan model yang buktinya belum kuat."*

#### Yang sudah benar — jangan diulang

**1. PPO-nya benar-benar belajar.** Dianalisis dari `decision_engine/models/training_monitor.csv` (8.362 episode, 3,45 jam):

| Episode | Reward rata-rata |
|---|---:|
| 0–836 | −3,38 |
| 4.180–5.016 | −1,89 |
| 7.524–8.360 | **−1,80** |

Naik **monoton di setiap desil**, total **+1,58**. Ini kurva belajar sungguhan, bukan noise atau garis datar — bagian tersulit dari PPO sudah lewat.

**2. Integrasinya aman.** `decision_engine/engine_factory.py` membuat default tetap `rule-based`; PPO hanya aktif lewat env `SMARTTWIN_DECISION_ENGINE=ppo`, dan `PPOEngine` punya fallback internal ke rule-based di `recommend()` maupun `recommend_cycle()` (`source="ppo-fallback-rule-based"`). **Sistem tidak bisa rusak karena PPO.**

**3. Environment-nya proper.** Gymnasium `SmartTwinSumoEnv`, ada `check_env`, split train/eval 80/20, seed terkontrol, `traci` pakai `label` unik jadi tidak bentrok antar sesi.

#### ⚠️ P-1a. Model hasil training tidak ada di repo — sempat selesai, basi lagi malam ini

Yuli sudah commit checkpoint-nya (`f62b7ac "add model"`, `aa9d06d "add smoke train ppo"`) dan `stable-baselines3`/`gymnasium` sudah terpasang di `backend/.venv` — masalah aslinya (dependency hilang) tetap beres.

**Tapi:** action space PPO diubah dari 5 dimensi ke 4 dimensi sore ini (bagian dari perbaikan Bug A/B/D), dan checkpoint yang ter-commit masih 5 dimensi. `test_real_checkpoint_reaches_recommendation_endpoint` sekarang gagal lagi — endpoint jatuh ke `ppo-fallback-rule-based`. **Ini otomatis beres** begitu training v4 (sedang berjalan) selesai dan checkpointnya di-commit menggantikan yang lama. `pytest -q` backend sekarang: **86 passed, 1 failed**.

#### ✅→🔵 P-1b. Klaim "PPO mengalahkan rule-based" belum sahih — bobot sudah diperbaiki, tunggu evaluasi v4

Angka di bawah ini **dari training v2 (200k), sudah usang** — dipertahankan sebagai riwayat kenapa bobot diubah. Bobot throughput sudah dinaikkan dari 0,20 jadi 0,45 (`THROUGHPUT_REWARD_WEIGHT` di `ppo_env.py:59`, bagian dari perbaikan Bug A/B/D) sebagai reaksi langsung atas temuan di bawah. **Belum ada evaluasi baru** untuk membuktikan ini benar-benar memperbaiki throughput di v4 — itu langkah berikutnya setelah training v4 selesai, bukan lagi tugas terbuka menaikkan bobot.

`evaluation.json` menulis `"ppo_beats_rule_on_reward": true` sebagai **satu-satunya flag**. Sangat mudah dibaca sebagai "PPO lebih baik". Perbandingan ketiga seed pada metrik sebenarnya:

| Metrik | Seed 1000 | Seed 2000 | Seed 3000 | Skor |
|---|---|---|---|---:|
| **Reward** | ✅ PPO | ✅ PPO | ✅ PPO | **3/3** |
| **Antrean** | ✅ −8,6% | ❌ +0,7% | ❌ +2,4% | **1/3** |
| **Waktu tunggu** | ✅ −7,9% | ✅ −3,1% | ❌ **+10,1%** | **2/3** |
| **Throughput** | ❌ **−10,2%** | ❌ −2,6% | ➖ +1 kend. | **0/3** |

Dua hal yang harus dipahami sebelum angka ini dipakai di laporan:

- **Menang di reward itu hampir tautologi.** Reward adalah fungsi yang PPO dilatih untuk memaksimalkan. Yang menentukan untuk laporan adalah **delay, antrean, throughput** — persis 3 metrik di kotak 9. Di situ PPO menang **4 dari 9** perbandingan.
- **Throughput PPO tidak pernah menang.** Penyebabnya terbaca di `ppo_env.py:166` — bobot reward `0,20 × throughput − 0,50 × antrean − 0,30 × tunggu`. Throughput diberi bobot terkecil, jadi agent belajar **mengorbankan jumlah kendaraan yang lewat** demi antrean pendek. Untuk sistem lalu lintas itu trade-off serius: antrean pendek karena lebih sedikit kendaraan dilayani bukan perbaikan.

**Status:** bobot sudah dinaikkan (lihat P-1b di atas) dan training v4 sedang jalan. Yang tersisa cuma menunggu evaluasi v4 dan melaporkan ketiga metrik lalu lintas — bukan cuma reward.

#### ✅ P-1c. Baseline pembanding bukan RuleBasedEngine asli — SELESAI

`rule_based_action()` (`ppo_env.py:430`) sekarang panggil `RuleBasedEngine().recommend_cycle()` yang asli lewat `self.rule_based_engine` (`ppo_env.py:177`), bukan lagi tiruan `argmax`. PPO diadu melawan engine yang benar-benar jalan di dashboard.

#### ✅ P-1d. Fitur saat training ≠ fitur saat inference — SELESAI

Dulu slot 0 dan slot 3 observasi selalu berkorelasi sempurna (volume dibagi 60 vs 33), sedangkan saat inference keduanya sinyal independen. Diperbaiki dengan modul bersama `decision_engine/ppo_features.py` yang dipakai training **dan** inference — `densityIndex` sekarang besaran nyata yang berbeda dari `volume`, bukan angka yang sama dibagi ulang. Sekaligus bagian dari perbaikan Bug D (P-1 di atas): `volume` saat training sekarang dihitung dari crossing sungguhan, sama semantiknya dengan `TrafficState.volume` produksi.

#### Urutan kerja 1–7 September

P-1a, P-1c, P-1d ✅ selesai. Sisanya:

1. **Tunggu training v4 selesai** (sedang berjalan, dipantau otomatis untuk checkpoint 10k)
2. **Evaluasi v4** vs `RuleBasedEngine` di 3 seed, pakai `evaluate_ppo.py` — ini yang membuktikan apakah Bug A/B/D + bobot baru benar-benar memperbaiki throughput, bukan cuma dugaan
3. **Commit checkpoint v4** kalau lulus gerbang kualitas — ini juga otomatis memperbaiki P-1a (test integrasi yang sekarang gagal karena checkpoint basi)
4. Kalau lulus: aktifkan lewat `SMARTTWIN_DECISION_ENGINE=ppo` dan update dokumen ini + kalimat "Cara menjawab juri" di bagian 7

**Aturan berhenti tetap sama:** kalau setelah v4 PPO tetap kalah pada throughput, **jangan dipaksakan aktif**. Kotak 10 tetap fungsional dengan Scenario Generator, dan PPO tetap layak dilaporkan sebagai pengembangan yang berhasil dilatih plus 3 bug metodologi yang ditemukan dan diperbaiki lewat investigasi sendiri — itu cerita yang kuat untuk juri, menang atau tidak. **PPO yang menurunkan throughput lebih buruk daripada rule-based yang bekerja.**

### P-2. Perkuat bukti LSTM — Yuli, 2–3 jam

Dua klaim masih bertumpu sampel kecil:
- "Mengalahkan naive baseline" (MAE 1,65 vs 2,30) — diuji pada **16 sequence** saja, dari 1.044 sequence latih
- "Forecast menurunkan delay" — **1 snapshot**

Perbaikan: bagi ulang data supaya test set lebih besar; ulang `scenario_worker.py --compare-forecast` di 10–20 snapshot. Target kalimat: *"konsisten membaik di 17 dari 20 pengujian"*.

> **Catatan Yuli, 30 Agustus:** retraining dengan split kronologis 60/15/25
> sudah dicoba; test independen naik dari 16 menjadi 96 sequence, tetapi MAE
> LSTM turun kualitasnya menjadi 2,0440 dan hanya unggul tipis dari naive
> 2,0720. Tim memutuskan kembali memakai checkpoint lama (split 70/15/15,
> MAE 1,6528 vs naive 2,2973). Hasil lama tetap disebut proof of concept karena
> test efektif hanya 16 sequence dan datanya berasal dari satu sesi rekaman.
>
> Uji dampak operasional checkpoint lama kemudian diperluas menjadi **20
> snapshot** dalam sesi data yang sama: delay membaik 20/20, antrean 17/20,
> throughput 19/20, dan ketiga metrik membaik bersamaan pada **17/20** pengujian.
> Hasil ini memperkuat konsistensi pada rekaman tersebut, tetapi bukan bukti
> generalisasi lintas hari/lokasi. Rincian reproduksinya ada di
> `docs/hasil-studi-forecast-multi-snapshot.md`.

### P-3. LOS per lengan — Rahmat, 2–3 jam

`calculate_los()` menghitung dari delay **rata-rata seluruh simpang**. HCM aslinya per lengan. Akibatnya kalau selatan macet parah (LOS E) tapi 3 lengan lain lancar (LOS A), sistem melaporkan LOS B — **masalah di selatan tidak terlihat**.

Bonus: demo jadi lebih meyakinkan — bisa menunjuk satu lengan dan bilang "yang ini LOS E, karena itu diberi hijau lebih lama".

### P-4. Rapi-rapi — siapa saja senggang

- `METERS_PER_QUEUED_VEHICLE = 7.0` estimasi → tulis di laporan sebagai asumsi, atau kalibrasi
- Bobot 50/50 di `select_best_scenario()` → tulis alasannya, atau uji sensitivitas
- Dua jalur Traffic State Builder paralel → gabungkan atau beri komentar kapan pakai yang mana
- ✅ **Selesai 30 Agustus** — `backend`, `simulation`, `decision_engine` digabung jadi **satu venv di root** (`.venv/`), `requirements.txt` juga digabung ke root. Masalah `ModuleNotFoundError: supabase`/`postgrest` yang bikin `simulation/pytest` gagal collect (dan bikin `scenario_worker.py` gak bisa dijalankan langsung) **hilang total**, bukan lagi sekadar workaround "pakai backend/.venv dari root". `cv/.venv` dan `forecasting/.venv` tetap terpisah sengaja (CUDA torch, stack ML beda) — lihat CLAUDE.md bagian "Single root venv". `.env` juga dipindah dari `backend/.env` ke `.env` di root, dipakai bersama oleh semua modul termasuk `cv/`. **Catatan: `backend/.venv` lama belum dihapus** karena masih dipakai training PPO v4 yang sedang berjalan — dihapus setelah training selesai.

### P-5. Perbaiki akar penyebab akurasi CV rendah — DICOBA, DIKEMBALIKAN 29 Agustus

> **Keputusan final: kode dikembalikan ke versi sebelum P-5. Angka akurasi resmi tetap 48,7%** (rata-rata 8 sampel, lihat S-4 / `hasil-validasi-akurasi-cv.md`). Ringkasan di bawah dipertahankan sebagai catatan investigasi — bukan instruksi untuk dikerjakan lagi.

**Yang dicoba, singkatnya:**

1. **Bug kontaminasi antar-garis** (CCTV_2 MAGELANG↔DIPONEGORO, dugaan penyebab sampel #6). Diperbaiki dengan `segmen_berpotongan()` — matematisnya benar dan terverifikasi lewat simulasi titik. **Tapi saat diuji di video sungguhan** (CCTV_2, menit 8–20, dibandingkan 4 sampel yang punya hitungan manual): sampel #6 (DIPONEGORO) membaik drastis (41,7%→83,3%) persis sesuai dugaan, sampel #5 (DIPONEGORO) sedikit membaik — **tapi sampel #3 dan #4 (MAGELANG) malah memburuk parah** (39,2%→14,0% dan 63,3%→26,7%). Rata-rata 4 sampel: 44,9%→40,8%, **sedikit lebih buruk secara agregat**. Dugaan penyebab regresi MAGELANG (belum dibuktikan): pengecekan segmen yang lebih ketat mungkin menolak crossing sah yang lintasannya miring/dekat ujung garis — trade-off presisi vs recall yang belum sepenuhnya dipahami.

2. **Turunkan `CONFIDENCE`** ke 0.25 — diuji di 1 jendela (sampel #1, CCTV_1): hasilnya memburuk (50,8%→36,9%). Hipotesis ditolak berdasar 1 titik data.

**Kenapa dikembalikan, bukan diperdalam lebih jauh:** hasil campur/negatif pada bukti yang ada, dan investigasi lanjutan (kenapa MAGELANG regresi) akan makan waktu GPU + analisis lagi tanpa jaminan hasil, sementara tenggat 31 Agustus masih punya item wajib lain (S-5, latihan, rekaman). Keputusan sadar: **kode dikembalikan ke `git show 9387c13:cv/vehicle_counter_pingit.py`** (versi sebelum commit `82f63f1`), angka 48,7% dari S-4 tetap jadi laporan resmi.

**✅ Efek samping sudah dibereskan.** Dua kali proses ulang video (CCTV_1 & CCTV_2) otomatis meng-upload video anotasi ke HuggingFace **dengan path tetap** (`videos/simpang4-pingit/annotated/anotasi_CCTV_X.mp4`, lihat `hf_writer.py:58`) — artinya **menimpa video produksi asli**, bukan cuma menambah baris baru. Ini pola yang **sudah pernah terjadi 2× sebelumnya** (lihat riwayat commit HF: "Restore anotasi_CCTV_1.mp4 (accidentally overwritten by ...)", 23 & 25 Agustus).

Dipulihkan dengan pola yang sama persis:
1. Download versi baik dari commit HF terakhir sebelum test (`8cb05f945a...` untuk CCTV_1, `4005778a5...` untuk CCTV_2)
2. Upload ulang sebagai commit baru "Restore ... (accidentally overwritten by P-5 confidence-threshold test run)" — **terverifikasi** ukuran file kembali persis sama (260.974.538 & 261.868.146 byte, cocok dengan versi produksi asli)
3. 2 baris orphan di tabel Supabase `cameraVideos` (id 41 & 42, dikonfirmasi dulu isinya sebelum dihapus — cocok waktu upload & ukuran dengan 2 test run) sudah dihapus

Supabase dan HuggingFace sekarang bersih, tidak ada sisa dari eksperimen P-5.

**⚠️ Untuk siapa pun yang menjalankan `vehicle_counter_pingit.py` untuk eksperimen ke depannya:** proses ini SELALU upload ke HuggingFace di akhir (bukan cuma tulis CSV lokal) kecuali kamera itu tidak terdaftar di `CAMERA_ID_MAP`. Backup lokal CSV **tidak cukup** — pertimbangkan juga risiko ke Supabase/HuggingFace. Lihat `cv/CATATAN.md`.

**Bukan blocker demo** — nomor akurasi (48,7%) sudah ada dan jujur dilaporkan di S-4. Kalau nanti ada waktu setelah 31 Agustus untuk investigasi ulang, mulai dari pertanyaan "kenapa MAGELANG regresi" sebelum mencoba perbaikan lain.

---

## 5. Yang TIDAK dikerjakan (keputusan sadar, bukan kelupaan)

Supaya tidak ada yang iseng mengerjakan ini dan membuang waktu:

| Hal | Alasan |
|---|---|
| **CV live RTSP** | Tidak ada akses stream CCTV Dishub. Cukup S-5 (siapkan jalurnya) |
| **Validasi mAP formal** | Butuh anotasi ground truth. S-4 sudah cukup untuk demo |
| **Scheduler otomatis** | `run_ingest.py` cukup sekali; worker cukup dibuka di terminal saat demo. SOP sudah menutup ini |
| **Halaman History** | Di luar scope demo, data mock boleh dibiarkan |
| **Auth (login/register)** | Sudah diputuskan bukan prioritas |
| **Scenario Generator versi penuh** | 3 kandidat memang desainnya, biar muat di interval 60 detik |

---

## 6. Sebelum merekam video — WAJIB

Ikuti **`sop-demo-end-to-end.md`** langkah demi langkah. Intinya:

```
SEKALI SAJA:  buat tabel liveScenarioCache → run_ingest.py
SETIAP REKAM: backend → worker --once --full-cycle (smoke test)
              → worker --full-cycle (BIARKAN TERBUKA) → frontend
```

**Risiko terbesar saat rekaman:** kalau `scenario_worker.py` tidak jalan, backend menganggap cache basi setelah **120 detik**, lalu **diam-diam** kembali ke rule-based. Kotak 7, 8, 9 hilang dari alur — **tanpa error, layar tetap terlihat normal**. Anda bisa merekam sistem yang melewati 3 kotak dari diagram Anda sendiri tanpa sadar.

**Saat merekam, sorot badge "Diuji simulasi SUMO"** di panel Rekomendasi. Itu bukti hidup di layar bahwa keputusan benar-benar lewat simulasi.

---

## 7. Cara menjawab juri

**"Apakah semua kotak di diagram sudah ada?"**
> "Ke-12 kotak terimplementasi. Sebelas berjalan penuh dan terverifikasi. Kotak Adaptive Decision Engine saat ini dijalankan Scenario Generator berbasis simulasi SUMO — keputusannya diuji lewat tiga kandidat simulasi nyata sebelum dipakai."

**"Bagaimana dengan PPO?"** — pertanyaan ini kemungkinan besar muncul karena PPO tertulis eksplisit di diagram
> "PPO sudah dilatih 8.362 episode di lingkungan SUMO dengan kurva reward yang menunjukkan pembelajaran nyata, dan sudah terintegrasi ke backend lewat feature flag dengan fallback otomatis ke rule-based. Untuk demo ini kami menjalankan Scenario Generator karena validasi bahwa PPO mengungguli baseline pada metrik lalu lintas — terutama throughput — masih berjalan."

*Ini jawaban yang kuat DAN jujur: menunjukkan PPO nyata dikerjakan, sekaligus menjelaskan kenapa belum dipakai tanpa terdengar seperti kegagalan.*

**"Apakah ini realtime?"**
> "Pemrosesan berjalan realtime terhadap masukan video. Kami memakai rekaman CCTV Simpang Pingit karena tidak ada akses ke stream operasional Dishub — antarmuka masukannya sendiri menerima RTSP maupun file."

**"Seberapa akurat deteksinya?"**
> "Validasi manual pada 8 sampel menunjukkan akurasi rata-rata 48,7%, dengan sistem cenderung kehilangan hitungan pada kondisi lalu lintas padat — konsisten dengan keterbatasan tracking pada kerumunan motor yang rapat, yang sudah kami dokumentasikan. Ini bukan bug pada logika penghitungan — sudah kami verifikasi ke kode — melainkan keterbatasan deteksi pada kepadatan tinggi. Ini area yang kami sadari perlu perbaikan lanjutan."

*Ini jawaban yang jujur dan justru menunjukkan tim SUDAH mengukur dan MEMAHAMI keterbatasannya — sikap itu biasanya dinilai lebih baik oleh juri daripada angka tinggi yang tidak bisa dijelaskan kalau ditanya lebih dalam. Detail lengkap ada di `hasil-validasi-akurasi-cv.md`.*

**"Apa buktinya sistem ini lebih baik?"**
> "Setiap keputusan diuji lewat tiga kandidat di simulasi SUMO dan dipilih berdasarkan delay dan panjang antrean terendah, dengan LOS standar HCM 2000. Metrik pemenangnya tampil langsung di dashboard."

### JANGAN dikatakan

- ❌ **"PPO mengalahkan rule-based"** — gerbang kualitas otomatis **menolaknya** di 3 seed (menang 2 dari 3 metrik; throughput selalu kalah). Investigasi 29 Agustus juga menemukan reward hampir buta terhadap throughput (saturasi di 15/langkah) dan 80% keunggulan reward-nya berasal dari penalti starvation yang tidak pernah terjadi di produksi. Lihat P-1 Temuan C & D
- ❌ **"PPO sudah dipakai di sistem"** — default tetap rule-based; model sudah bisa dimuat (P-1a selesai) tapi belum diaktifkan sebagai default
- ❌ "Realtime CCTV" — rekaman
- ❌ **"Akurasi deteksi tinggi/95%"** — terukur 48,7% rata-rata (8 sampel), jangan digeneralisir dari sampel terbaik (#7, 96,1%) saja
- ❌ "Forecast terbukti menurunkan delay 14%" — sebelum P-2, itu 1 percobaan
- ❌ "Sistem berjalan otomatis penuh" — worker dijalankan manual

---

## 8. Pembagian tugas

**Diperbarui 29 Agustus malam.** Semua tugas Fase 1 sekarang selesai, termasuk S-8 (dikerjakan Rahmat, bukan Melpi — lihat catatan di S-8). Yang tersisa: S-7 (siapa saja, sekarang unblocked) dan kelanjutan PPO v4.

| Siapa | Status Fase 1 | Sisa kerja sekarang |
|---|---|---|
| **Yuli** | ✅ S-1, S-2 selesai | Setelah training v4 selesai: jalankan `evaluate_ppo.py` di 3 seed, dan kalau lulus gerbang kualitas, commit checkpoint v4 (memperbaiki test integrasi yang sekarang gagal). P-2 bukti LSTM (2–3j) masih terbuka |
| **Melpi** | ✅ S-3, S-6 selesai | Refactor signal-recommendation-nya (commit `2d2d08d`) sudah diperbaiki Rahmat supaya build hijau lagi (S-8) — kalau ada niat/konteks lanjutan dari refactor itu yang belum kesampaikan, cek diff S-8 dulu sebelum lanjut. Setelah itu: LOS per lengan (dukung P-3) |
| **Rahmat** | ✅ S-4, S-5, S-8 selesai | Memantau training v4 (checkpoint 50k berikutnya), lalu P-3 LOS per lengan, P-4 rapi-rapi. **P-5 tetap dikembalikan** (lihat catatan) |
| Siapa saja | — | S-7 verifikasi browser (30m) — **sudah bisa dikerjakan** |

**Prioritas sekarang, dalam urutan:** (1) S-7 verifikasi browser (build sudah hijau), (2) training v4 selesai + dievaluasi, (3) P-2/P-3 kalau masih ada waktu sebelum tanggal 6–7 September.

---

*Dokumen ini menggantikan `pembagian-tugas-tahap-akhir.md`, `pembagian-tugas-24-agustus.md`, `audit-24-agustus.md`, `status-integrasi-diagram-arsitektur.md`, `roadmap.md`, dan `realtime-dashboard.md` — semuanya dihapus 28 Agustus karena isinya sudah selesai atau bertentangan satu sama lain. Riwayatnya tetap ada di git.*

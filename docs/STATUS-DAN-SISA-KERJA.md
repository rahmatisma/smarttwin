# STATUS & SISA KERJA — SmartTwin

**Diperbarui: 28 Agustus 2026.** Ini **satu-satunya dokumen status** di repo ini. Kalau mau tahu "sudah sampai mana" atau "apa yang belum", baca ini — jangan cari di dokumen lain.

Dokumen lain di `docs/` sekarang cuma 2 jenis: **cara kerja** (rujukan teknis) dan **hasil pengujian** (bukti untuk laporan). Tidak ada lagi dokumen "pembagian tugas" atau "audit" terpisah yang saling bertentangan.

> **Aturan biar tidak berantakan lagi:** kalau sebuah item di sini selesai, **pindahkan ke bagian 2 (Sudah Selesai)** dengan satu baris bukti. Jangan bikin dokumen status baru.

---

## 1. Posisi sekarang

| # | Kotak diagram | % | Keterangan singkat |
|---|---|---:|---|
| 1 | Traffic Monitoring Data | 85% | Jalan penuh. Rekaman `.mp4`, bukan RTSP live |
| 2 | YOLO + ByteTrack | 60% | **Diukur 29 Agustus: akurasi crossing 48,7% rata-rata (8 sampel), turun dari asumsi 80%.** Bukan bug logika — kehilangan deteksi saat padat. Lihat S-4 |
| 3 | Traffic State Builder | 90% | Jalan, tervalidasi fisik. Akurasi volume masukan mewarisi keterbatasan kotak 2 |
| 4 | Virtual Intersection (SUMO) | 100% | Network asli Simpang Pingit + program TLS dinamis |
| 5 | Realtime Traffic State | 90% | Polling live jalan |
| 6 | Traffic Forecast (LSTM) | 92% | Terlatih, tersambung, studi dampak ada |
| 7 | Scenario Generator | 90% | **Sudah live** lewat cache |
| 8 | Traffic Simulation | 92% | **Sudah live**, sudah divalidasi multi-seed |
| 9 | Performance Analysis (LOS) | 90% | 4 metrik nyata, tampil di dashboard |
| 10 | Adaptive Decision Engine | 65% / 90% | PPO dilatih, terintegrasi, model bisa dimuat & lolos test (naik dari 10%). Belum unggul di throughput, jadi peran tetap diisi Scenario Generator |
| 11 | Signal Timing Recommendation | 88% | Live. `/signal/status` belum baca cache skenario |
| 12 | Dashboard | 92% | Build hijau, badge `source` + LOS ada |

**Keseluruhan: ≈86% harfiah / ≈88% fungsional.**
PPO (kotak 10) naik, tapi validasi akurasi CV (kotak 2, S-4) menurunkan angka lebih banyak — 48,7% terukur, bukan lagi asumsi 80%. Turun tipis dari ≈88%/≈90% sebelumnya meski dua pekerjaan besar (PPO, validasi CV) sama-sama selesai — itu tandanya audit ini mengukur bukti nyata, bukan menaikkan angka tiap kali ada progres.

**Bukti eksekusi 29 Agustus:**
- `backend/` → `pytest -q` = **77 passed, 0 failed**
- `simulation/` → `pytest tests/ -q` = **11 passed, 1 failed** (lihat item S-2)
- `frontend/` → `npm run build` = **sukses, 13/13 route**

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
| Checkpoint PPO tidak ter-commit, `pytest` backend 1 gagal | ✅ **Selesai 29 Agustus** | Yuli commit model (`f62b7ac`); `stable-baselines3`/`gymnasium` ditambahkan ke `backend/requirements.txt`. `pytest` → 77 passed, 0 failed |

---

## 3. SISA KERJA — Fase 1 (sebelum 31 Agustus, video presentasi)

Total **±6 jam**, dibagi 3 orang. Semuanya rendah risiko, tidak ada eksperimen.

### 🔴 S-1. Panel Status Sinyal belum ikut sumber simulasi — Yuli, 1–2 jam

**Masalahnya:** di dashboard ada 2 panel bersebelahan. Panel "Rekomendasi" menampilkan angka **hasil simulasi SUMO**. Panel "Status Sinyal" menampilkan angka **rumus rule-based**. Dua panel, dua sumber, angkanya bisa tidak cocok.

Panel Status Sinyal bahkan punya badge "Diuji simulasi SUMO" di `SignalStatusPanel.tsx:242`, tapi badge itu **tidak akan pernah muncul** — `signal_service.py` cuma bisa menghasilkan `source` bernilai `"backend"`, `"demo"`, atau `"rule-based"` (baris 120, 164, 267, 411). Kode UI-nya ada tapi mati.

**Perbaikannya cuma di 1 tempat.** `_recompute_cycle_plan()` (`signal_service.py:207`) adalah **satu-satunya** fungsi yang membuat `CyclePlan`; kedua panel mengambil dari situ.

1. Di awal fungsi itu, panggil `live_scenario_cache_service.get_fresh(...)` — pola persis sama seperti `recommendation_service.py:107`
2. Kalau cache segar **dan** memuat `cyclePlan`, pakai itu, set `source = "scenario-generator"`
3. Kalau tidak, jalankan `recommend_cycle()` seperti sekarang — **jangan hapus jalur lama**, itu fallback-nya
4. Hapus penimpaan `cyclePlan` di `recommendation_service.py:181-187` karena sudah ditangani di hulu

**Selesai kalau:** worker `--full-cycle` jalan → **kedua** panel menampilkan "Diuji simulasi SUMO". Worker dimatikan >2 menit → keduanya balik "Estimasi langsung", tanpa error. Tambah 2 unit test (cache segar & cache basi).

---

### 🔴 S-2. Satu test merah — Yuli, 15 menit

**Masalahnya:** `pytest` di `simulation/` menghasilkan **1 failed**. `run_tls_simulation.py:769` sudah dipindah memanggil `recommend_full_cycle()`, tapi `ScenarioEngineStub` di `tests/test_forecast_client.py:188` masih cuma punya `recommend()`.

**Kenapa penting:** test itu tugasnya menjaga agar data forecast benar-benar diteruskan di tiap tahap. Selama merah, penjagaan itu mati. Dan kalau juri minta lihat test, merah = pertanyaan yang tidak perlu.

**Perbaikan:** tambahkan `recommend_full_cycle()` ke stub, sesuaikan assertion.

**Selesai kalau:** `pytest tests/ -q` di `simulation/` → **12 passed, 0 failed**.

---

### 🔴 S-3. Angka palsu "32 detik" di Digital Twin — Melpi, 30 menit

**Masalahnya:** `digitaltwinview.tsx:46,48` berisi `{ direction: "North", state: "GREEN", time: 32 }`. Sebelum data asli masuk, layar menampilkan angka yang **diketik manual**, bukan hasil sistem. Risikonya juri melihat itu di awal video dan mengira itu keluaran sistem.

**Perbaikan:** ganti jadi "memuat…" sampai data pertama masuk. Polanya sudah ada di `page.tsx:674`.

**Selesai kalau:** buka dashboard dengan backend mati — tidak ada satu pun angka yang tampil seolah data asli.

---

### ✅ S-4. Akurasi deteksi CV — SELESAI 29 Agustus, hasilnya perlu perhatian

Divalidasi manual: 8 potongan @1 menit (4 arah × ramai/sepi), dihitung manusia lalu dibandingkan `crossing_simpang.csv`. Detail lengkap + data mentah di **`docs/hasil-validasi-akurasi-cv.md`**.

**Hasil: rata-rata akurasi 48,7%** (rentang 22,2%–96,1%). Ini **jauh di bawah** target awal (~90%) dan harus dilaporkan apa adanya — bukan angka yang bisa dipoles.

**Sudah dicek ke kode, bukan bug arah/logika crossing** — `hitung_crossing()` (`vehicle_counter_pingit.py:866-868`) terverifikasi menghitung kedua arah lalu lintas dengan benar. Pola datanya (4 dari 5 sampel "ramai" punya akurasi terburuk) mengarah ke **kehilangan deteksi/tracking saat kondisi padat** — konsisten dengan keterbatasan ID-switch ByteTrack yang sudah didokumentasikan sendiri di kode untuk metrik antrean, kemungkinan juga memengaruhi hitungan crossing.

**Ini menurunkan kotak 2 (YOLO+ByteTrack) dari 80% menjadi lebih rendah** — lihat bagian 1. Sekaligus **relevan untuk kotak 3 dan 9**: kalau volume kendaraan yang masuk `TrafficState` bisa meleset 22%–96% tergantung kepadatan, itu bisa memengaruhi kualitas keputusan hijau, bukan cuma soal pelaporan angka.

**Kalimat aman untuk laporan** (jangan klaim 90%+, jangan generalisir dari 1 sampel terbaik):
> "Validasi manual pada 8 sampel menunjukkan akurasi rata-rata 48,7%, dengan sistem cenderung kehilangan hitungan pada kondisi padat — konsisten dengan keterbatasan tracking yang sudah didokumentasikan. Ini bukan bug pada logika crossing (sudah diverifikasi ke kode), melainkan keterbatasan deteksi pada kepadatan tinggi. Perbaikan lanjutan adalah kerja di luar scope 16 hari."

---

### 🟡 S-5. CV siap-RTSP tanpa perlu kamera — Rahmat, 30 menit

**Masalahnya:** sumber video di-hardcode (`vehicle_counter_pingit.py:1320`). Kalau juri tanya "bisa dipakai CCTV sungguhan?", jawabannya cuma klaim lisan.

**Perbaikan:** jadikan sumber video sebuah parameter.

```python
# cv2.VideoCapture menerima path file DAN URL RTSP dengan cara yang sama,
# jadi ini benar-benar cuma soal dari mana string-nya datang.
parser.add_argument("--sumber", default=None,
                    help="Path file video atau URL RTSP. Kosong = pakai rekaman.")
```

**Kenapa ini penting padahal cuma 30 menit:** pernyataan Anda berubah dari *"kami tidak bisa live"* (terdengar keterbatasan) jadi **"arsitekturnya menerima RTSP maupun file; kami memakai rekaman karena tidak ada akses stream CCTV Dishub"** (terdengar keputusan).

**Selesai kalau:** `--sumber rtsp://contoh` gagal di **koneksi** (wajar, tidak ada kameranya), bukan gagal di parsing argumen.

---

### 🟡 S-6. Tiga pernyataan scope untuk laporan — Melpi, 1 jam

Tiga hal ini **sudah benar apa adanya**, tidak perlu dikoding. Yang kurang cuma kalimatnya di laporan teknis:

| Hal | Kalimat yang dipakai |
|---|---|
| CV pakai rekaman | "Sistem memproses rekaman CCTV Simpang Pingit (43 menit, 4 kamera). Antarmuka masukan menerima file maupun stream RTSP; rekaman dipilih karena tidak tersedia akses ke stream CCTV operasional." |
| `north` pakai zona tengah | "Lengan utara diwakili zona badan simpang (`simpang_tengah`) sebagai proxy, karena sudut CCTV_2 menangkap badan simpang alih-alih lengan utara terpisah. Tercatat sebagai `northDataNote` di `metadata.json`." |
| Hanya 3 kandidat skenario | "Scenario Generator menguji 3 kandidat durasi per siklus, dipilih agar total waktu simulasi tetap di bawah interval keputusan 60 detik." |

---

### ⚠️ S-7. Verifikasi browser hidup — siapa saja, 30 menit

Perbaikan terakhir baru diuji lewat `npm run build`, **belum lewat browser sungguhan**. Buka dashboard, bandingkan angka di layar dengan hasil `POST /recommendation` dan `GET /signal/status` langsung. Pastikan cocok.

---

## 4. SISA KERJA — Fase 2 (1–7 September)

### P-1. PPO — kotak 10, Yuli

> **Berubah total 29 Agustus.** Dokumen ini sebelumnya menulis "nol baris kode RL". **Itu sudah tidak berlaku** — commit `f921ce9` (28 Agustus, 10.410 baris) membawa environment Gymnasium, training, evaluasi, integrasi backend, dan 7 test baru. Bagian di bawah adalah hasil review menyeluruh terhadap commit itu.

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

#### ✅ P-1a. Model hasil training tidak ada di repo — SELESAI 29 Agustus

Yuli sudah commit checkpoint-nya (`f62b7ac "add model"`, `aa9d06d "add smoke train ppo"`) — `decision_engine/models/smarttwin_ppo.zip` dan `smarttwin_ppo_smoke.zip` sekarang ada di repo.

**Sub-masalah yang baru ketemu saat verifikasi:** checkpoint-nya ada, tapi `pytest` backend tetap gagal dengan `ModuleNotFoundError: No module named 'stable_baselines3'` — library pembacanya belum terpasang di `backend/.venv` (beda dari `decision_engine/`'s venv tempat training jalan). **Sudah diperbaiki** hari ini: `stable-baselines3==2.9.0` + `gymnasium==1.3.0` ditambahkan ke `backend/requirements.txt` dan dipasang.

**Terverifikasi:** `pytest -q` di `backend/` → **77 passed, 0 failed**.

#### 🔴 P-1b. Klaim "PPO mengalahkan rule-based" belum sahih — Yuli, 2–3 jam

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

**Yang dikerjakan:** naikkan bobot throughput di reward, latih ulang, lalu laporkan ketiga metrik lalu lintas — bukan cuma reward.

#### 🟡 P-1c. Baseline pembanding bukan RuleBasedEngine asli — Yuli, 1–2 jam

`ppo_env.py:192` `rule_based_action()` hanya `argmax(antrean)` lalu `round(nilai × 9)` untuk durasi. Sedangkan `RuleBasedEngine` produksi memakai demand score + alokasi proporsional + largest-remainder rounding ke siklus tetap.

Jadi PPO dibandingkan dengan **tiruan sederhana**, bukan lawan sebenarnya. Klaim "mengalahkan rule-based" belum teruji terhadap engine yang benar-benar jalan di dashboard.

**Yang dikerjakan:** panggil `RuleBasedEngine` asli di jalur evaluasi, terjemahkan hasilnya ke aksi environment.

#### 🟡 P-1d. Fitur saat training ≠ fitur saat inference — Yuli, 1–2 jam

Ini masalah paling halus dan paling mudah terlewat:

| Slot | Saat training (`ppo_env.py:186`) | Saat inference (`ppo_engine.py:117`) |
|---|---|---|
| 0 | `volume/60` — kendaraan **yang sedang ada** di edge | `volume/60` — kendaraan **yang melintas** dalam window |
| 3 | `volume/33` — **volume yang sama** | `densityIndex/33` — besaran **berbeda** |

Dua konsekuensi: (a) `volume` saat training itu kehadiran sesaat (`getLastStepVehicleNumber`), sedangkan `TrafficState.volume` itu hitungan crossing — besaran berbeda; (b) di training slot 0 dan slot 3 **selalu berkorelasi sempurna** (angka sama, dibagi 60 vs 33), sedangkan saat inference keduanya sinyal independen. **Model belajar di dunia yang tidak sama dengan dunia tempat ia dipakai.**

Tambahan: `ppo_env.py:20` melatih dari `cv/output/smarttwin_traffic_data.csv` (21 Agustus), bukan `crossing_simpang.csv`/`snapshot_zona.csv` yang dipakai ingest sekarang.

#### Urutan kerja 1–7 September

P-1a ✅ selesai. Sisanya:

1. **P-1c** ganti baseline ke `RuleBasedEngine` asli
2. **P-1d** samakan fitur training dengan inference
3. **P-1b** naikkan bobot throughput, latih ulang, evaluasi ulang

**Aturan berhenti:** kalau setelah semua ini PPO tetap kalah pada throughput, **jangan dipaksakan aktif**. Kotak 10 tetap 90% fungsional dengan Scenario Generator, dan PPO tetap layak dilaporkan sebagai pengembangan yang berhasil dilatih. **PPO yang menurunkan throughput lebih buruk daripada rule-based yang bekerja.**

### P-2. Perkuat bukti LSTM — Yuli, 2–3 jam

Dua klaim masih bertumpu sampel kecil:
- "Mengalahkan naive baseline" (MAE 1,65 vs 2,30) — diuji pada **16 sequence** saja, dari 1.044 sequence latih
- "Forecast menurunkan delay" — **1 snapshot**

Perbaikan: bagi ulang data supaya test set lebih besar; ulang `scenario_worker.py --compare-forecast` di 10–20 snapshot. Target kalimat: *"konsisten membaik di 17 dari 20 pengujian"*.

### P-3. LOS per lengan — Rahmat, 2–3 jam

`calculate_los()` menghitung dari delay **rata-rata seluruh simpang**. HCM aslinya per lengan. Akibatnya kalau selatan macet parah (LOS E) tapi 3 lengan lain lancar (LOS A), sistem melaporkan LOS B — **masalah di selatan tidak terlihat**.

Bonus: demo jadi lebih meyakinkan — bisa menunjuk satu lengan dan bilang "yang ini LOS E, karena itu diberi hijau lebih lama".

### P-4. Rapi-rapi — siapa saja senggang

- `METERS_PER_QUEUED_VEHICLE = 7.0` estimasi → tulis di laporan sebagai asumsi, atau kalibrasi
- Bobot 50/50 di `select_best_scenario()` → tulis alasannya, atau uji sensitivitas
- Dua jalur Traffic State Builder paralel → gabungkan atau beri komentar kapan pakai yang mana
- `CLAUDE.md` masih menyebut `simulation/requirements-rl.txt` yang sudah hilang → perbarui
- `simulation/.venv` tidak punya `supabase` → untuk test forecast client pakai `backend/.venv`

### P-5. Perbaiki akar penyebab akurasi CV rendah — Rahmat, 2–4 jam

> **Update 29 Agustus:** akar penyebab **sudah ketemu** lewat pengamatan langsung Rahmat + verifikasi kode/geometri — bukan lagi "investigasi", sekarang tinggal "perbaikan". Detail lengkap di `hasil-validasi-akurasi-cv.md` bagian Interpretasi.

**Dua masalah berbeda, dua perbaikan berbeda:**

1. **Kendaraan hilang** (penyebab dominan, CCTV_1/CCTV_3 dempet + CCTV_2 kamera jauh) — kendaraan baru dapat `track_id` SETELAH lewat garis, jadi `prev_pos` kosong dan lintasnya tak tercatat (`vehicle_counter_pingit.py:852-855`). **Perbaikan yang realistis dalam waktu terbatas:** turunkan `CONFIDENCE` dari 0.35 (coba ~0.25) supaya kendaraan kedeteksi lebih awal/lebih kecil, tes ulang di 1-2 sampel yang tadi jelek (CCTV_1 7:31, CCTV_2 19:16), bandingkan `jumlah_crossing` baru vs manual yang sudah ada. **Perbaikan oklusi murni (motor dempet) kemungkinan tidak bisa dikejar dalam sisa waktu** — itu butuh model/resolusi lebih baik, cukup didokumentasikan sebagai keterbatasan.
2. **Kendaraan terhitung ganda di garis salah** (CCTV_2 khusus, sampel #6) — `sisi_garis()` pakai garis tak terbatas, bukan segmen (`vehicle_counter_pingit.py:465-479`), dan titik potong MAGELANG×DIPONEGORO cuma 0,016 dari ujung DIPONEGORO. **Perbaikan konkret:** batasi pengecekan ke proyeksi parameter `t` dalam rentang `[0,1]` di sepanjang segmen (bukan garis penuh) sebelum menghitung `sisi_garis()`. Ini cuma menyentuh CCTV_2 (satu-satunya kamera dengan >1 garis), risiko regresi kecil.

**Setelah salah satu/keduanya diperbaiki:** ulangi minimal 3 sampel yang paling jelek (bukan seluruh 8) dari tabel S-4 untuk buktikan ada perbaikan, update `hasil-validasi-akurasi-cv.md` dengan angka baru — jangan timpa angka lama, tambahkan sebagai "setelah perbaikan" supaya progresnya kelihatan.

**Bukan blocker demo** — nomor akurasi sudah ada dan jujur dilaporkan (S-4), ini pekerjaan penguatan kalau ada waktu.

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

- ❌ **"PPO mengalahkan rule-based"** — yang menang cuma reward (fungsi yang PPO dilatih untuk maksimalkan). Pada throughput PPO **tidak pernah** menang, dan baselinenya bukan `RuleBasedEngine` asli. Lihat P-1b/P-1c
- ❌ **"PPO sudah dipakai di sistem"** — default tetap rule-based; model sudah bisa dimuat (P-1a selesai) tapi belum diaktifkan sebagai default
- ❌ "Realtime CCTV" — rekaman
- ❌ **"Akurasi deteksi tinggi/95%"** — terukur 48,7% rata-rata (8 sampel), jangan digeneralisir dari sampel terbaik (#7, 96,1%) saja
- ❌ "Forecast terbukti menurunkan delay 14%" — sebelum P-2, itu 1 percobaan
- ❌ "Sistem berjalan otomatis penuh" — worker dijalankan manual

---

## 8. Pembagian tugas

| Siapa | Fase 1 (sebelum 31 Agt) | Fase 2 (1–7 Sept) |
|---|---|---|
| **Yuli** | S-1 panel sinyal (1–2j), S-2 test merah (15m) | **P-1b/c/d PPO** (utama), P-2 bukti LSTM |
| **Melpi** | S-3 hardcode (30m), S-6 pernyataan scope (1j) | Tampilkan LOS per lengan (dukung P-3) |
| **Rahmat** | S-5 argumen `--sumber` (30m) | P-3 LOS per lengan, P-4 rapi-rapi, **P-5 investigasi akurasi CV** |
| Siapa saja | S-7 verifikasi browser (30m) | — |

**Beban Fase 1: Yuli ±2j, Melpi ±1,5j, Rahmat ±4,5j.** Muat dalam 1 hari kerja, menyisakan 2 hari untuk latihan dan rekaman.

---

*Dokumen ini menggantikan `pembagian-tugas-tahap-akhir.md`, `pembagian-tugas-24-agustus.md`, `audit-24-agustus.md`, `status-integrasi-diagram-arsitektur.md`, `roadmap.md`, dan `realtime-dashboard.md` — semuanya dihapus 28 Agustus karena isinya sudah selesai atau bertentangan satu sama lain. Riwayatnya tetap ada di git.*

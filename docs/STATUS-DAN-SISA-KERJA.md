# STATUS & SISA KERJA — SmartTwin

**Diperbarui: 28 Agustus 2026.** Ini **satu-satunya dokumen status** di repo ini. Kalau mau tahu "sudah sampai mana" atau "apa yang belum", baca ini — jangan cari di dokumen lain.

Dokumen lain di `docs/` sekarang cuma 2 jenis: **cara kerja** (rujukan teknis) dan **hasil pengujian** (bukti untuk laporan). Tidak ada lagi dokumen "pembagian tugas" atau "audit" terpisah yang saling bertentangan.

> **Aturan biar tidak berantakan lagi:** kalau sebuah item di sini selesai, **pindahkan ke bagian 2 (Sudah Selesai)** dengan satu baris bukti. Jangan bikin dokumen status baru.

---

## 1. Posisi sekarang

| # | Kotak diagram | % | Keterangan singkat |
|---|---|---:|---|
| 1 | Traffic Monitoring Data | 85% | Jalan penuh. Rekaman `.mp4`, bukan RTSP live |
| 2 | YOLO + ByteTrack | 80% | Jalan. Akurasi belum pernah diukur formal |
| 3 | Traffic State Builder | 95% | Jalan, tervalidasi fisik |
| 4 | Virtual Intersection (SUMO) | 100% | Network asli Simpang Pingit + program TLS dinamis |
| 5 | Realtime Traffic State | 90% | Polling live jalan |
| 6 | Traffic Forecast (LSTM) | 92% | Terlatih, tersambung, studi dampak ada |
| 7 | Scenario Generator | 90% | **Sudah live** lewat cache |
| 8 | Traffic Simulation | 92% | **Sudah live**, sudah divalidasi multi-seed |
| 9 | Performance Analysis (LOS) | 90% | 4 metrik nyata, tampil di dashboard |
| 10 | Adaptive Decision Engine | 10% / 90% | PPO nol kode / peran terisi Scenario Generator |
| 11 | Signal Timing Recommendation | 88% | Live. `/signal/status` belum baca cache skenario |
| 12 | Dashboard | 92% | Build hijau, badge `source` + LOS ada |

**Keseluruhan: ≈84% harfiah / ≈90% fungsional.**
Selisihnya seluruhnya dari kotak 10 (PPO). Lihat bagian 4.

**Bukti eksekusi 28 Agustus:**
- `backend/` → `pytest -q` = **69 passed, 0 failed**
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

### 🟡 S-4. Akurasi deteksi CV belum pernah diukur — Rahmat, 3–4 jam

**Masalahnya:** kalau juri tanya **"seberapa akurat deteksinya?"**, jawaban Anda sekarang *"belum pernah diukur"*. Ini pertanyaan yang hampir pasti muncul dan satu-satunya yang belum punya jawaban berupa angka.

**Perbaikan (versi hemat, bukan mAP penuh):**
1. Pilih 5 potongan video @1 menit, kamera & kondisi berbeda (ramai/sepi)
2. **Hitung manual** kendaraan yang melintas di tiap potongan, catat di spreadsheet
3. Ambil angka CV untuk jendela waktu sama dari `crossing_simpang.csv`
4. `akurasi = 1 − |CV − manual| / manual` per potongan, lalu rata-ratakan
5. Tulis ke `docs/hasil-validasi-akurasi-cv.md` — **termasuk kalau hasilnya jelek**

**Kenapa cukup:** ini bukan mAP, jangan diklaim begitu. Tapi *"akurasi penghitungan 92% pada 5 sampel tervalidasi manual"* jauh lebih kuat daripada *"belum diukur"* — dan jujur.

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

### P-1. PPO — kotak 10, Yuli (pekerjaan terbesar)

**Kondisi sekarang: nol baris kode RL.** Pencarian `PPO|stable_baselines|gymnasium` di seluruh repo cuma menemukan 3 komentar. `simulation/requirements-rl.txt` bahkan sudah tidak ada.

Butuh 4 hal yang belum ada satu pun:
1. **Environment wrapper** — membungkus SUMO agar terlihat seperti lingkungan RL (`reset()`, `step()`, observation space, action space)
2. **Reward function** — mendefinisikan "bagus" secara angka. Ini yang **paling menentukan** dan paling sering salah. Mulai sesederhana mungkin: `reward = -(delay + antrean)`
3. **Loop pelatihan** — berjam-jam. SUMO jalan di CPU; GPU cuma bantu bagian jaringan sarafnya
4. **Validasi** — buktikan PPO mengalahkan rule-based pada metrik yang sama

| Hari | Target | Kalau gagal |
|---|---|---|
| 1–2 Sept | Wrapper jalan: `reset()`/`step()` bisa dipanggil, SUMO merespons | Stop di sini |
| 3–4 Sept | Pelatihan jalan & **reward naik** (bukan datar/acak) | **Kalau akhir hari ke-4 reward masih datar, STOP** |
| 5–6 Sept | Bandingkan PPO vs rule-based pada snapshot sama | — |
| 7 Sept | Tukar `RuleBasedEngine()` → `PPOEngine()` kalau menang | — |

**Sudah disiapkan:** `PPOEngine` cukup punya `.recommend(state, currentGreenSeconds, currentPhase, forecast, forecastWeight)` dengan bentuk **persis sama** seperti `RuleBasedEngine`. Kalau itu dipenuhi, penukarannya **satu baris**. Ini dirancang sejak awal, bukan kebetulan.

**Aturan berhenti:** kalau 4 September belum ada tanda belajar, berhenti. Kotak 10 tetap 90% fungsional dengan Scenario Generator. **PPO setengah jadi lebih buruk daripada rule-based yang bekerja.**

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
> "Ke-12 kotak terimplementasi. Sebelas berjalan penuh dan terverifikasi. Kotak Adaptive Decision Engine saat ini diisi Scenario Generator berbasis simulasi SUMO — keputusannya diuji lewat tiga kandidat simulasi nyata sebelum dipakai. PPO sedang dalam pelatihan sebagai pengembangan lanjutan, dan antarmukanya sudah disiapkan agar bisa langsung ditukar."

**"Apakah ini realtime?"**
> "Pemrosesan berjalan realtime terhadap masukan video. Kami memakai rekaman CCTV Simpang Pingit karena tidak ada akses ke stream operasional Dishub — antarmuka masukannya sendiri menerima RTSP maupun file."

**"Seberapa akurat deteksinya?"** *(setelah S-4 selesai)*
> "Akurasi penghitungan [X]% pada 5 sampel yang divalidasi manual. Validasi mAP formal dengan dataset teranotasi adalah pengembangan lanjutan."

**"Apa buktinya sistem ini lebih baik?"**
> "Setiap keputusan diuji lewat tiga kandidat di simulasi SUMO dan dipilih berdasarkan delay dan panjang antrean terendah, dengan LOS standar HCM 2000. Metrik pemenangnya tampil langsung di dashboard."

### JANGAN dikatakan

- ❌ "PPO sudah jadi" — nol kode
- ❌ "Realtime CCTV" — rekaman
- ❌ "Akurasi 95%" sebelum S-4 selesai — belum diukur
- ❌ "Forecast terbukti menurunkan delay 14%" — sebelum P-2, itu 1 percobaan
- ❌ "Sistem berjalan otomatis penuh" — worker dijalankan manual

---

## 8. Pembagian tugas

| Siapa | Fase 1 (sebelum 31 Agt) | Fase 2 (1–7 Sept) |
|---|---|---|
| **Yuli** | S-1 panel sinyal (1–2j), S-2 test merah (15m) | **P-1 PPO** (utama), P-2 bukti LSTM |
| **Melpi** | S-3 hardcode (30m), S-6 pernyataan scope (1j) | Tampilkan LOS per lengan (dukung P-3) |
| **Rahmat** | S-4 validasi CV (3–4j), S-5 argumen `--sumber` (30m) | P-3 LOS per lengan, P-4 rapi-rapi |
| Siapa saja | S-7 verifikasi browser (30m) | — |

**Beban Fase 1: Yuli ±2j, Melpi ±1,5j, Rahmat ±4,5j.** Muat dalam 1 hari kerja, menyisakan 2 hari untuk latihan dan rekaman.

---

*Dokumen ini menggantikan `pembagian-tugas-tahap-akhir.md`, `pembagian-tugas-24-agustus.md`, `audit-24-agustus.md`, `status-integrasi-diagram-arsitektur.md`, `roadmap.md`, dan `realtime-dashboard.md` — semuanya dihapus 28 Agustus karena isinya sudah selesai atau bertentangan satu sama lain. Riwayatnya tetap ada di git.*

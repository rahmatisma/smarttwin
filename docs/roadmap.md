# SmartTwin — Roadmap Pengembangan (REVISI DARURAT: 16 Hari)

> ⚠️ **SUPERSEDED sejak 17 Agustus 2026 — jangan dijadikan acuan status terkini.**
> Dokumen ini berhenti disinkronkan tanggal 17 Agustus. Banyak risiko/checklist di sini sudah tertutup tapi tidak pernah dicentang balik (contoh: identitas koridor `east`, kalibrasi `north` — dua-duanya sudah selesai per audit 26-27 Agustus, tapi masih tertulis "berisiko" di bawah). **Acuan status terkini: `docs/pembagian-tugas-tahap-akhir.md`.** Dokumen ini dipertahankan cuma sebagai catatan sejarah scope/timeline awal, bukan sumber kebenaran kerja yang sudah/belum selesai.

**Tim:** AkU dan DuA ORang PLEnGer — Politeknik Negeri Lhokseumawe
**Kompetisi:** KMIPN VIII 2026, final di Makassar
**Timeline:** 15–31 Agustus 2026 (~16 hari)
**Status:** REVISI DARURAT — timeline asli 4 minggu (28 hari) terkompresi jadi 16 hari
**Disinkronkan dengan kondisi repo:** 17 Agustus 2026 — lihat [Progress 15–17 Agustus](#progress-1517-agustus-2026). Sinkronisasi sebelumnya 15 Agustus

> **Kenapa direvisi:** Rencana 3-track paralel (CV, Digital Twin, RL) diasumsikan punya ruang sampai akhir bulan. Ternyata batas waktu riil cuma sampai 31 Agustus — 16 hari dari sekarang, sekitar 57% dari waktu yang direncanakan. Perubahan wajib: **PPO dan LSTM keluar dari scope aktif mulai sekarang**, bukan dievaluasi nanti — checkpoint Minggu 3 yang direncanakan sebelumnya sendiri sudah tidak muat. Yuli dialihkan dari RL & Forecast ke track Web/Backend. Statusnya beda jauh antara keduanya: PPO belum disentuh sama sekali, sementara LSTM sudah menghasilkan dua eksperimen terlatih dan terevaluasi (PeMS04 R² 0,879 dan TMU) — lihat [Status PPO dan LSTM](#status-ppo-dan-lstm).

---

## Progress 15–17 Agustus 2026

Tiga hari pertama dari 16 hari. Ringkasan ini **menambah**, bukan menggantikan, penandaan di Fase 0–1 di bawah.

### Selesai

**1. Sinkronisasi 4 video CCTV** (`cv/_arsip/README.md`, `cv/output/sync_report.json`)

Keempat lengan Simpang Pingit terekam dan dipotong ke jendela waktu bersama, jadi frame ke-N di keempat file punya jam dinding yang sama. Rekaman final 16:30:12–17:19:16 (15 Agustus 2026), 78.046 frame @30 fps per kamera.

Pekerjaan ini jauh lebih berat dari dugaan awal: jam burned-in CCTV harus dibaca lewat OCR, dan pada MP4 terfragmentasi `cap.set()` mendarat di frame yang salah walau jamnya terbaca sempurna — sehingga `sync_videos.py` versi final tidak memakai `cap.set()` sama sekali. Barang buktinya diarsipkan di `cv/_arsip/`.

**Batas yang masih berlaku:** laju jam tiap channel DVR tidak sama persis (selisih ~0,3% antara Pingit 3 dan 4), jadi di ujung rekaman keempatnya bisa hanyut ~10 detik. Aman untuk agregasi per jendela 5 menit; **tidak aman** untuk mencocokkan kejadian antar-lengan frame demi frame.

**2. Perbaikan bug volume CSV** (`65f0e73`, lanjutan `e37fc4d`)

`vehicle_count` dan `*_count` selama ini diambil dari kendaraan yang **terlihat di frame**, bukan yang **memotong counting line** — padahal docstring sudah menjanjikan crossing sejak awal. Akibatnya `COUNTING_LINES` dan `ARAH_MASUK` tidak berpengaruh apa pun terhadap CSV; seluruh kalibrasi garis cuma menggambar di layar.

Ketahuan karena `east` dan `north` — video sama (`CCTV_2.mp4`), garis beda — menghasilkan 7.578 baris **identik byte demi byte**.

Dampak terukur (south, jendela 16:30:12–16:33:12, 440 baris di kedua versi): volume **1876 → 73**, sementara `queue` tetap **185**. Queue yang tidak bergerak itu kontrolnya — hanya kolom volume yang berubah.

> **Angka volume sebelum dan sesudah `65f0e73` TIDAK SEBANDING.** CSV lama sudah dihapus dari repo (`e37fc4d`) supaya tidak terpakai tanpa sengaja.

**3. Dataset CV final** — `cv/output/smarttwin_traffic_data.csv`, 29.453 baris, keempat lengan 16:30:12–17:19:16:

| approach | baris | volume | queue |
|---|---|---|---|
| north | 7.589 | 3.183 | 19 |
| east | 7.583 | 1.264 | 19 |
| west | 7.368 | 1.962 | 9 |
| south | 6.913 | 1.272 | 2.543 |

### Status kalibrasi counting line

Kolom volume sekarang sepenuhnya ditentukan garis ini, jadi status kalibrasinya **langsung jadi status validitas angka**:

| Lengan | Garis | Status | Bukti |
|---|---|---|---|
| **south** | `(0.10, 0.65, 0.90, 0.65)` — default, tapi terverifikasi | **Terverifikasi** | 67/67 crossing bergerak menuju stop line (uji 60 detik, 16 Agt); laju 34,7/menit atas uji 180 detik (17 Agt) |
| **west** | `(0.830, 0.753, 0.956, 0.345)` — diganti 16 Agt | **Terverifikasi** | Arah jalur diukur optical flow per kotak uji; sumbu jalan +11°, garis dipasang tegak lurus di +101°. Garis lama nyaris sejajar arus, cuma 14 crossing dari 174 track |
| **east** | `(0.964, 0.659, 0.745, 0.461)` | **Garis oke, koridornya belum** | Digambar dari analisa langsung frame `CCTV_2.mp4`. Lihat catatan di bawah |
| **north** | `(0.10, 0.65, 0.90, 0.65)` — default | **BELUM dikalibrasi** | Kameranya memotret badan simpang, bukan ruas lurus; pendekatannya belum diputuskan. Angkanya keluar (volume tertinggi, 3.183) tapi belum punya dasar |

**Pelajaran metodologis:** jangan pernah memvalidasi laju crossing dari satu jendela 60 detik. Uji 60 detik pada south memberi **1** crossing dan sempat terbaca seperti regresi; jendela 180 detik memberi **104** (34,7/menit, sejajar lengan lain). Menit pertama itu kebetulan jendela lalu lintas berhenti. Minimal 180 detik.

### Terbuka: identitas koridor east

`east` dan `north` membaca **video yang sama** (`CCTV_2.mp4`), dibedakan hanya oleh counting line. Yang belum terbukti: **koridor jalan tempat garis east dipasang itu Diponegoro atau Magelang?**

Bukti yang ada (`cv/_arsip/BUKTI_pita_atas_CCTV4_vs_CCTV2.jpg`) hanya menunjukkan **ada** koridor jalan menerus di frame CCTV 2 (74 deteksi lolos di atas y=0,28H) — bukan koridor itu lengan yang mana. Bukti itu dibuat untuk menjawab pertanyaan lain.

Kalau ternyata Magelang, `east` dan `north` menghitung lengan yang sama dua kali — kesalahan yang jauh lebih halus daripada baris identik, karena angkanya kelihatan wajar.

**Cara menutupnya:** bearing garis terhadap network SUMO (TLS `SIMPANG_CENTER`), atau uji silang — satu kendaraan yang sama pada detik yang sama di dua kamera, ditelusuri masuk dari lengan mana.

> **Sampai itu terjawab, angka east jangan dipakai penuh** — pakai sebagai indikatif, dan jangan dijadikan dasar klaim kinerja lengan timur di laporan.

**Caveat terpisah yang berlaku sekarang juga:** karena east dan north satu video, kolom `queue_length_veh`, `queue_length_m_est`, dan `density_index` keduanya **selalu identik** (lihat tabel di atas: 19 dan 19) — ketiganya tidak bergantung pada counting line. Yang benar-benar membedakan east dari north hanyalah kolom volume.

### Berubah dari asumsi roadmap sebelumnya

**`backend/` sudah tidak kosong.** Per 17 Agustus ada **22 file Python**: `app/main.py`, `app/api/routes/` (health, traffic, signal, forecast, recommendation), `app/schemas/`, `app/services/`, `app/core/config.py`, plus `tests/test_api.py`, `requirements.txt`, `.env.example`, dan `README.md`. Roadmap ini sebelumnya menyebut backend "nol file" di tiga tempat — sudah dikoreksi di bawah. Yang belum diverifikasi: apakah endpoint-nya sudah menyajikan `TrafficState` asli atau masih stub.

**Ada eksperimen LSTM keempat yang tidak ada di rencana** — `forecasting/scripts/yolo/` (5 skrip: inspect, preprocess, train, evaluate, predict), commit `a25f2ba` "training lstm with yolo data". Ini melatih LSTM dari data CV kita sendiri, bukan data proxy luar negeri. Secara arah, ini justru menjawab kelemahan utama yang dilaporkan di [Cara membawakannya](#cara-membawakannya): transferabilitas.

> ⚠️ **Tapi sumber datanya bermasalah.** Skripnya membaca `forecasting/data/smarttwin_traffic_data_copy.csv`, yaitu salinan CSV **sebelum** perbaikan `65f0e73` — `vehicle_count` masih berbasis kehadiran, dan barisnya masih memuat east sebagai duplikat persis north. Selain itu file sumbernya tidak ada di repo (`forecasting/data/` cuma berisi Brisbane.csv, PEMS04.npz, TMU.csv), dan `forecasting/outputs/yolo/` belum ada, jadi hasilnya belum bisa diperiksa maupun diulang.
>
> **Perlu keputusan pemilik track ini (Yuli):** latih ulang dari CSV baru, atau tidak dibawa ke laporan. Metrik apa pun dari run yang sekarang tidak bisa dipertanggungjawabkan.

---

## Checkpoint keputusan PPO — 17 Agustus 2026

**Keputusan: PPO TIDAK dikerjakan sekarang.** Bukan ditolak selamanya — ditunda dengan titik cek ulang yang tanggalnya sudah ditetapkan di bawah, supaya tidak jadi keputusan mengambang.

### Dasar keputusan

Dipetakan dari kondisi repo per 17 Agustus, bukan dari asumsi roadmap lama:

| | Item wajib sebelum training PPO bisa mulai | Status sekarang | Biaya |
|---|---|---|---|
| A | Traffic State Builder | 25% (skema saja, logika agregasi 0%) | 2–3 od |
| B | Generator demand CV → SUMO | 0% | 3–4 od |
| C | Baseline fixed-time dari observasi sinyal asli | 0% | 2 od |
| D | Environment wrapper Gym/Gymnasium di atas SUMO+TraCI | 0% | 3–4 od |
| E | Reward + harness evaluasi | 0% | 2 od |
| | **Total sebelum langkah training pertama** | | **12–15 od** |

Anggaran kapasitas 18–28 Agustus: **31 orang-hari** (2 orang Sel–Rab, 3 orang mulai Kam; 29–31 Agustus disisihkan untuk demo, slide, dan latihan).

- MVP tanpa PPO: 21,5–23,5 od → **penyangga +7,5 od**
- MVP + PPO: 30–33 od → **penyangga −2 sampai +1 od**

Karena A–C berurutan dan dikerjakan orang yang sama dengan MVP, jalur kritisnya membuat **training PPO paling cepat mulai ~27 Agustus** — menyisakan 3 hari yang beririsan penuh dengan persiapan demo. Kalau D meleset satu hari saja (paling rawan, belum pernah dikerjakan siapa pun di tim), praktis tidak ada hasil yang bisa dibawakan.

### Yang harus dikorbankan kalau dipaksakan

Untuk membuka ~9 od, yang harus **dihapus** — bukan disederhanakan: validasi PKJI 2023 (3 od), `page.tsx` lepas dari mockData (2 od), anotasi CVAT + mAP/MOTA/IDF1 (2 od), kalibrasi north + identitas koridor east (2 od).

Keempatnya item **kredibilitas**, dan tidak satu pun tergantikan oleh PPO. PPO yang dilatih di atas demand berasumsi, tanpa baseline PKJI dan tanpa metrik akurasi CV, justru **lebih sulit dipertanggungjawabkan** di depan juri daripada rule-based yang tervalidasi.

### Catatan soal server training

Ada tidaknya server **tidak mengubah kalkulasi ini**. Server hanya mempercepat F (training), satu-satunya item yang bukan jalur kritis. Ia tidak menyentuh A–E yang semuanya kerja integrasi di laptop. Tiga hal tambahan: PPO dengan policy MLP kecil hampir tidak terbantu GPU (hambatannya SUMO melangkah per detik — butuh banyak core CPU untuk environment paralel, bukan GPU); menyiapkan server memakan 0,5–1 od dari anggaran yang sama; dan training tetap tidak bisa mulai sebelum environment-nya ada. Server memperbaiki bagian yang bukan masalahnya.

### Yang dikerjakan sekarang

Prioritas penuh ke MVP, urut: **A** Traffic State Builder → **B** integrasi CV→SUMO → **C** baseline sinyal existing → **Scenario Generator** → **Decision Engine rule-based** → **Performance Analysis** → **validasi PKJI 2023**.

### 🔁 Titik cek ulang: Rabu, 26 Agustus 2026

Pada tanggal itu, PPO dievaluasi ulang — **berdasarkan sisa waktu dan kapasitas yang nyata saat itu, bukan asumsi hari ini.**

Kenapa 26 Agustus: MVP inti (7 item di atas, 15,5–17,5 od) secara kumulatif jatuh tempo antara 24–26 Agustus pada anggaran kapasitas ini. Tanggal 26 memberi jeda kalau ada yang meleset, dan masih menyisakan 27–28 Agustus (6 od) untuk mengambil keputusan sebelum jendela demo.

**Gerbang yang harus lolos SEMUANYA supaya PPO dibuka lagi** — kalau ada satu saja gagal, PPO tetap tidak dikerjakan dan dibawakan sebagai desain + roadmap lanjutan:

- [ ] Ketujuh item MVP di atas selesai **dan** terverifikasi jalan end-to-end, bukan sekadar ada file-nya
- [ ] Backend menyajikan `TrafficState` asli — `traffic_service.py` tidak lagi mengembalikan angka hardcoded
- [ ] `frontend/src/app/page.tsx` sudah lepas dari `@/lib/mockData`
- [ ] Validasi PKJI 2023 sudah menghasilkan angka, bukan baru rencana
- [ ] Tidak ada isu validitas data yang menggantung — kalibrasi `north` dan identitas koridor `east` sudah tertutup
- [ ] Sisa kapasitas riil **≥ 12 od** sebelum 28 Agustus

> **Ambangnya memang tinggi, dan itu disengaja.** Sisa kapasitas 27–28 Agustus cuma 6 od, sementara PPO butuh 12–15 od. Artinya gerbang terakhir hanya bisa lolos kalau MVP selesai jauh lebih cepat dari perkiraan — sekitar 22 Agustus. Checkpoint ini bukan formalitas untuk membuka PPO belakangan; ia ada supaya keputusan hari ini punya tanggal kedaluwarsa dan diuji ulang dengan angka, bukan dilupakan.

---

## Pembagian tim (revisi)

| Peran | Fokus | Perubahan dari rencana sebelumnya |
|---|---|---|
| Rahmat — Setup & Digital Twin | Monorepo, SUMO/TraCI, integrasi seluruh modul | Tidak berubah |
| Melpi — Data & CV | Video, anotasi, YOLO+ByteTrack, Traffic State Builder | Tidak berubah — ini jalur kritis tercepat yang harus selesai duluan |
| Yuli — Web & Backend (dialihkan) | `backend/` — FastAPI + PostgreSQL dari nol, lalu sambungkan `frontend/src/app/page.tsx` dari `mockData` ke data asli | **Dialihkan dari RL & Forecast.** Eksperimen LSTM dihentikan setelah PeMS04 & TMU selesai dievaluasi; PPO tidak jadi dikerjakan |

**Alasan realokasi Yuli:** dengan 16 hari, tidak ada slack buat track ke-4 yang risikonya tinggi dan hasilnya tidak pasti (PPO/LSTM). Kapasitas itu dipindah ke bottleneck yang justru pasti terjadi.

**Bottleneck-nya bukan dashboard.** `frontend/` sudah punya 9 komponen (Header, Sidebar, StatsRow, DonutRing, DigitalTwinPanel, CameraFeedPanel, SignalStatusPanel, RecommendationPanel, ForecastChart) dan `simulation/snapshot_dashboard_data.py` sudah menghasilkan data density asli dari SUMO. Fokus Yuli:

1. ~~**`backend/` FastAPI + PostgreSQL dari nol**~~ — **sudah dikerjakan** per 17 Agustus (22 file Python). Sisanya: verifikasi endpoint menyajikan `TrafficState` asli, bukan stub, dan pastikan skema PostgreSQL-nya ada
2. **Lepas `page.tsx` dari data dummy** — `frontend/src/app/page.tsx:19` masih `import { ... } from "@/lib/mockData"`; ganti ke data asli lewat backend. **Ini prioritas utama Yuli sekarang**
3. Komponen dashboard baru dibuat hanya kalau memang ada yang kurang, bukan sebagai kerjaan utama
4. **Putuskan nasib LSTM-YOLO** (`forecasting/scripts/yolo/`) — dilatih dari CSV yang sudah terbukti salah; latih ulang dari `cv/output/smarttwin_traffic_data.csv` yang baru, atau tidak dibawa ke laporan

## Status PPO dan LSTM

Keduanya sama-sama di luar scope 16 hari, tapi statusnya **jauh berbeda** — jangan disamakan waktu menyusun laporan atau presentasi.

| Komponen | Status |
|---|---|
| PPO (Decision Engine RL) | Di luar scope, **belum dikerjakan sama sekali**. Tidak ada kode RL di repo — hanya `simulation/requirements-rl.txt` berisi dua nama package (`stable-baselines3`, `sumo-rl`). Tidak ada environment wrapper, tidak ada training script. Tetap dibawakan di laporan sebagai bagian desain sistem dan roadmap lanjutan. **Ditinjau ulang 26 Agustus 2026** — lihat [Checkpoint keputusan PPO](#checkpoint-keputusan-ppo--17-agustus-2026) |
| LSTM (Traffic Forecast) | **Tiga eksperimen dijalankan, dua di antaranya selesai dilatih & dievaluasi.** Pengerjaan dihentikan 15 Agustus 2026 untuk fokus ke scope 16 hari. Kode, data, model, dan seluruh hasil evaluasi ada di repo (`forecasting/`) dan dipakai sebagai bahan laporan teknis |

### Rincian tiga eksperimen LSTM

| Dataset | Apa itu | Status | Hasil utama |
|---|---|---|---|
| **PeMS04** | Sensor jalan tol California (Caltrans), 307 sensor × 3 feature | Dilatih & dievaluasi — **paling lengkap** | **R² 0,879** overall; flow **0,933**, occupancy 0,869, speed 0,839. Test 2.535 sampel |
| **TMU** | Sensor jalan raya Inggris (A174, Teesside), interval 15 menit | Dilatih & dievaluasi | **MAPE speed 2,09%**; MAPE vehicle_count 25,6% (MAE 27,87). Test 444 sampel |
| **Brisbane** | API open data simpang, Brisbane City Council | **Hanya diproses — tidak pernah masuk training** | Tidak ada metrik. Dari 66 baris mentah cuma 5 baris lolos preprocessing (rentang 5 menit), sedangkan modelnya butuh 16 timestep untuk satu sequence |

**PeMS04 porsinya jangan dikecilkan di narasi laporan** — itu satu-satunya eksperimen dengan artefak lengkap (model tersimpan, evaluasi per-sensor dan per-feature, plot actual-vs-predicted).

### Cara membawakannya

**Yang benar:** modelnya bekerja, tapi datanya bukan data lokasi target. R² 0,879 dan MAPE speed 2,09% membuktikan pipeline LSTM-nya jalan. Masalahnya transferabilitas — TMU dan PeMS04 sama-sama sensor ruas jalan menerus di luar negeri, bukan simpang bersinyal Indonesia. Brisbane satu-satunya data simpang asli, dan justru itu yang durasi pengumpulannya tidak cukup.

**Yang salah dan jangan dipakai:** "hasilnya jelek" atau "modelnya gagal". Angkanya ada di repo dan bisa dibuka juri dalam satu menit — klaim itu akan langsung terbantah oleh datanya sendiri.

**Temuan yang dilaporkan:** hambatan utama forecasting untuk simpang target adalah **ketersediaan data lokasi**, bukan arsitektur model. Ini hasil penelitian yang bisa dipertanggungjawabkan.

**Hati-hati saat mengutip angka:** MAE/RMSE PeMS04 dalam satuan ter-scale (bukan kendaraan/jam), dan MAPE tidak dapat dipercaya di dataset ini — `queue_proxy` TMU menghasilkan MAPE 1.008.321.136% karena pembagian mendekati nol. Pakai MAE/RMSE/R² di slide.

**Fallback untuk demo 16 hari:** asumsi volume flat dari `TrafficState` terakhir.

---

## Keputusan kunci

| Area | Keputusan |
|---|---|
| Jenis simpang | Simpang 4 bersinyal |
| Lokasi | Simpang Pingit, Yogyakarta — sudah dikonfirmasi sebagai "Simpang Empat Pingit" oleh Dishub Kota Yogyakarta, dilengkapi ATCS + detektor kendaraan khusus. Ada penelitian akademik (metodologi MKJI) yang sudah memodelkan keempat lengannya — bisa jadi pembanding validasi PKJI 2023 |
| Sumber video | Live feed CCTV ATCS via app agregator, direkam via screen-record |
| Decision Engine | Rule-based — satu-satunya pendekatan untuk 16 hari ini, sesuai proposal sendiri yang menyatakan ini valid untuk tahap awal |

## Kebutuhan data

| # | Data | Jumlah | Sumber | Buat apa |
|---|---|---|---|---|
| 1 | Video mentah | Minimal 20–30 menit, dari sudut yang tersedia di Simpang Pingit | Screen-record app CCTV ATCS | Input pipeline CV |
| 2 | Geometri persimpangan | 1 network | OpenStreetMap + `netconvert` | Bangun model SUMO |
| 3 | Konfigurasi sinyal existing | 3–5 siklus penuh | Rewind-pause dari video rekaman | Baseline fixed-time |
| 4 | Video teranotasi | 5–10 menit, klip pendek | Subset video sendiri + CVAT | Ukur mAP, MOTA/IDF1 |
| 5 | Historis volume kendaraan Simpang Pingit | — | Tidak dikejar lagi di 16 hari ini | LSTM — pencarian data pengganti dihentikan; ketiadaan data historis lokasi target justru jadi temuan yang dilaporkan |

## Stack teknologi

| Komponen | Teknologi |
|---|---|
| Deteksi kendaraan | YOLO26s (`ultralytics`, bobot `cv/models/yolo26s.pt`) + ByteTrack bawaan. Dijalankan di venv CUDA terpisah `E:\KMIPN 2026\venv-cuda` — 5,1× lebih cepat dari CPU (42,8 vs 8,4 fps) |
| Simulasi | SUMO + TraCI mentah |
| Backend | FastAPI + WebSocket |
| Frontend | Next.js + Tailwind |
| Database | PostgreSQL |
| Deployment | Docker Compose (native run tetap oke buat demo kalau waktu mepet) |

---

## Roadmap 16 hari

### Fase 0 — Hari 1–3 (15–17 Agustus): Tutup data, mulai setup

Sebagian besar sudah selesai sebelum revisi ini dibuat:

- [x] Rahmat: init monorepo `/frontend` `/backend` `/cv` `/simulation` `/docker` + `/forecasting`
- [x] Rahmat: kontrak data — `docs/data-contract.md`
- [x] Rahmat: export geometri Pingit dari OSM + `netconvert` → `simulation/network/simpang4_pingit.net.xml.gz`
- [x] Rahmat: SUMO network Pingit valid — 34 junction, satu TLS `SIMPANG_CENTER`, 20 koneksi, coverage TLS 100% (`check_tls_coverage.py`). Artefak roundabout dari OSM sudah diratakan jadi satu junction lewat `flatten_roundabout.py`
- [x] Rahmat: TraCI terhubung ke network Pingit dan terverifikasi — `run_intersection.py` (`test_traci.py` hanya diagnostik instalasi, pakai network `cross` bawaan SUMO, bukan network proyek)
- [x] Melpi: CV dasar jalan — `cv/vehicle_counter.py` + `cv/output/smarttwin_traffic_data.csv`
- [x] Yuli: scaffold Next.js dashboard — 9 komponen sesuai mockup, masih pakai `mockData`
- [x] **Yuli: scaffold FastAPI** — `backend/` sudah berisi 22 file Python (routes, schemas, services, tests) per 17 Agustus. Skema PostgreSQL-nya sendiri belum diverifikasi
- [x] Melpi: rekam keempat lengan Simpang Pingit — **keempatnya dapat**, bukan cuma 2 minimum yang ditargetkan, dan sudah disinkronkan ke satu jendela waktu (16:30:12–17:19:16)
- [ ] Melpi: observasi 3–5 siklus sinyal existing dari rekaman — belum dikerjakan, dan ini yang dipakai sebagai baseline fixed-time

> **Catatan regresi (15 Agustus).** Centang SUMO/TraCI di atas sempat tidak sesuai kenyataan: `run_intersection.py` memuat `network/simpang4.net.xml.gz` — network **Bandung** dari sebelum pindah lokasi — karena commit `050324f` tanpa sengaja membatalkan migrasi Pingit `811f7c4`. Sudah diperbaiki (`92fbe98`) dan network lamanya dihapus (`37d493b`). Sekarang hanya ada satu network proyek: `simpang4_pingit.net.xml.gz`. Kalau ada file network lain muncul lagi, itu regresi.

### Fase 1 — Hari 4–7 (18–21 Agustus): CV jalan, SUMO matang, backend nyambung

- [x] Melpi: YOLO+ByteTrack jalan di footage Pingit — keempat lengan diproses, volume dari crossing garis, dataset penuh 49 menit tersedia. **Selesai lebih cepat dari jadwal fase ini**
- [ ] Melpi: kalibrasi counting line `north` — satu-satunya lengan yang garisnya masih default dan belum punya dasar (lihat tabel status kalibrasi)
- [ ] Melpi: tutup identitas koridor `east` (Diponegoro vs Magelang) lewat bearing SUMO atau uji silang antar-kamera
- [ ] Melpi: mulai Traffic State Builder — agregasi `VehicleDetection` per jendela waktu jadi `TrafficState`, sesuai `docs/data-contract.md`
- [x] Rahmat: TraCI kontrol fase manual terverifikasi di `SIMPANG_CENTER` — program 4 fase, siklus 90 detik (39 hijau / 6 kuning per arah); `setPhase()` dan `setRedYellowGreenState()` dua-duanya terbukti mengubah state lampu
- [~] Yuli: endpoint FastAPI yang menyajikan `TrafficState` + skeleton WebSocket — routes `traffic`/`signal`/`forecast`/`recommendation` sudah ada berikut schemas & services. **Belum diverifikasi** apakah sudah menyajikan data asli atau masih stub, dan WebSocket belum dicek

### Fase 2 — Hari 8–11 (22–25 Agustus): Integrasi MVP

**Goal:** video → deteksi → data → simulasi → rekomendasi jalan end-to-end

- [ ] Traffic State Builder tersambung ke SUMO, demand kendaraan ikut deteksi asli
- [~] Ekstraksi state per lengan dari SUMO — `simulation/snapshot_dashboard_data.py` sudah jalan: simulasi Pingit 300 detik, klasifikasi lengan dari sudut kompas, tulis `outputs/approach_snapshot.json`. Masih snapshot manual sekali jalan, belum aliran data hidup
- [ ] Scenario Generator (heuristik) + Decision Engine rule-based
- [ ] Yuli: `frontend/src/app/page.tsx` lepas dari `@/lib/mockData`, ambil data asli dari backend

**Milestone.**

### Fase 3 — Hari 12–14 (26–28 Agustus): Rule-based final, validasi PKJI

- [ ] Rule-based + Performance Analysis selesai dan teruji
- [ ] Anotasi klip pendek via CVAT, ukur mAP dan MOTA/IDF1
- [ ] Validasi hasil SUMO terhadap PKJI 2023 — cross-check ke penelitian Simpang Pingit yang sudah ada
- [ ] Dashboard mendekati selesai penuh
- [ ] **26 Agustus — jalankan [checkpoint keputusan PPO](#checkpoint-keputusan-ppo--17-agustus-2026).** Periksa keenam gerbangnya satu per satu dan catat hasilnya di sini. Kalau ada satu saja gagal, PPO tetap di luar scope dan keputusannya selesai — tidak perlu ditinjau lagi sampai kompetisi berakhir

### Fase 4 — Hari 15–16 (29–31 Agustus): Demo prep

- [ ] Docker Compose kalau sempat — native run tetap oke buat demo
- [ ] Bug fixing, latihan presentasi
- [ ] Siapkan narasi jujur soal PPO dan LSTM — **dua narasi berbeda**: PPO sebagai desain/roadmap lanjutan yang belum dikerjakan, LSTM sebagai eksperimen yang sudah menghasilkan model terlatih dan terevaluasi. Yang kedua dibawakan sebagai hasil penelitian, bukan sebagai kekurangan
- [x] Tarik metrik & plot evaluasi LSTM ke repo — sudah masuk di `forecasting/outputs/` (commit `9148b6c`)
- [ ] Siapkan slide hasil LSTM: pakai R² dan MAE/RMSE, **jangan pakai MAPE** (rusak di dataset ini), dan jangan sebut MAE PeMS04 sebagai satuan kendaraan (angkanya ter-scale)

---

## Rencana kontingensi (lebih agresif — sudah dikompresi maksimal)

Di 16 hari, tidak ada ruang "cek nanti". Kalau ada tanda molor, langsung ambil urutan ini:

1. Scenario Generator jadi 2 opsi saja
2. Visualisasi digital twin: diagram statis + titik posisi kendaraan berkala, bukan animasi penuh
3. WebSocket → polling sederhana
4. Docker Compose → native run satu laptop

**Yang tidak boleh dikorbankan:** pipeline CV → Digital Twin → rekomendasi rule-based end-to-end, dan validasi terhadap PKJI 2023.

**Risiko lama sudah lewat — daftar ini direvisi 17 Agustus.**

~~Risiko terbesar: penyelesaian data di Fase 0 (Melpi).~~ **Tertutup.** Keempat lengan terekam dan tersinkron, dataset CV penuh 49 menit sudah ada. Ini yang paling bergantung waktu kalender riil, dan sudah aman.

~~Risiko kedua: `backend/` masih nol file.~~ **Tertutup sebagian.** Sudah 22 file Python per 17 Agustus. Sisanya tinggal verifikasi apakah endpoint-nya menyajikan data asli.

**Risiko terbesar sekarang — validitas, bukan ketersediaan.** Datanya sudah ada; yang belum pasti adalah apakah angkanya berarti apa yang kita kira:

1. **Identitas koridor `east`.** Kalau ternyata Magelang, kita melaporkan lengan utara dua kali dengan label berbeda. Ini kesalahan yang tidak akan ketahuan dari angkanya sendiri — semuanya terlihat wajar. **Tutup sebelum Fase 3.**
2. **`north` belum dikalibrasi** tapi justru menyumbang volume tertinggi (3.183, dua kali lipat lengan lain). Angka terbesar di dataset ini adalah angka yang paling lemah dasarnya.
3. **LSTM-YOLO dilatih dari CSV yang sudah terbukti salah** (`a25f2ba`). Perlu keputusan: latih ulang atau tidak dibawa.

Pola yang sama di ketiganya: pipeline-nya jalan, keluarannya rapi, dan justru itu yang bikin cacat asumsinya sulit terlihat. Bug volume kemarin lolos berhari-hari persis karena CSV-nya kelihatan baik-baik saja.

**Risiko jadwal:** Fase 1 CV selesai lebih cepat, tapi sisa Fase 1 (Traffic State Builder) belum mulai dan dia prasyarat seluruh Fase 2. Sisa waktu 14 hari (18–31 Agustus).

---

## Referensi

- **PKJI 2023 resmi:** Direktorat Jenderal Bina Marga, binamarga.pu.go.id — bagian relevan: kapasitas simpang APILL
- **Penelitian pembanding:** "Pemodelan Lalu Lintas pada Simpang Bersinyal di Kota Yogyakarta (Studi Kasus Simpang Pingit)" — kapasitas per lengan sudah dihitung, bisa jadi cross-check validasi PKJI
- **Live CCTV:** App agregator CCTV ATCS Indonesia (iOS/Android), Dishub Kota Yogyakarta
- **Anotasi:** CVAT (cvat.ai, gratis dan open-source)
- **Library:** `ultralytics` (YOLOv8+ByteTrack), `traci`, `sumolib`

---

*Revisi darurat: kompresi dari 28 hari menjadi 16 hari (15–31 Agustus 2026). PPO tidak dikerjakan; eksperimen LSTM dihentikan setelah dilatih & dievaluasi dengan data proxy. Yuli dialihkan ke Web/Backend.*

*Update 17 Agustus 2026 — disinkronkan ulang dengan kondisi repo. Selesai: sinkronisasi 4 video CCTV, perbaikan bug volume CSV (`65f0e73`), kalibrasi counting line south & west, scaffold backend. Terbuka: identitas koridor east, kalibrasi north, nasib LSTM-YOLO. Sisa waktu 14 hari.*

*Keputusan 17 Agustus 2026 — PPO tidak dikerjakan sekarang; prioritas penuh ke MVP rule-based. Ditinjau ulang 26 Agustus dengan enam gerbang terukur. Dasar hitungannya ada di [Checkpoint keputusan PPO](#checkpoint-keputusan-ppo--17-agustus-2026).*

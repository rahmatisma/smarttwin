# Bagian B — Alur Data SmartTwin, Dijelaskan Detail

> Catatan pribadi belajar. Semua isi di bawah dibaca langsung dari kode
> (bukan dari ringkasan dokumen lain), disusun 5 September 2026.
> Tujuannya: supaya tiap kotak di diagram "buat apa" dan tiap tabel
> "isinya apa" jelas, bukan cuma nama teknis.

---

## Peta besar dulu (baca ini sebelum masuk detail)

Bayangkan datanya seperti barang yang berpindah tangan berkali-kali:

```
1. Kamera lihat kendaraan
2. Dicatat jadi angka (CSV)
3. Angka dipindah ke "gudang pusat" (Supabase) — 3 tingkat kerapian
4. Sistem ambil angka terkini dari gudang, buat 3 usulan pengaturan lampu
5. Ketiga usulan diuji di simpang virtual (SUMO)
6. Pemenang disimpan ke "papan pengumuman" (cache) dan "buku riwayat"
7. Dashboard baca papan pengumuman itu, tampilkan ke layar
```

Detail tiap langkah ada di bawah. Tiap bagian dijelaskan: **buat apa**,
**isinya apa**, dan **siapa yang pakai**.

---

## Tahap 1 — CV menghasilkan data mentah

**File:** `cv/vehicle_counter_pingit.py`

**Buat apa:** Ini program yang benar-benar "melihat" video, pakai YOLO
buat mendeteksi tiap kendaraan lalu ByteTrack buat mengikuti kendaraan
yang sama antar-frame (supaya 1 motor tidak dihitung berkali-kali).

**Hasilnya ditulis ke 2 file CSV lokal** (bukan langsung ke database):

| File | Isinya |
|---|---|
| `cv/output/crossing_simpang.csv` | Tiap kali kendaraan **melintasi garis** di suatu lengan, dicatat 1 baris: jam, kamera mana, lengan mana, berapa yang lewat (dipecah motor/mobil/bus/truk) |
| `cv/output/snapshot_zona.csv` | Perkiraan **kepadatan** (density) — bukan hitungan lewat, tapi "seberapa penuh" suatu zona di layar |

**Kenapa dipisah jadi 2 file:** crossing itu **hitungan kejadian**
(nambah tiap ada yang lewat), sedangkan density itu **snapshot kondisi**
(dilihat sesaat). Dua jenis pengukuran yang beda sifat, jadi dipisah
filenya.

**Belum masuk database di titik ini** — dua CSV ini masih di komputer
lokal.

---

## Tahap 2 — Data mentah dikirim ke Supabase (ada 2 jalur, beda kegunaan)

### Jalur A — Kirim sekaligus (dipakai pas nyiapin demo)

```
run_ingest.py (di root project)
    -> panggil backend/app/pipeline/cv_csv_bridge.py :: ingest()
```

**Buat apa:** Kalau video sudah selesai diproses semua (CSV-nya sudah
lengkap dari awal sampai akhir), jalankan ini SEKALI untuk memindahkan
**semua isi CSV** ke Supabase sekaligus. Ini langkah 1 di SOP demo.

**Aman diulang** — kalau dijalankan 2x dengan CSV yang sama, tidak
bikin data dobel (pakai deteksi duplikat lewat kombinasi
`intersectionId`+`windowStart`+`windowEnd`).

### Jalur B — Kirim sedikit-sedikit (dipakai pas ada yang upload video baru)

```
Orang upload video lewat halaman CCTV di dashboard
    -> backend/app/services/cv_trigger_service.py (nyalakan proses YOLO di belakang layar)
    -> cv/process_uploaded_video.py (jalanin YOLO)
    -> cv/supabase_writer.py (tulis ke Supabase sedikit-sedikit, sambil video diproses)
```

**Buat apa:** Ini buat skenario interaktif — video BARU yang belum
pernah diproses, diupload langsung dari dashboard, hasilnya nongol ke
database sambil YOLO masih jalan (tidak perlu nunggu CSV selesai
duluan).

**Bedanya sama Jalur A:** Jalur A ambil dari **file CSV yang sudah
jadi**. Jalur B nulis Supabase **sambil YOLO masih memproses video**,
langsung dari memory, tidak lewat CSV perantara.

**Kedua jalur ini berakhir di tabel yang sama** (dijelaskan di bawah) —
cuma beda "pintu masuk"-nya.

---

## Tahap 3 — 3 tingkat kerapian data di Supabase

Ini bagian yang paling sering bikin bingung karena ada 3 tabel yang
kelihatannya mirip. Perbedaannya adalah **tingkat kerapian/rangkuman**:

```
trafficLaneMetrics   (paling MENTAH — per lengan, per jendela 5 detik)
        |
        v  (dirangkum/agregasi)
trafficApproachStates (RANGKUMAN — 1 baris per lengan, siap dipakai)
```

Plus 1 tabel lagi yang levelnya beda (bukan soal kendaraan, tapi soal
"kapan"):

```
trafficStates  (cuma AMPLOP PENANDA WAKTU, isinya bukan angka kendaraan)
```

### `trafficStates` — amplop penanda waktu

**Buat apa:** Menandai "ada 1 pengukuran untuk simpang ini, dari jam
sekian sampai jam sekian, sumbernya dari mana". **TIDAK ADA angka
kendaraan di tabel ini sama sekali.**

| Kolom | Contoh isi | Artinya |
|---|---|---|
| `id` | 4821 | Nomor unik "amplop" ini — dipakai tabel lain buat nunjuk balik ke sini |
| `intersectionId` | 1 | Simpang mana (cuma ada 1 di proyek ini: Simpang Pingit) |
| `windowStart` | 2026-08-15 16:30:10 | Mulai jam berapa |
| `windowEnd` | 2026-08-15 16:30:15 | Sampai jam berapa (jendelanya 5 detik) |
| `source` | "cv" | Datang dari CV (bisa juga nilai lain kalau ada sumber lain) |
| `createdAt` | (waktu proses tulis jalan) | Kapan baris ini benar-benar ditulis ke database |

**Kenapa perlu tabel amplop kalau tidak ada angkanya?** Karena satu
jendela waktu itu punya BANYAK baris rincian (1 per lengan, kadang 1
per lajur) — supaya semua rincian itu bisa "dikumpulkan jadi 1 grup",
mereka semua nunjuk ke 1 nomor amplop yang sama (`trafficStateId`).

### `trafficLaneMetrics` — rincian paling mentah, per lengan per jendela

**Buat apa:** Ini rincian ASLI, langsung dari hasil hitung CV, belum
dirangkum apa-apa.

| Kolom | Contoh isi (lengan Utara, jendela 16:30:10) | Artinya |
|---|---|---|
| `trafficStateId` | 4821 | Nunjuk ke "amplop" mana (tabel di atas) |
| `laneId` | (id lajur Utara) | Lajur/lengan mana |
| `timestamp` | 2026-08-15 16:30:15 | Jam akhir jendela ini |
| `vehicleCount` | 2 | Total kendaraan lewat di jendela ini |
| `carCount` | 2 | Dari situ, berapa yang mobil |
| `motorcycleCount` | 0 | Berapa motor |
| `busCount` | 0 | Berapa bus |
| `truckCount` | 0 | Berapa truk |
| `queueLengthVeh` | 0 | Berapa kendaraan ngantre (dalam satuan kendaraan) |
| `queueLengthMEst` | (angka meter) | Perkiraan panjang antrean dalam meter |
| `densityIndex` | (0.0 - 1.0) | Seberapa padat (dari data density/snapshot_zona) |

**Ini tabel yang PALING BANYAK barisnya** — karena 1 baris = 1 lengan =
1 jendela 5 detik. Kalau video 43 menit, itu ribuan baris.

### `trafficApproachStates` — rangkuman siap pakai (ini yang PALING PENTING)

**Buat apa:** Ini hasil rangkuman dari `trafficLaneMetrics` — 1 baris
per lengan per jendela, sudah dijumlah/dirata-rata. **Inilah yang
BENERAN dipakai** oleh Scenario Generator, RuleBasedEngine, dan
dashboard — bukan `trafficLaneMetrics` langsung.

| Kolom | Contoh isi (lengan Utara) | Artinya |
|---|---|---|
| `approach` | "north" | Lengan mana |
| `volume` | 2 | Total kendaraan (dijumlah dari semua lajur di lengan itu) |
| `queueLengthVeh` | 0 | Antrean (diambil nilai maksimum dari lajur-lajurnya) |
| `queueLengthMEst` | (meter) | Antrean dalam meter |
| `densityIndex` | (0.0-1.0) | Rata-rata kepadatan |
| `avgSpeedKmh` | **null** | **Sengaja kosong** — CV belum bisa ukur kecepatan. Ada komentar di kode: "jangan diisi 0.0 supaya tidak terbaca seolah kendaraan diam" |

**File yang bikin rangkuman ini:** `backend/app/pipeline/traffic_state_builder.py`

**Poin penting yang sempat bikin saya salah gambar di diagram
sebelumnya:** `traffic_state_builder.py` itu **bukan langkah terpisah
yang jalan sendiri setelah ingest selesai** — dia itu kelas/alat yang
**dipanggil DARI DALAM** `cv_csv_bridge.py::ingest()` untuk langsung
merangkum begitu selesai nulis `trafficLaneMetrics`. Tapi dia juga
dipakai di tempat LAIN secara terpisah (misal
`simulation/run_tls_simulation.py::loadTrafficState()` yang minta "buatkan
rangkuman dari kondisi TERBARU sekarang" kapan saja dibutuhkan, tidak
menunggu proses ingest). Jadi ini alat serbaguna, dipanggil dari
beberapa tempat berbeda, bukan cuma 1 tahap linear.

---

## Tahap 4 — Sistem mengambil kondisi terkini (2 cara, buat kebutuhan beda)

**File:** `simulation/scenario_worker.py`, `simulation/run_tls_simulation.py`

Tiap kali sistem mau bikin rekomendasi baru, dia ambil data dari
`trafficApproachStates`, tapi dengan **2 cara beda**:

| Cara | Fungsi | Ambil data seberapa lama | Dipakai buat |
|---|---|---|---|
| `loadTrafficState()` | 1 jendela **5 detik** paling akhir | Sangat baru, tapi rawan "kaget" kalau kebetulan lagi rame sesaat | Kandidat **Baseline** |
| `loadAveragedTrafficState()` | Rata-rata **2 menit** terakhir (24 jendela) | Lebih stabil, tidak gampang salah baca kondisi sesaat | Kandidat **Aggressive & Balanced** (rumus PKJI) |

**Kenapa dibedakan:** rumus PKJI butuh angka kendaraan per jam yang
dihitung dari jendela 5 detik dikali 720 — kalau kebetulan pas rame
1-2 kendaraan ekstra di jendela itu, hasil kali 720-nya jadi meleset
jauh. Rata-rata 2 menit meredam "kagetan" itu. Baseline (rumus lebih
sederhana) tetap pakai jendela 5 detik supaya perilakunya tidak ikut
berubah dari sebelumnya.

---

## Tahap 5 — Prediksi masa depan (LSTM) — ada 2 model, bukan cuma 1

**File:** `backend/app/services/forecast_service.py` (model AGREGAT,
1 simpang jadi 1 angka), `backend/app/services/per_approach_forecast_service.py`
(model PER LENGAN, 4 angka terpisah)

**Cara kerjanya dipanggil:** `simulation/forecast_client.py`
(dipakai `scenario_worker.py`) mengirim **HTTP request ke backend
sendiri** (bukan baca database langsung):

1. `GET /api/v1/traffic/live-csv` (atau riwayat serupa) — ambil 12
   `TrafficState` terakhir (12 × 5 detik = 60 detik riwayat)
2. `POST /api/forecast/approaches` — kirim 12 data itu, minta prediksi
   **60 detik ke depan** (12 timestep berikutnya, tiap 5 detik)

**Kalau model per-lengan gagal/tidak tersedia:** otomatis jatuh ke
model agregat sebagai cadangan, ditandai
`forecastSource: "aggregate-recent-share-fallback"` di hasilnya — jadi
kalau ini muncul, itu tandanya sedang pakai cadangan, bukan model
utama.

**Hasil prediksi ini cuma berisi 1 angka per lengan** (`predicted_volume`
— total kendaraan, bukan dirinci motor/mobil/bus/truk). Ini persis
alasan kenapa Aggressive/Balanced (yang butuh rincian jenis kendaraan
buat rumus PKJI) **tidak bisa** pakai hasil prediksi ini — sudah
dibahas panjang di percakapan sebelumnya.

---

## Tahap 6 — Scenario Generator: bikin 3 usulan pengaturan lampu

**File:** `simulation/scenario_generator.py` — kelas `ScenarioEngine`

**Buat apa:** Dari data Tahap 4 & 5, hitung 3 rencana siklus lampu
berbeda:

| Kandidat | Dasar hitungannya | Pakai forecast? |
|---|---|---|
| **Baseline** | `decision_engine/rule_based_engine.py` (rumus sederhana: skor kepadatan → detik hijau) | Ya, dicampur 30% |
| **Aggressive** | Rumus PKJI 2023 + koreksi Degree of Saturation | Tidak |
| **Balanced** | Rumus PKJI 2023 (pembagian proporsional polos) | Tidak |

---

## Tahap 7 — Uji 3 usulan itu di simpang virtual, pilih pemenang

**File:** `simulation/run_tls_simulation.py` (jalankan SUMO lewat TraCI,
network `simulation/network/simpang4_pingit.net.xml.gz`)

**Buat apa:** Ketiga kandidat di atas **benar-benar dijalankan** di
simulasi (bukan cuma dihitung di atas kertas), diukur delay/antrean/
throughput/LOS-nya, lalu `select_best_scenario()` pilih yang hasilnya
paling bagus.

---

## Tahap 8 — Simpan hasil (2 jenis, tujuan beda)

**File:** `simulation/scenario_worker.py` — fungsi `write_cache()` dan
`write_history()`

### `liveScenarioCache` — papan pengumuman (cuma 1 baris, ditimpa terus)

**Buat apa:** Nyimpan HASIL TERBARU saja — begitu ada hasil baru,
baris lama **ditimpa**, bukan ditambah. Ini yang dibaca dashboard buat
tampilan real-time.

**Basi setelah 120 detik** — kalau umurnya lebih dari itu, dianggap
tidak bisa dipakai, sistem fallback ke jalur cadangan (dijelaskan di
Tahap 9).

### `recommendations`, `simulations`, `simulationMetrics` — buku riwayat (terus bertambah)

**Buat apa:** Beda dari cache, ini **tidak pernah ditimpa** — tiap
hasil baru **ditambahkan** sebagai baris baru. Inilah yang dipakai
halaman **History** di dashboard buat nampilin riwayat dari waktu ke
waktu.

---

## Tahap 9 — Backend memutuskan mau pakai data mana

**File:** `backend/app/services/signal_service.py`,
`backend/app/services/recommendation_service.py`

**Buat apa:** Saat ada permintaan rekomendasi:

1. Cek `liveScenarioCache` — kalau masih segar (≤120 detik) → pakai itu,
   `source = "scenario-generator"`
2. Kalau basi → hitung sendiri langsung pakai
   `decision_engine/engine_factory.py::create_decision_engine()`
   (default `RuleBasedEngine`, atau `PPOEngine` kalau env var
   `SMARTTWIN_DECISION_ENGINE=ppo` di-set), `source = "rule-based"`

**Endpoint yang menyediakan ini ke luar (dipanggil frontend):**

| Endpoint | Buat apa |
|---|---|
| `GET /signal/status` | Status lampu sekarang (buat panel Signal Status) |
| `POST /recommendation` | Rekomendasi siklus lampu (buat panel Recommendation) |
| `GET /api/v1/digital-twin/scenarios/latest` | Data buat halaman Digital Twin |
| `GET /api/v1/history/recommendations` | Riwayat rekomendasi (buat halaman History) |
| `POST /api/forecast/approaches` | Prediksi LSTM per lengan (dipanggil `scenario_worker.py`, bukan frontend langsung) |
| `GET /api/v1/traffic/...`, `/api/v1/cctv/...`, `/api/v1/simulation/...`, `/api/v1/health` | Data traffic mentah, CCTV, kontrol simulasi, cek kesehatan server |

---

## Tahap 10 — Dashboard ambil data (2 jalur berbeda, ini penting)

**File:** `frontend/src/lib/supabaseData.ts`

Ternyata dashboard **TIDAK selalu lewat backend** buat ambil data —
ada 2 jalur:

### Jalur 1 — Lewat backend API (pakai `fetch(...)`)

- `/signal/status` → panel Signal Status
- `/recommendation` → panel Recommendation
- `/api/v1/history/...` → halaman History
- `/api/v1/digital-twin/scenarios/latest` → halaman Digital Twin

### Jalur 2 — Langsung ke Supabase dari browser (pakai `.from(...)`, TANPA lewat backend)

- `trafficStates` → data traffic mentah
- `cameras`, `cameraVideos` → daftar kamera & video
- `intersections`, `approaches` → data referensi simpang

**Kenapa ini penting diketahui:** kalau backend mati tapi Supabase
masih hidup, sebagian dashboard (yang jalur 2) **masih bisa tampil**,
sementara sebagian lain (jalur 1, misal panel rekomendasi) akan error/
kosong. Ini bukan bug — cuma arsitektur yang perlu dipahami supaya
tidak salah diagnosis kalau ada bagian dashboard yang "hidup sebagian".

---

## Ringkasan super singkat (kalau lupa detail di atas)

```
Kamera -> CSV lokal -> Supabase (3 lapis kerapian data)
       -> sistem ambil kondisi terkini (2 cara: sesaat vs rata-rata)
       -> tambah prediksi (opsional, cuma buat Baseline)
       -> hitung 3 usulan lampu -> uji di simpang virtual -> pilih menang
       -> simpan ke papan pengumuman (cache) + buku riwayat (history)
       -> backend sediakan lewat API
       -> dashboard ambil (sebagian lewat API, sebagian langsung Supabase)
```

# Kotak 3 — Traffic State Builder

> Investigasi langsung ke `backend/app/pipeline/traffic_state_builder.py`
> (1.602 baris, dibaca menyeluruh strukturnya). Disusun 6 September 2026.

---

## Cara termudah memahami ini — mulai dari sini

Ingat di Kotak CV, hasil hitungan per-lengan (dari `crossing_simpang.csv`
dkk) dikirim ke Supabase, masuk ke tabel `trafficLaneMetrics` — itu
tabel yang isinya **per lajur, apa adanya**, belum dirangkum.

**Traffic State Builder itu tukang rangkum.** Kerjanya sesimpel ini:

1. Ambil semua baris `trafficLaneMetrics` untuk **1 titik waktu**
   (1 "amplop" `trafficStateId` yang sama).
2. Kelompokkan baris-baris itu berdasar **lengan mana** dia (lewat
   `laneId` → cari tahu itu lajur punya lengan apa).
3. Untuk tiap lengan (Utara/Timur/Selatan/Barat), **jumlahkan** semua
   angka kendaraannya (kalau lengan itu punya lebih dari 1 lajur),
   **rata-ratakan** angka kepadatannya.
4. Cek juga: **apakah ke-4 lengan datanya lengkap?** Kalau ada yang
   bolong, dicatat sebagai peringatan (`missingApproaches`) — bukan
   error yang menghentikan proses, cuma catatan jujur "1 lengan ini
   tidak ada datanya".
5. Hasilnya: 1 paket rapi berisi kondisi ke-4 lengan, disimpan ke
   `trafficApproachStates`.

**Itu saja intinya** — dari "banyak baris berantakan per lajur" jadi
"1 paket rapi per lengan, per titik waktu".

---

## ✅ Ada 2 file bernama sama — sudah ditangani baik oleh tim, bukan masalah terbuka

Ada **dua** file bernama `traffic_state_builder.py`:

| File | Status |
|---|---|
| `backend/app/pipeline/traffic_state_builder.py` | **Aktif dipakai** — dibaca `scenario_worker.py`, API backend, semua jalur produksi |
| `simulation/traffic_state_builder.py` | **Legacy/tidak dipakai produksi** — alat manual buat replay CSV lama jadi snapshot JSON offline |

**Koreksi dari versi catatan saya sebelumnya:** saya sempat cuma kutip
peringatan dari sisi file backend, kesannya cuma 1 file yang "sadar
diri". Setelah saya cek langsung isi file legacy-nya, **ternyata
dia juga punya peringatan sendiri yang sama jelasnya** di baris
1-9-nya:

> *"JALUR OFFLINE/LEGACY, BUKAN RUNTIME PRODUKSI... Jalur aktif adalah
> cv_csv_bridge.py (CSV -> Supabase), lalu
> backend/app/pipeline/traffic_state_builder.py (Supabase ->
> TrafficState). Scenario worker dan API tidak membaca output JSON
> script ini."*

Jadi **kedua file saling mewanti-wanti dengan jelas** — bukan cuma
satu sisi. Saya juga grep seluruh repo: **nol file lain yang
meng-import file legacy ini** — dia betul-betul cuma alat mandiri,
tidak nyambung ke jalur produksi manapun secara diam-diam.

**Kesimpulan:** tidak ada yang perlu "diperbaiki" di kode untuk temuan
ini — sudah ditangani rapi oleh tim (dua peringatan, saling silang).
Yang perlu diperbaiki cuma catatan saya sendiri yang tadinya kurang
lengkap kutipannya (sudah dibetulkan di sini). Sudah diverifikasi juga
sebelumnya: `run_tls_simulation.py` benar mengimpor dari file backend
yang aktif, bukan yang legacy.

**Satu detail teknis menarik yang ikut ketemu waktu baca file
legacy ini:** dia punya bagian "SEMANTIK KOLOM SUMBER" yang menjelaskan
aturan `queueLengthVeh` seharusnya di-**MAX** (bukan di-jumlah) karena
itu data KEHADIRAN, sementara `volume` boleh dijumlah karena itu data
ALIRAN. Backend yang aktif (dibahas di atas) memakai **SUM** untuk
`queueLengthVeh`, bukan MAX. Saat ini itu tidak jadi masalah nyata
(karena 1 lengan cuma pernah punya 1 baris data aktif per jendela —
lihat catatan `LAJUR_PER_LENGAN`/lane_2 kosong di Kotak 1), tapi kalau
suatu saat lajur ke-2 mulai dipakai atau ada jalur pemanggilan lain
yang menggabung banyak titik waktu, SUM bisa mulai menumpuk kehadiran
yang sama seperti yang dikhawatirkan komentar CV. **Ini sekarang jadi
2 sumber yang sama-sama mendukung kecurigaan awal** (komentar CV +
dokumentasi builder legacy), walau belum ada bukti dia AKTIF salah di
kode produksi hari ini.

---

## Ringkasan 5W1H

- **Apa:** Kelas `TrafficStateBuilder`, tukang rangkum data mentah
  per-lajur jadi kondisi rapi per-lengan.
- **Siapa/file mana:** `backend/app/pipeline/traffic_state_builder.py`.
- **Kapan dipanggil:** (a) otomatis di akhir `cv_csv_bridge.py::ingest()`
  buat merangkum batch yang baru masuk, dan (b) dipanggil langsung
  oleh `scenario_worker.py` (lewat `run_tls_simulation.py`) tiap kali
  butuh kondisi terbaru/rata-rata.
- **Di mana sumber & tujuannya:** Baca dari `trafficLaneMetrics`,
  tulis ke `trafficApproachStates`.
- **Kenapa perlu tahap terpisah ini** (bukan langsung dari CV ke
  approach states): karena 1 lengan bisa punya lebih dari 1 lajur, dan
  cara menggabungkan tiap jenis angka itu beda-beda (dijelaskan di
  bawah) — butuh 1 tempat yang konsisten melakukan itu.
- **Bagaimana:** Query Supabase → kelompokkan per lengan lewat peta
  relasi lajur→lengan→simpang → gabungkan angka dengan aturan
  tertentu → cek kelengkapan → simpan.

---

## Aturan menggabungkan angka (beda-beda tiap jenis data!)

Dari fungsi `aggregate_approach()`, ini aturan pastinya kalau 1 lengan
punya lebih dari 1 baris (lebih dari 1 lajur) di titik waktu yang sama:

| Jenis data | Cara gabung | Kenapa |
|---|---|---|
| `volume`, `carCount`, `motorcycleCount`, `busCount`, `truckCount` | **DIJUMLAH** | Kendaraan di lajur 1 + lajur 2 = total lengan itu |
| `queueLengthVeh`, `queueLengthMEst` | **DIJUMLAH** | Sama alasannya — antrean tiap lajur digabung jadi total lengan |
| `densityIndex` | **DIRATA-RATA** | Kepadatan itu rasio (0.0-1.0), tidak masuk akal dijumlah (bisa lebih dari 1) |
| `avgSpeedKmh` | **SELALU `None`** (kosong) | CV belum bisa ukur kecepatan sama sekali — kodenya eksplisit tidak menghitung ini, bukan lupa |

---

## ⚠️ Temuan yang perlu saya laporkan jujur (bukan cuma dipoles)

Saya baca ulang komentar di `cv/vehicle_counter_pingit.py` (Kotak CV)
yang bilang: *"...persis kesalahan yang SEDANG TERJADI di
backend/app/pipeline/traffic_state_builder.py (queue di-sum lintas
detik)"* — maksudnya, tim CV menuduh fungsi ini menjumlahkan antrean
dari **banyak titik waktu berbeda**, yang berarti 1 kendaraan diam
yang sama bisa terhitung berkali-kali (sekali per detik dia masih
diam), bikin angka antrean jadi bengkak.

**Saya telusuri kodenya baris demi baris untuk cek klaim ini** — dan
hasilnya **tidak sepenuhnya cocok** dengan yang saya temukan:

- `buildFromSupabase()` (baris 1260-1283) mengelompokkan
  `lane_metrics` **per `trafficStateId`** dulu (`metrics_by_state`),
  BARU memanggil `build_state()` sekali per kelompok itu.
- `build_state()` cuma menerima baris yang **sudah disaring untuk 1
  `trafficStateId` saja** — jadi `aggregate_approach()` yang
  menjumlahkan itu, dalam kode SEKARANG, cuma menjumlah baris-baris
  dalam **1 titik waktu yang sama** (beda LAJUR, bukan beda DETIK).
- Kalau memang cuma beda lajur (bukan beda waktu), menjumlahkan itu
  **benar**, bukan bug — itu literally "antrean lajur 1 + antrean
  lajur 2 = antrean lengan".

**Kesimpulan saya:** klaim di komentar CV itu kemungkinan (a) merujuk
ke versi kode yang lebih lama yang sudah diperbaiki tanpa komentarnya
ikut diperbarui, atau (b) ada jalur pemanggilan lain yang belum saya
temukan yang tidak menyaring per-`trafficStateId` dengan benar. **Saya
tidak bisa memastikan mana yang benar** tanpa bertanya langsung ke
siapa yang menulis komentar itu — jadi saya laporkan sebagai
**ketidaksesuaian yang belum terjawab**, bukan saya klaim "sudah pasti
aman" atau "sudah pasti bug". Ini PR buat ditanyakan/dicek lagi.

---

## Bug lama yang sudah dikonfirmasi diperbaiki

**PostgREST diam-diam memotong hasil di 1000 baris.** Ditemukan 25
Agustus 2026: rekaman 49 menit menghasilkan 2.152 baris
`trafficLaneMetrics`, tapi cuma 1000 yang kebaca (tanpa error/
peringatan apapun dari Supabase) — jadi `trafficApproachStates` cuma
kebentuk untuk 250 dari 538 jendela, sisanya **hilang tanpa jejak di
log**. Ambang ini kena di rekaman apa pun yang lebih panjang dari
~21 menit — bukan kasus langka.

**Sudah diperbaiki**: `get_lane_metrics()` sekarang eksplisit
mem-paginasi (`--range()` berulang sampai habis), jadi tidak lagi
bergantung ke limit diam-diam PostgREST.

---

## 2 cara data "kondisi terbaru" diambil (beda kegunaan)

| Method | Ambil berapa window | Dipakai untuk |
|---|---|---|
| `build_latest_state_for_intersection()` | **1** window terbaru (`.limit(1)`) | `loadTrafficState()` — Baseline |
| `buildFromSupabase(limit=N)` | **N** window terbaru sekaligus | `loadAveragedTrafficState()` — Aggressive/Balanced (N=24, lalu dirata-ratakan lagi di luar fungsi ini) |

Catatan: `buildFromSupabase` mengembalikan **daftar** `BuiltTrafficState`
(satu per window, sudah lengkap per-lengan) — bukan 1 gabungan. Rata-
rata 2 menitnya dihitung TERPISAH oleh `loadAveragedTrafficState()` di
`run_tls_simulation.py`, bukan di dalam builder ini.

---

## "Kualitas data" di sini artinya apa — dan apa yang BUKAN artinya

Tiap `BuiltTrafficState` dibawa `dataQuality` berisi:
- `completenessScore` — (4 dikurangi jumlah lengan yang datanya
  bolong) ÷ 4. Kalau ke-4 lengan ada datanya, skornya 1.0.
- `missingApproaches` — daftar lengan mana yang kosong di titik waktu
  itu.
- **Peringatan yang SELALU ada, apa pun kondisinya:** *"Completeness
  tidak mengukur akurasi YOLO/ByteTrack."*

Ini penting: skor "lengkap 1.0" cuma berarti **ke-4 lengan ADA
datanya**, bukan berarti **datanya AKURAT**. Kode ini jujur menandai
batasannya sendiri, tidak menyamarkan seolah "completeness 100% =
data sempurna".

---

## Pertanyaan juri yang mungkin muncul + jawaban siap-pakai

**T: "Kalau 1 kamera mati/videonya rusak, apa sistem berhenti?"**
> "Tidak. Traffic State Builder tetap jalan untuk 3 lengan lainnya,
> cuma menandai lengan yang bolong itu di `missingApproaches` dan
> menurunkan skor kelengkapan — bukan error yang menghentikan sistem."

**T: "Kenapa ada file `traffic_state_builder.py` di 2 tempat?"**
> "Satu legacy (simulation/), tidak dipakai produksi — sudah
> diverifikasi lewat kode aslinya sendiri. Yang aktif ada di backend/,
> dipakai semua jalur produksi."

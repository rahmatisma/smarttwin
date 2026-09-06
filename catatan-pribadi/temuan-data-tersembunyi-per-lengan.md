# Temuan: Data Per Lengan yang "Bersembunyi" di Balik Angka Gabungan

> Catatan pribadi (bukan status tracker — lihat `docs/STATUS-DAN-SISA-KERJA.md` untuk
> itu). Ini hasil audit tanggal 6 September 2026, dipicu diskusi soal desain ulang
> halaman Riwayat Keputusan. Semua temuan sudah divalidasi manual ke kode langsung
> (dibaca sendiri, bukan tebakan), bukan cuma laporan mentah dari pencarian otomatis.

## Kenapa audit ini dilakukan

Proyek ini pernah punya masalah nyata: LOS keseluruhan simpang bisa menunjukkan "C"
(baik-baik saja) padahal lengan Utara dan Barat sebenarnya "D" (buruk) — angka
gabungan **menyembunyikan** masalah di lengan tertentu. Itu sudah ditemukan dan
diperbaiki (item P-3 di `docs/STATUS-DAN-SISA-KERJA.md`, selesai 4 September 2026).

Pertanyaannya: apa cuma itu satu-satunya tempat masalah seperti ini terjadi, atau ada
yang lain? Audit ini menyisir seluruh `backend/`, `simulation/`, `frontend/`, dan
`forecasting/` untuk mencari pola yang sama: data per lengan yang **sudah dihitung**
di suatu tempat, tapi **hilang/dibuang** sebelum sampai ke tampilan.

## Pembagian tanggung jawab

Dibagi berdasarkan halaman/area yang sedang dipegang tiap orang:

| Temuan | Pemilik | Kenapa |
|---|---|---|
| 1. Digital Twin kehilangan LOS/delay per lengan | **Yuli** | Bug-nya ada di halaman Digital Twin (dashboard utama, selector skenario) |
| 2. Notifikasi kemacetan cuma 1 lengan | **Melpi** | Pegang bagian notifikasi |
| 3. Antrean meter tanpa versi per lengan | **Saya** (Riwayat) — lihat catatan di temuan | Root cause di kode simulasi bersama (`scenario_generator.py`), tapi paling kepakai buat tab per-lengan yang sedang dikerjakan di halaman Riwayat |
| Catatan tambahan: Ringkasan Prediksi di `ForecastChart.tsx` | **Bersama (Yuli + Saya)** | Komponen ini dipakai di dashboard Digital Twin (Yuli) DAN di modal detail halaman Riwayat (Saya) — siapa pun yang duluan sempat boleh ambil |

---

## Temuan 1 (paling serius): Panel Digital Twin kehilangan LOS & delay per lengan

**Pemilik: Yuli** (halaman Digital Twin)

**Apa** — Saat user mengganti pilihan skenario di dashboard utama dari "Traffic
Realtime" ke "Baseline"/"Aggressive"/"Balanced", strip "LOS per lengan" yang
biasanya muncul **hilang begitu saja**, tanpa pesan error apa pun.

**Siapa** (komponen yang terlibat, urut dari sumber data sampai tampilan) —
1. `simulate_cycle_candidate()` di `simulation/scenario_generator.py` — sudah
   menghitung `delayByApproachSeconds`, `losByApproach`, dll untuk tiap kandidat.
2. `scenario_worker.py` — menyimpan semua data itu ke cache.
3. Skema `DigitalTwinCandidate` di `backend/app/schemas/digital_twin.py` — **tidak
   mendeklarasikan** field-field per lengan itu sama sekali, cuma field agregat
   (`avgDelaySeconds`, `los`, dst).
4. `backend/app/api/routes/digital_twin.py` — membangun respons API dari skema di
   atas, jadi otomatis membuang field yang tidak dideklarasikan.
5. `frontend/src/lib/supabaseData.ts` — tipe TypeScript-nya meniru skema backend
   yang sudah terpotong itu.
6. `candidateToRecommendation()` di `frontend/src/app/page.tsx` — mengubah data API
   jadi objek yang ditampilkan, tidak pernah mengisi `losByApproach`.
7. `RecommendationPanel.tsx` — strip LOS per lengan digerbang kondisi
   `displayRec.losByApproach && ...`; kalau kosong, otomatis tidak tampil (bukan error).

**Kapan** — Setiap kali selector skenario di dashboard diganti dari "Traffic
Realtime" ke skenario lain. Ini tombol yang terlihat di dashboard utama, bukan jalur
tersembunyi/jarang dipakai.

**Di mana** (ringkas) — `simulation/scenario_generator.py:590-604` (sumber data) →
`backend/app/schemas/digital_twin.py:17-28` (field dibuang di sini) →
`backend/app/api/routes/digital_twin.py:94` → `frontend/src/lib/supabaseData.ts:670-682`
→ `frontend/src/app/page.tsx:49-86` → `frontend/src/components/RecommendationPanel.tsx:448`.

**Kenapa ini masalah** — Ini persis pola yang sama dengan bug P-3 (LOS gabungan
menyembunyikan LOS lengan tertentu), tapi terjadi lagi di jalur yang berbeda dan
belum ada yang memperbaikinya. Kalau ini kejadian saat demo — juri klik ke skenario
"Aggressive" atau "Balanced" — dan salah satu lengan sebenarnya masih buruk, tidak
akan ada tanda apa pun yang menunjukkannya.

**Bagaimana** (arah perbaikan, belum dikerjakan) — Tambahkan 4 field per lengan
(`delayByApproachSeconds`, `losByApproach`, `queueLengthVehByApproach`,
`throughputVehByApproach`) ke skema `DigitalTwinCandidate`, lalu pastikan alurnya
sampai ke `candidateToRecommendation()` di frontend. Datanya sudah ada dari langkah 1
di atas — ini murni soal "diteruskan", bukan menghitung ulang apa pun.

---

## Temuan 2: Notifikasi kemacetan cuma melaporkan 1 lengan paling parah

**Pemilik: Melpi** (notifikasi)

**Apa** — Sistem forecast (LSTM) menghasilkan prediksi kepadatan untuk 4 lengan × 12
titik waktu ke depan (48 titik data), tapi notifikasi kemacetan cuma dikirim untuk
**1 titik tertinggi** dari semuanya — lengan lain yang sebenarnya juga di atas ambang
batas tidak dapat notifikasi sama sekali.

**Siapa** — `evaluate_once()` di `simulation/scenario_worker.py`, baris sekitar
570-583:
```python
horizon, highest = max(forecast_points, key=lambda item: float(item[1].get("densityIndex", 0) or 0))
```

**Kapan** — Setiap kali worker menjalankan siklus evaluasi (tiap 60 detik, sama
seperti alur "Kandidat yang Diuji di SUMO" yang dibahas sebelumnya).

**Di mana** — `simulation/scenario_worker.py:570-602`.

**Kenapa ini masalah** — Kalau Utara dan Barat sama-sama diprediksi padat di jam
yang sama (realistis untuk simpang 4 lengan dengan pola lalu lintas yang berkaitan),
cuma lengan dengan angka sedikit lebih tinggi yang dapat notifikasi. Operator yang
mengandalkan notifikasi tidak akan tahu lengan satunya juga bermasalah. Ini bukan
keterbatasan teknis — `notification_service.create_notification()` sudah mendukung
banyak notifikasi sekaligus (dibedakan lewat `reference_id`), cuma belum
diloop ke semua lengan yang lewat ambang batas, cuma diambil yang tertinggi saja.

**Bagaimana** (arah perbaikan, belum dikerjakan) — Ganti `max()` satu nilai jadi
loop/filter semua `(horizon, approach)` yang density-nya di atas ambang batas, kirim
notifikasi terpisah untuk masing-masing (reference_id sudah otomatis mencegah duplikat).

---

## Temuan 3: Antrean dalam satuan meter tidak pernah ada versi per lengan

**Pemilik: Saya** (halaman Riwayat Keputusan) — root cause-nya di kode simulasi
bersama (`simulation/scenario_generator.py`), bukan cuma milik satu halaman, tapi
kebutuhan langsungnya ada di tab per-lengan yang lagi dikerjakan di Riwayat, jadi
paling masuk akal dikerjakan dari sisi ini dulu. Kalau Yuli juga butuh
`avgQueueLengthMByApproach` di Digital Twin, tinggal pakai field yang sama begitu ada.

**Apa** — `avgQueueLengthM` (antrean dalam meter) cuma ada sebagai angka gabungan
seluruh simpang. Versi jumlah kendaraan per lengan (`queueLengthVehByApproach`) ada,
tapi versi meter per lengan **tidak pernah dihitung**.

**Siapa** — `simulation/scenario_generator.py`, konstanta `METERS_PER_QUEUED_VEHICLE
= 7.0` cuma dikalikan ke angka antrean **gabungan** (`queue_veh`), padahal dict per
lengan (`queue_by_approach`) ada di baris yang sama persis di fungsi itu.

**Kapan** — Selalu — ini bukan bug yang muncul di kondisi tertentu, tapi gap yang
memang ada di semua data sejak awal fitur ini dibuat.

**Di mana** — `simulation/scenario_generator.py` (fungsi `simulate_cycle_candidate`
dan `simulate_candidate`); sudah didokumentasikan jujur di komentar
`backend/app/services/history_service.py:61-73`.

**Kenapa ini beda dari Temuan 1 & 2** — Ini **bukan** data yang "hilang tanpa
disadari" — kodenya sendiri sudah punya komentar yang mengakui keterbatasan ini. Jadi
tingkat kepentingannya lebih rendah, tapi tetap berarti klaim seperti "antrean lengan
Utara sepanjang 12 meter" **tidak bisa** ditampilkan, cuma "antrean lengan Utara
sejumlah 8 kendaraan" yang bisa.

**Bagaimana** (arah perbaikan, opsional) — Kalikan `queue_by_approach` dengan
`METERS_PER_QUEUED_VEHICLE` di titik yang sama saat versi gabungannya dihitung, lalu
alirkan sebagai field baru `avgQueueLengthMByApproach` mengikuti pola field
`...ByApproach` yang sudah ada.

---

## Catatan tambahan (bukan temuan utama, cuma perlu diketahui)

**Pemilik: bersama (Yuli + Saya)** — komponen `ForecastChart.tsx` dipakai di
dashboard Digital Twin maupun di modal detail Riwayat, jadi bukan milik satu halaman.

Kotak "Ringkasan Prediksi" di `frontend/src/components/ForecastChart.tsx`
(baris 417-434, isinya "Puncak Antrean", "Antrean Terpanjang", "Rata-rata
Kepadatan") dihitung dari data **gabungan** (`series`, baris 154-157), padahal
grafik 4-garis di atasnya sudah benar menampilkan data **per lengan**
(`approachSeries`). Jadi grafiknya sudah benar, tapi 3 angka ringkasan di
bawahnya bisa tidak nyambung dengan apa yang terlihat di grafik.

---

## Yang sudah dicek dan TERBUKTI BAIK (bukan cuma belum diperiksa)

Supaya jelas ini bukan cuma daftar masalah — bagian-bagian berikut sudah ditelusuri
langsung dan datanya mengalir utuh per lengan sampai ke tampilan:

- LOS & delay per lengan di jalur **"Traffic Realtime"** (perbaikan P-3, masih bekerja).
- `queueLengthVehByApproach` & `throughputVehByApproach` di halaman Riwayat Keputusan
  (fitur yang baru saja ditambahkan & di-commit).
- `avgSpeedKmh` & `densityIndex` per lengan, dari Traffic State Builder sampai API.
- Forecast LSTM per lengan — endpoint `/api/forecast/approaches` dan grafik 4-garis
  di `ForecastChart.tsx` sudah benar per lengan (cuma kotak ringkasannya yang belum,
  lihat catatan tambahan di atas).
- Panel Digital Twin live (`DigitalTwinPanel.tsx`) — titik antrean & warna sinyal
  per lengan sudah benar, ini bukan bug, karena satu lampu lalu lintas memang wajar
  menyandikan status ke-4 lengan dalam satu string status.

---

## Ringkasan prioritas

| # | Temuan | Pemilik | Tingkat urgensi | Kenapa |
|---|---|---|---|---|
| 1 | Digital Twin kehilangan LOS/delay per lengan | Yuli | **Tinggi** | Terlihat di dashboard utama, bug sama persis dengan P-3 yang sudah pernah jadi temuan |
| 2 | Notifikasi kemacetan cuma 1 lengan | Melpi | Sedang | Bisa membuat operator kehilangan peringatan lengan lain |
| 3 | Antrean meter tidak ada versi per lengan | Saya | Rendah | Sudah didokumentasikan jujur di kode, bukan kejutan |
| — | Ringkasan Prediksi pakai data gabungan | Yuli + Saya | Sangat rendah | Cuma teks ringkasan, grafik utamanya sudah benar |

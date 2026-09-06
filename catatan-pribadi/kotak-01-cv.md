# Kotak 1-2 — Computer Vision (Deteksi & Hitung Kendaraan)

> Investigasi langsung ke kode `cv/vehicle_counter_pingit.py` (2.202
> baris, dibaca penuh strukturnya), bukan dari ringkasan dokumen.
> Disusun 6 September 2026.

---

## Cara termudah memahami ini — mulai dari sini

Lupakan dulu semua istilah teknis di bawah. Bayangkan cuma **1 CCTV**
(misal CCTV_1, lengan Selatan). Begini kejadiannya, langkah simpel:

1. **Videonya diputar oleh program** — bukan kamu yang nonton,
   programnya yang "nonton" video itu gambar demi gambar (1 gambar =
   1 frame).
2. **Program tidak lihat SEMUA gambar** — cuma sebagian (misal 1 dari
   5 gambar), biar tidak berat. Gambar yang dilewati tetap diputar di
   layar biar kelihatan normal, cuma tidak "dipikirkan".
3. **Tiap gambar yang dilihat, program pakai AI (YOLO)** buat cari:
   "di gambar ini ada kendaraan apa saja, dan di mana posisinya?"
4. **Tiap kendaraan dikasih nomor ID** — biar kalau motor yang sama
   muncul lagi di gambar berikutnya, program tahu itu motor yang sama,
   bukan motor baru (supaya tidak dihitung dobel).
5. **Ada garis batas** (sudah digambar manual sebelumnya di posisi
   tertentu). Tiap gambar, dicek: "motor ini sudah lewat garis itu
   belum?" Kalau baru lewat, dihitung **+1** untuk lengan itu.
6. **Setiap 5 detik**, program rangkum "dalam 5 detik ini ada berapa
   motor/mobil/bus/truk yang lewat garis" jadi 1 angka, ditulis 1
   baris ke **`crossing_simpang.csv`**.
7. **File ini nanti dikirim ke database** (Supabase) — lanjut ke
   cerita Bagian B (Traffic State Builder, dst).

Ulang terus langkah 1-6 sampai video habis. **Cuma itu intinya** —
video → dilihat AI → dihitung yang lewat garis → dirangkum tiap 5
detik → disimpan ke `crossing_simpang.csv`.

**3 file CSV yang dihasilkan, biar tidak ketuker:**

| File CSV | Isinya |
|---|---|
| `crossing_simpang.csv` | Kendaraan yang **lewat garis**, dirangkum tiap 5 detik |
| `percobaan_logic_simpang.csv` | Kendaraan yang **ada di dalam zona** (bukan yang lewat), tiap 5 detik |
| `snapshot_zona.csv` | Sama kayak zona di atas, tapi dicatat tiap **1 detik**, angka TERAKHIR (bukan rata-rata) — buat tampilan yang kelihatan "hidup" |

### Isi kolom asli tiap CSV (dicek langsung ke file, bukan dugaan)

**`crossing_simpang.csv`** — 1 baris = 1 kamera, 1 lengan, per jendela
5 detik, angka BULAT (hasil jumlah kejadian lewat garis):
```
timestamp,kamera,label_garis,jumlah_crossing,motor_crossing,mobil_crossing,truk_crossing,bus_crossing,frame_number
2026-08-15 16:30:10,CCTV_1,selatan,2,0,2,0,0,60
```
→ Artinya: di jendela 5 detik yang berakhir jam 16:30:10, dari CCTV_1
(lengan Selatan), ada **2 kendaraan lewat garis**, keduanya mobil,
tidak ada motor/truk/bus.

**`percobaan_logic_simpang.csv`** — 1 baris = 1 kamera, per jendela 5
detik, angka PECAHAN/DESIMAL (karena ini RATA-RATA, bukan jumlah):
```
timestamp,kamera,lengan,total_di_zona,motor_di_zona,mobil_di_zona,truk_di_zona,bus_di_zona,frame_number
2026-08-15 16:30:10,CCTV_1,selatan,9.23,1.15,6.69,0.38,1.0,60
```
→ Artinya: rata-rata dari beberapa kali "intip" dalam 5 detik itu,
ada rata-rata **9,23 kendaraan** di zona Selatan (1,15 motor, 6,69
mobil, dst — pecahan karena hasil rata-rata beberapa hitungan bulat).

**`snapshot_zona.csv`** — kolomnya SAMA PERSIS dengan file zona di
atas, tapi per 1 detik dan nilai TERAKHIR (bisa angka bulat karena
bukan rata-rata, cuma 1 bacaan apa adanya):
```
timestamp,kamera,lengan,total_di_zona,motor_di_zona,mobil_di_zona,truk_di_zona,bus_di_zona,frame_number
2026-08-15 16:30:12,CCTV_1,selatan,10,2,7,0,1,0
```
→ Artinya: pada detik itu (bacaan mentah TERAKHIR sebelum detiknya
berganti), ada 10 kendaraan di zona Selatan saat itu juga — bukan
rata-rata dari beberapa saat sebelumnya.

**Angka file asli (dicek langsung, dari rekaman 49 menit 15 Agustus
2026):** `crossing_simpang.csv` = 112.780 bytes, `percobaan_logic_simpang.csv`
= 139.618 bytes, `snapshot_zona.csv` = 551.245 bytes (10.453 baris,
dari jam 16:30:12 sampai 17:19:16 — file ini paling besar karena
ditulis tiap 1 detik, bukan tiap 5 detik).

Semua detail di bawah ini (mode batch vs upload, resolusi 1280, dst)
itu tambahan buat yang mau tahu LEBIH DALAM — bukan wajib dipahami
duluan.

---

## Ringkasan 5W1H

- **Apa:** Program yang "melihat" video CCTV, mendeteksi tiap
  kendaraan, melacaknya antar-frame, lalu menghitungnya dengan 3 cara
  berbeda sekaligus (crossing, zona kepadatan, antrean).
- **Siapa/file mana:** `cv/vehicle_counter_pingit.py` (file utama yang
  benar-benar dipakai), memakai konfigurasi dari `cv/vehicle_counter.py`
  (file "asli"/generik).
- **Kapan dijalankan:** Manual dari terminal (`python
  vehicle_counter_pingit.py ...`) untuk proses batch, ATAU otomatis di
  latar belakang lewat `cv/process_uploaded_video.py` saat ada yang
  upload video baru dari dashboard.
- **Di mana hasilnya:** 3 file CSV di `cv/output/`.
- **Kenapa perlu 3 cara hitung sekaligus:** Crossing bagus buat volume
  kendaraan lewat (dibutuhkan `trafficApproachStates.volume`), zona
  bagus buat kepadatan/antrean (kendaraan diam ditumpuk), dan keduanya
  **tidak bisa saling menggantikan** — dijelaskan sendiri di kode.
- **Bagaimana:** YOLO26s mendeteksi posisi tiap kendaraan per frame,
  ByteTrack memberi ID supaya kendaraan yang sama tidak dihitung
  berkali-kali, lalu 3 fungsi hitung berbeda jalan dari data deteksi
  yang sama itu.

---

## ✅ Temuan pertama — nama/docstring menyesatkan — SUDAH DIPERBAIKI (6 September)

**Yang ditemukan awalnya:** baris 1-8 file ini dulu bilang:

> *"SMARTTWIN — PERCOBAAN LOGIKA ZONA (bukan crossing). Salinan kerja
> dari `vehicle_counter.py` yang MENGGANTI logika hitungnya."*

Nama filenya `vehicle_counter_pingit.py` (kedengarannya seperti "skrip
resmi"), tapi docstring-nya sendiri bilang cuma "PERCOBAAN". Lebih
parah lagi — waktu saya baca lebih dalam, docstring lamanya juga
punya bagian **"YANG SENGAJA TIDAK ADA DI SINI"** yang bilang *"Tidak
ada kolom crossing... tidak ada estimasi antrean"* — padahal file ini
**PUNYA** `CROSSING_LINES`, `hitung_crossing()`, dan `hitung_antrean()`
yang aktif dipakai. Jadi bukan cuma judul yang usang, ada klaim yang
sudah terang-terangan salah dibanding isi kode sekarang. Ditambah
"Cara pakai" di docstring lama menyebut nama file yang salah
(`vehicle_counter_copy.py`, bukan `vehicle_counter_pingit.py`).

**Sudah diperbaiki langsung di kode** (bukan cuma dicatat di sini):
docstring `cv/vehicle_counter_pingit.py` ditulis ulang supaya
menyebutkan dengan benar bahwa file ini skrip produksi mode batch yang
menghasilkan 3 output sekaligus (crossing, zona, antrean), riwayat
kenapa namanya begitu tetap disimpan sebagai konteks (bukan dihapus),
dan bagian yang klaimnya salah (soal "tidak ada crossing/antrean")
sudah dibuang, diganti bagian "Keterbatasan yang masih melekat" yang
isinya cuma keterbatasan yang benar-benar masih berlaku sekarang.
Cuma perubahan komentar/dokumentasi — **tidak ada logika kode yang
diubah**, jadi aman.

---

## Alur kerja, langkah demi langkah (dengan angka detik/frame persis)

### 1. Baca 1 frame video

`state.cap.read()` — baca **1 frame** dari video (file lokal, atau
stream RTSP kalau pakai `--sumber`).

### 2. Putuskan: diproses YOLO atau dilewati?

Parameter `--langkah` (default **5**): cuma **1 dari setiap 5 frame**
yang benar-benar diproses YOLO. 4 frame lainnya cuma ditampilkan mentah
(supaya video di layar tetap terlihat mengalir mulus), **tidak ikut
dihitung**.

**Efek kecepatannya:** kalau video aslinya ~25 fps, YOLO cuma jalan
~5 kali per detik (bukan 25). Ini disengaja demi kecepatan proses —
komentar di kode sendiri bilang "~6 fps" (sedikit meleset dari hitungan
25/5=5, kemungkinan pembulatan kasar, bukan salah besar).

**Trade-off yang diakui sendiri di kode:** makin besar `--langkah`,
makin renggang jarak posisi yang dibandingkan buat deteksi crossing —
kendaraan cepat/dekat garis **bisa lompat sisi tanpa terdeteksi**.
Kalau butuh crossing akurat, disarankan turunkan ke `--langkah 1`
(proses semua frame) — tapi defaultnya tetap 5 demi kecepatan.

### 3. Deteksi + Tracking (kalau frame ini diproses)

```python
state.model.track(frame, tracker="bytetrack.yaml",
                   classes=TRACK_CLASSES, conf=CONFIDENCE,
                   imgsz=1280, ...)
```

- **Resolusi 1280** (bukan default YOLO 640) — **disengaja & terukur**:
  di resolusi 640, motor cuma kelihatan 17-21% dari yang seharusnya
  (motor kecil di ujung jauh frame hilang), padahal motor itu **79,3%**
  dari seluruh kendaraan yang lewat. Konsekuensinya: proses jadi **2-3x
  lebih lambat**, tapi dianggap perlu karena motor mayoritas mutlak di
  simpang ini.
- **ByteTrack** dipakai supaya 1 kendaraan yang sama di banyak frame
  tetap punya 1 ID (`track_id`) — tanpa ini, 1 motor bisa kehitung
  berkali-kali.

### 4. Dari hasil deteksi, dihitung 3 hal SEKALIGUS

**a) Crossing** (`hitung_crossing()`) — bandingkan posisi kendaraan
FRAME INI vs frame SEBELUMNYA (yang diproses, bukan frame video asli
kalau `--langkah`>1). Kalau tandanya (sisi kiri/kanan garis) berbalik,
berarti dia baru saja melintasi garis → dihitung 1 kali, lalu ID itu
ditandai supaya tidak dihitung dobel walau nanti bolak-balik dekat
garis.

**b) Kehadiran di zona** (`hitung_kendaraan_di_zona()`) — cek titik
tengah tiap kendaraan, apakah ada di dalam area poligon yang sudah
dikalibrasi per kamera (`cv/kalibrasi_zona.py`). Beda dari crossing:
1 kendaraan yang DIAM di zona dihitung TERUS di setiap frame selama
dia di situ (bukan cuma 1 kali).

**c) Antrean** (`hitung_antrean()`) — kendaraan dianggap "sedang
mengantre" kalau: (1) posisinya di dalam zona, (2) pergerakan
antar-frame di bawah ambang tertentu, (3) sudah "hampir diam" minimal
5 kali proses berturut-turut (~1 detik nyata, dengan `--langkah`
default). **Ambang-ambang ini secara eksplisit ditandai belum
final** — ada komentar tanggal 25 Agustus yang mengoreksi kesalahan
hitung sebelumnya, dan penutupnya: *"BUTUH DIKALIBRASI ULANG setelah
lihat hasil run sungguhan — angka ini titik awal, bukan final."*

### 5. Ditulis ke CSV — dengan 2 KECEPATAN BERBEDA (ini sering terlewat)

| File | Kecepatan tulis | Isinya |
|---|---|---|
| `crossing_simpang.csv` | **Tiap 5 detik**, RATA-RATA/akumulasi jendela | Hasil crossing (a) |
| `percobaan_logic_simpang.csv` | **Tiap 5 detik**, rata-rata | Hasil zona (b) |
| `snapshot_zona.csv` | **Tiap 1 detik**, bacaan TERAKHIR (bukan rata-rata) | Salinan hasil (b), buat tampilan yang "hidup" |

**Koreksi ke catatan Bagian B saya sebelumnya:** saya sempat menyiratkan
`snapshot_zona.csv` juga berjendela 5 detik seperti yang lain —
**ternyata tidak**, dia 1 detik dan bukan rata-rata, cuma "nilai
terakhir sebelum detik berganti". Ini beda granularitas yang perlu
diperbaiki di catatan lama.

---

## Peta kamera → lengan simpang (dan 1 kejanggalan tersembunyi)

| Kamera | Jalan | Lengan | Ada garis crossing sendiri? |
|---|---|---|---|
| CCTV_1 | Jl. Tentara Pelajar | Selatan | Ya |
| CCTV_2 | Jl. Magelang | "simpang_tengah" (proxy Utara) | Ya — **2 garis sekaligus** |
| CCTV_3 | Jl. Kyai Mojo | Barat | Ya |
| CCTV_4 | Jl. P. Diponegoro | Timur | **TIDAK ADA** |

**Kejanggalan yang perlu dicatat:** CCTV_4 (kamera Timur) **tidak
punya garis crossing sendiri sama sekali**. Sudut kameranya tidak
menangkap crossing dengan jelas. Sebagai gantinya, **volume Timur
diambil dari garis "DIPONEGORO" yang digambar di frame CCTV_2**
(karena CCTV_2 kebetulan memotret badan simpang yang juga menangkap
mulut Jl. Diponegoro). Jadi: kepadatan zona Timur dari CCTV_4, tapi
angka volume/crossing Timur dari kamera LAIN (CCTV_2). Ini dijelaskan
sadar di kode (bukan bug tersembunyi), tapi kalau juri lihat sendiri
"kenapa CCTV_4 gak ada garis crossing", jawabannya sudah siap:
keterbatasan sudut kamera, diselesaikan pakai garis dari kamera
tetangga yang framenya kebetulan menangkap mulut jalan itu juga.

**CCTV_2 juga unik** — dia dapat label lengan `"simpang_tengah"`,
BUKAN `"utara"`. Alasannya: framenya memotret badan bundaran simpang
(kendaraan berbelok segala arah), bukan ruas lurus lengan Utara murni.
Jadi anggka dari CCTV_2 itu proxy/perkiraan kepadatan Utara, bukan
pengukuran murni satu lengan.

---

## Temuan lain yang perlu jujur disebut

1. **`QUEUE_SPACE_M`** (jarak per kendaraan buat estimasi antrean
   dalam meter: motor 2m, mobil 5m, bus/truk 10m) — ditandai eksplisit
   di kode: *"ESTIMASI KESEPAKATAN TIM, BUKAN kutipan dari tabel resmi
   PKJI 2023. Jangan dipresentasikan sebagai angka standar kalau
   ditanya juri."*

2. **Bug lama yang sudah diperbaiki (25 Agustus):** `LAJUR_PER_LENGAN`
   sempat pakai key `"utara"` yang tidak pernah cocok dengan nama
   lengan asli (`"simpang_tengah"`), jadi diam-diam selalu jatuh ke
   default 1 lajur untuk Utara — padahal aslinya 2 lajur. Sudah
   diperbaiki, dicatat di komentar supaya tidak terulang.

3. **Insiden nyata (29 Agustus):** pakai `--sumber` (buat tes RTSP)
   sempat MENIMPA CSV produksi jadi 0 baris, karena file dibuka mode
   tulis-ulang di awal proses SEBELUM kamera sempat dicoba dibuka —
   gagal koneksi pun tetap menghapus data lama. **Sudah diperbaiki**:
   sekarang `--sumber` wajib menulis ke folder terpisah
   (`cv/output/_sumber_kustom/`), tidak pernah menyentuh CSV produksi.

4. **Round-robin, bukan paralel** — 4 kamera diproses bergantian
   dalam **1 thread yang sama** (1 frame CCTV_1, 1 frame CCTV_2, dst,
   ulang), bukan 4 proses berjalan bersamaan. "Bersamaan"-nya cuma
   terasa dari sisi tampilan, bukan benar-benar paralel secara
   komputasi.

5. **Jalur upload video (`process_uploaded_video.py`) pakai
   `vehicle_counter.py` yang generik**, bukan `vehicle_counter_pingit.py`
   yang sudah dikalibrasi khusus Simpang Pingit (zona, garis crossing,
   dsb, semua kalibrasi di atas ada di file `_pingit`). **Belum
   ditelusuri** seberapa besar dampaknya — kemungkinan video yang
   diupload manual lewat dashboard tidak dapat kalibrasi zona/crossing
   sedetail video produksi 4 kamera tetap. Ini PR investigasi lanjutan.

6. **⚠️ Update dari investigasi Kotak 2 (Traffic State Builder):**
   komentar di baris ~143-147 file ini (soal `WINDOW_DETIK`) menuduh
   ada *"kesalahan yang SEDANG TERJADI di
   backend/app/pipeline/traffic_state_builder.py (queue di-sum lintas
   detik)"*. Saya sudah telusuri kode backend itu baris demi baris
   (lihat `catatan-pribadi/kotak-02-traffic-state-builder.md`) — **klaim
   ini TIDAK sepenuhnya cocok** dengan kode backend yang ada sekarang:
   fungsi agregasinya sudah menyaring data per `trafficStateId` (per
   satu titik waktu) sebelum menjumlahkan, jadi tidak menjumlah lintas
   detik seperti yang dituduhkan. Kemungkinan komentar ini sudah usang
   (bug-nya sudah diperbaiki di backend tapi komentar di CV tidak ikut
   diperbarui), atau ada jalur pemanggilan lain yang belum ditemukan.
   **Belum dipastikan mana yang benar** — perlu ditanyakan langsung ke
   penulis komentarnya.

7. **Akurasi keseluruhan 48,7%** (dari validasi manual 8 sampel,
   sudah dibahas panjang sebelumnya) — pola kehilangan deteksi paling
   parah saat kondisi padat, konsisten dengan keterbatasan ID-switch
   ByteTrack.

---

## Pertanyaan juri yang mungkin muncul + jawaban siap-pakai

**T: "Kenapa akurasinya cuma 48,7%, bukan yang lebih tinggi?"**
> "Sudah kami verifikasi ke kode — bukan bug logika (rumus hitungnya
> benar), tapi keterbatasan deteksi YOLO saat kondisi padat, ID
> tracking bisa terputus. Kami naikkan resolusi inferensi ke 1280
> khusus supaya motor kecil tetap terdeteksi, tapi itu belum menutup
> seluruh gap."

**T: "Kenapa CCTV_4 (Timur) datanya campur dari kamera lain?"**
> "Sudut kamera Timur tidak menangkap garis crossing dengan jelas.
> Kami pakai garis dari CCTV_2 yang framenya kebetulan juga menangkap
> mulut Jl. Diponegoro — solusi sadar, bukan kelalaian, dan sudah
> didokumentasikan di kode."

**T: "Berapa detik data kendaraan diperbarui?"**
> "Dua kecepatan: kondisi ringkas (rata-rata volume/kepadatan)
> diperbarui tiap 5 detik, tapi ada juga tampilan 'hidup' per 1 detik
> untuk kesan real-time di visualisasi."

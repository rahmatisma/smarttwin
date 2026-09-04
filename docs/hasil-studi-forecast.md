# Hasil Studi Forecast vs Tanpa Forecast

> **Catatan versi:** tabel eksperimen di bawah dijalankan ketika kandidat
> `aggressive` masih memakai rumus lama `baseline x 1,2`. Implementasi aktif
> sekarang memakai `baseline + 1 detik` setelah sweep 28–34 detik. Hasil
> kalibrasi aktif ada di `hasil-kalibrasi-kandidat-agresif.md`; tabel lama ini
> dipertahankan sebagai audit trail, bukan sebagai hasil kode terbaru.

**Dihasilkan:** 2026-08-27T03:07:10.387619+00:00

## Metode pengujian

Satu snapshot `TrafficState` yang sama (`simpang4-pingit`, window akhir 15 Agustus 2026 17:19:20 UTC) diuji dalam dua kondisi:

1. **Tanpa forecast:** `RuleBasedEngine` memakai 100% kondisi lalu lintas saat ini.
2. **Dengan forecast:** input keputusan merupakan campuran 70% kondisi saat ini dan 30% prediksi LSTM horizon +60 detik (`forecastWeight=0.3`).

Setiap kondisi memilih satu approach prioritas, kemudian menghasilkan tiga kandidat durasi hijau untuk approach yang sama. Setiap kandidat dijalankan dalam sesi SUMO terpisah selama 90 langkah:

- **Baseline:** durasi asli hasil `RuleBasedEngine`.
- **Aggressive:** `min(60, round(baseline × 1,2))` detik. Angka +20% adalah skenario pembanding demonstrasi, bukan hasil kalibrasi lalu lintas.
- **Balanced:** `round((baseline + 15) / 2)` detik, yaitu menarik durasi baseline ke arah batas minimum 15 detik.

Pemenang adalah kandidat dengan skor terendah:

```text
score = 0,5 × (delay / delay maksimum dalam kelompok)
      + 0,5 × (antrean / antrean maksimum dalam kelompok)
```

## Mengapa memakai baseline, aggressive, dan balanced?

Tiga nama ini **bukan keluaran LSTM**. LSTM hanya memprediksi kondisi traffic.
Ketiganya adalah desain eksperimen Scenario Generator:

1. **Baseline:** keputusan asli RuleBasedEngine sebagai kontrol.
2. **Aggressive:** menambah pelayanan lengan tersibuk. Kode aktif memakai
   `min(60, baseline + 1)`; +1 detik adalah alternatif lebih panjang dengan
   degradasi terkecil pada sweep awal.
3. **Balanced:** `round((baseline + 15) / 2)`, yaitu menguji durasi yang lebih
   dekat ke minimum green 15 detik.

Literatur mendukung **prinsip umumnya**, bukan tiga nama dan rumus persis ini.
Pedoman FHWA menjelaskan green interval melalui minimum/maximum green dan
perpanjangan berdasarkan demand. Studi adaptive signal control menilai perubahan
timing melalui delay, stops, waiting time, dan ukuran efisiensi. Karena itu,
mengeksplorasi beberapa durasi di sekitar baseline dan mengujinya di SUMO masuk
akal; tetapi rumus `+1`, balanced, dan bobot seleksi 50:50 tetap heuristik
SmartTwin yang perlu validasi lebih luas, bukan formula universal.

Rujukan:

- [FHWA Traffic Signal Timing Manual, Chapter 5](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm)
- [FHWA Traffic Signal Timing and Operations Strategies](https://ops.fhwa.dot.gov/arterial_mgmt/tst_ops.htm)
- [SUMO-RL reward documentation](https://lucasalegre.github.io/sumo-rl/mdp/reward/)
- [Deep Reinforcement Learning for Traffic Light Control](https://arxiv.org/abs/1803.11115)

## Hasil seluruh kandidat

| Kondisi | Kandidat | Hijau (s) | Delay (s) | Antrean (kend.) | Antrean (m) | Throughput | LOS |
|---|---|---:|---:|---:|---:|---:|---:|
| Tanpa forecast | baseline | 60 | 15.49 | 8 | 56.00 | 7 | B |
| Tanpa forecast | aggressive | 60 | 15.49 | 8 | 56.00 | 7 | B |
| Tanpa forecast | balanced | 38 | 15.57 | 6 | 42.00 | 6 | B |
| Dengan forecast | baseline | 28 | 13.85 | 5 | 35.00 | 8 | B |
| Dengan forecast | aggressive | 34 | 14.87 | 6 | 42.00 | 8 | B |
| Dengan forecast | balanced | 22 | 13.37 | 5 | 35.00 | 9 | B |

Tanpa forecast, `baseline` dan `aggressive` sama-sama 60 detik karena baseline sudah mencapai batas maksimum. Walaupun kandidat `balanced` mempunyai delay sedikit lebih tinggi, antreannya lebih rendah sehingga skor gabungannya menjadi yang terbaik. Dengan forecast, `balanced` mempunyai delay terendah, antrean setara nilai terendah, dan throughput tertinggi sehingga terpilih dengan lebih jelas.

## Asal dan perhitungan LOS

Nilai delay berasal dari rata-rata sampel `traci.vehicle.getAccumulatedWaitingTime(vehicleId)` untuk seluruh kendaraan aktif pada setiap langkah simulasi. Nilai tersebut dipetakan ke Level of Service HCM 2000 untuk simpang bersinyal:

| LOS | Rata-rata delay per kendaraan |
|---|---:|
| A | ≤ 10 detik |
| B | > 10 sampai ≤ 20 detik |
| C | > 20 sampai ≤ 35 detik |
| D | > 35 sampai ≤ 55 detik |
| E | > 55 sampai ≤ 80 detik |
| F | > 80 detik |

Karena delay pemenang tanpa forecast adalah 15,57 detik dan dengan forecast 13,37 detik, keduanya berada pada rentang LOS B. LOS tetap B bukan berarti tidak ada perbaikan; delay membaik tetapi belum melewati batas 10 detik untuk masuk LOS A.

Metrik lain dihitung sebagai berikut:

- Antrean kendaraan: jumlah maksimum kendaraan dengan kecepatan <0,1 m/s selama simulasi.
- Antrean meter: estimasi `antrean kendaraan × 7 meter`, bukan pengukuran geometri langsung.
- Throughput: jumlah kendaraan yang selesai perjalanan (`arrived`) selama 90 langkah.

## Perbandingan kandidat pemenang

| Kondisi | Kandidat | Delay (s) | Antrean (m) | Throughput | LOS |
|---|---:|---:|---:|---:|---:|
| Tanpa forecast | balanced | 15.57 | 42.00 | 6 | B |
| Dengan forecast | balanced | 13.37 | 35.00 | 9 | B |

## Selisih (dengan forecast - tanpa forecast)

- Delay: -2.20 detik
- Antrean: -7.00 meter
- Throughput: +3 kendaraan

Nilai negatif untuk delay/antrean berarti hasil dengan forecast lebih baik. Ini satu eksperimen pada satu snapshot, sehingga belum cukup untuk klaim signifikansi statistik.

## Audit dasar ilmiah kandidat Baseline, Aggressive, dan Balanced

Bagian ini ditambahkan setelah penelusuran ulang terhadap rujukan FHWA,
SUMO-RL, dan penelitian deep reinforcement learning. Kesimpulan utamanya:
literatur mendukung **prinsip** pembatasan waktu hijau, respons terhadap demand,
dan pemilihan tindakan berdasarkan kinerja. Literatur tersebut tidak menetapkan
rumus kandidat SmartTwin secara persis.

| Kandidat | Implementasi aktif | Status dasar ilmiah |
|---|---|---|
| Baseline | `RuleBasedEngine.recommend_cycle()` | Durasi berbasis demand dengan batas minimum/maksimum; prinsipnya sejalan dengan actuated control, tetapi formula internal SmartTwin tetap perlu dikalibrasi lokal. |
| Aggressive | Lengan dengan `demandScore` tertinggi mendapat `min(60, baseline + 1)` | `+1 detik` bukan formula FHWA. Ini perturbasi eksperimen yang dipilih dari sweep lokal 28--34 detik karena merupakan penambahan dengan degradasi terkecil. |
| Balanced | Setiap lengan memakai `round((baseline + 15) / 2)` | Interpolasi 50% menuju minimum green. Rumus dan bobot 50% bukan formula baku FHWA maupun SUMO-RL; ini heuristik pencarian SmartTwin. |

FHWA menyatakan bahwa durasi hijau pada pengendali actuated dipengaruhi oleh
minimum green, maximum green, passage/gap time, detector demand, dan kebutuhan
membersihkan antrean. FHWA juga menjelaskan bahwa maximum green dapat ditaksir
dari waktu hijau minimum-delay yang dikalikan sekitar 1,25--1,50, tetapi itu
adalah cara menetapkan **maximum green**, bukan pembenaran untuk kandidat
`baseline + 1` atau `(baseline + 15) / 2`.

SUMO-RL memakai perubahan cumulative delay sebagai reward bawaan. Penelitian
DRL yang dirujuk juga memodelkan perubahan timing sebagai action dan selisih
cumulative waiting time antarsiklus sebagai reward. Keduanya mendukung pola
"uji tindakan lalu nilai dampaknya", bukan formula tetap untuk kandidat
Aggressive atau Balanced.

Konsekuensi pelaporan:

- Jangan menyebut rumus Aggressive/Balanced sebagai "rumus FHWA".
- Sebut keduanya **kandidat heuristik yang diuji secara empiris di SUMO**.
- Dasar pemilihannya adalah hasil delay, antrean, dan throughput pada horizon
  yang sama, bukan nama kandidatnya.
- Validitas eksternal masih terbatas karena sweep agresif berasal dari satu
  snapshot dan studi multi-snapshot masih berasal dari satu sesi rekaman.

Rujukan audit:

- [FHWA Traffic Signal Timing Manual, Chapter 5](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm)
- [FHWA Traffic Signal Timing and Operations Strategies](https://ops.fhwa.dot.gov/arterial_mgmt/tst_ops.htm)
- [SUMO-RL reward documentation](https://lucasalegre.github.io/sumo-rl/mdp/reward/)
- [Deep Reinforcement Learning for Traffic Light Control](https://arxiv.org/abs/1803.11115)

## Rencana pembuktian kesesuaian SUMO terhadap PKJI 2023

Tujuan studi yang dapat dipertanggungjawabkan dirumuskan sebagai berikut:

> Membandingkan kapasitas dan tundaan per pendekat yang dihasilkan model
> mikrosimulasi SUMO dengan hasil perhitungan analitis PKJI 2023 pada geometri,
> arus, komposisi kendaraan, dan waktu sinyal yang sama; kemudian mengukur
> besar selisih keduanya menggunakan kriteria penerimaan yang ditetapkan
> sebelum pengujian.

Kata **sesuai** di sini berarti hasil SUMO berada dalam toleransi benchmark
PKJI yang ditetapkan penelitian. PKJI 2023 tidak menetapkan ambang resmi untuk
"akurasi simulator", sehingga toleransi tidak boleh diklaim sebagai ketentuan
PKJI. Pernyataan "memenuhi standar Indonesia" hanya boleh dipakai untuk
parameter kinerja yang memang memiliki kriteria PKJI, misalnya kriteria desain
umum `DJ <= 0,85`, bukan untuk menyatakan dua perangkat hitung identik.

### 1. Data masukan yang wajib dikumpulkan

Gunakan periode survei representatif satu jam dan catat per pendekat:

- geometri: lebar efektif, jumlah/lajur masuk, median, gradien, jarak parkir,
  dan tipe pendekat terlindung atau terlawan;
- lingkungan: ukuran kota dan kelas hambatan samping;
- arus gerakan lurus, belok kiri, dan belok kanan menurut jenis kendaraan;
- komposisi Mobil Penumpang (MP), Kendaraan Sedang (KS), dan Sepeda Motor
  (SM), lalu konversi `kend/jam` menjadi `SMP/jam` memakai EMP PKJI untuk tipe
  pendekat yang sesuai;
- fase, urutan fase, waktu hijau, kuning, merah-semua, dan waktu siklus aktual;
- antrean serta tundaan perjalanan lapangan sebagai data kalibrasi independen.

Data CV SmartTwin belum otomatis mencukupi semua butir ini. Khususnya, hitungan
crossing perlu dipisahkan menurut pendekat, gerakan, dan kelas PKJI; lebar
efektif serta faktor lingkungan harus diukur atau ditetapkan melalui survei.

### 2. Perhitungan benchmark PKJI 2023

Lakukan per pendekat menggunakan formulir/prosedur Simpang APILL PKJI:

```text
J  = J0 x FHS x FUK x FG x FP x FBKi x FBKa
C  = J x (wH / s)
DJ = q / C
T  = TLL + TG
TI = sum(q_i x T_i) / q_total
```

Keterangan ringkas: `J` arus jenuh terkoreksi, `C` kapasitas pendekat,
`wH` waktu hijau, `s` waktu siklus, `q` arus dalam SMP/jam, `DJ` derajat
kejenuhan, `TLL` tundaan lalu lintas, `TG` tundaan geometri, dan `TI` tundaan
rata-rata simpang. Lengkapi pula panjang antrean dan jumlah kendaraan terhenti
agar diagnosis tidak hanya bergantung pada satu angka.

### 3. Menyamakan eksperimen SUMO

- Bangun geometri, jumlah lajur, gerakan belok, kecepatan, dan program sinyal
  yang sama dengan input PKJI.
- Masukkan demand per pendekat dalam `SMP/jam` yang sudah dipetakan kembali ke
  komposisi kendaraan SUMO; jangan memasukkan total hitungan dua arah sebagai
  demand satu pendekat.
- Jalankan minimal 15 menit warm-up lalu satu jam pengukuran.
- Gunakan sekurangnya 10 seed acak untuk setiap periode agar hasil tidak
  bergantung pada satu pola keberangkatan kendaraan.
- Ukur kapasitas SUMO dari arus kendaraan yang melewati garis henti. Untuk uji
  kapasitas, berikan demand cukup tinggi dan hitung `J_SUMO` saat hijau, lalu
  `C_SUMO = J_SUMO x (wH/s)`.
- Hitung seluruh hasil per pendekat dan dalam satuan SMP, bukan hanya jumlah
  kendaraan mentah seluruh jaringan.

### 4. Menyamakan definisi tundaan

Metrik aktif studi ini memakai
`traci.vehicle.getAccumulatedWaitingTime()`. Nilai tersebut terutama mengukur
waktu berhenti dan **belum ekuivalen** dengan tundaan total PKJI yang terdiri
dari tundaan lalu lintas dan tundaan geometri. Karena itu, angka delay pada
tabel lama di atas belum dapat langsung dipakai sebagai bukti kesesuaian PKJI.

Untuk studi PKJI, simpan sekurangnya:

- `timeLoss` SUMO per kendaraan sebagai selisih terhadap perjalanan bebas;
- waiting time sebagai metrik tambahan, bukan pengganti tundaan total;
- waktu masuk/keluar dan pendekat asal setiap kendaraan;
- rerata tertimbang SMP per pendekat dan seluruh simpang.

Definisi operasional tundaan SUMO harus ditulis sebelum pengujian dan digunakan
secara konsisten pada semua scenario.

### 5. Analisis kesesuaian

Untuk setiap pendekat, periode, dan scenario, laporkan:

| Parameter | PKJI | Rerata SUMO | 95% CI SUMO | Selisih absolut | Selisih relatif |
|---|---:|---:|---:|---:|---:|
| Kapasitas (SMP/jam) |  |  |  |  |  |
| Derajat kejenuhan |  |  |  |  |  |
| Tundaan (det/SMP) |  |  |  |  |  |
| Panjang antrean (m) |  |  |  |  |  |

Tetapkan kriteria penerimaan **sebelum** melihat hasil. Contoh kriteria proyek
yang dapat diuji, tetapi bukan ambang resmi PKJI: galat relatif kapasitas paling
besar 10%, galat tundaan paling besar 15% atau 5 det/SMP, serta kesimpulan
`DJ <= 0,85`/`DJ > 0,85` yang sama antara SUMO dan PKJI. Gunakan juga MAE,
MAPE (hindari pembagi mendekati nol), bias, dan interval kepercayaan antar-seed.

### 6. Validasi lapangan dan bentuk klaim akhir

PKJI adalah benchmark analitis, sedangkan data lapangan adalah acuan empiris.
Pembuktian terkuat menggunakan tiga sisi:

```text
observasi lapangan
       |          \
       v           v
     PKJI <-----> SUMO
```

Kalibrasikan parameter SUMO dengan satu bagian data lapangan, lalu validasikan
pada periode lain yang tidak dipakai saat kalibrasi. Jangan mengubah parameter
setelah melihat hasil periode validasi.

Jika kriteria terpenuhi, klaim yang aman adalah:

> Pada periode dan kondisi yang diuji, keluaran kapasitas dan tundaan model
> SUMO berada dalam toleransi penelitian terhadap perhitungan PKJI 2023, dan
> klasifikasi pemenuhan kriteria derajat kejenuhan konsisten.

Jika hanya PKJI dan SUMO yang dibandingkan tanpa data lapangan, gunakan istilah
**verifikasi silang terhadap benchmark PKJI**, bukan "validasi kondisi nyata".

Rujukan utama PKJI:

- [Direktorat Jenderal Bina Marga -- PKJI 2023 (09/P/BM/2023)](https://binamarga.pu.go.id/index.php/nspk/detail/09pbm2023-pedoman-kapasitas-jalan-indonesia-)
- [Dokumen resmi PKJI 2023](https://binamarga.pu.go.id/uploads/files/1942/09pbm2023-pedoman-kapasitas-jalan-indonesia-.pdf)

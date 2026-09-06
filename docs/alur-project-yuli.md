# Penjelasan Alur Project SmartTwin untuk Yuli

## 1. Gambaran Umum

SmartTwin adalah sistem untuk membantu memantau dan mengatur lalu lintas di
Simpang Empat Pingit, Yogyakarta. Sistem ini menerima video CCTV, membaca
kendaraan yang terlihat, mengubah hasil pembacaan menjadi informasi lalu lintas,
menguji beberapa pengaturan lampu lalu lintas di simpang virtual, kemudian
menampilkan hasilnya di dashboard.

Sederhananya, alurnya seperti ini:

```text
Video CCTV
    ↓
YOLO membaca kendaraan
    ↓
ByteTrack mengikuti kendaraan agar tidak dihitung berulang
    ↓
Data kendaraan dirangkum menjadi kondisi lalu lintas
    ↓
Data disimpan dan dibaca oleh backend
    ↓
Sistem membuat beberapa pilihan waktu lampu hijau
    ↓
Pilihan diuji di simulasi SUMO
    ↓
Pilihan terbaik dan kondisi lalu lintas ditampilkan di dashboard
```

Tujuan akhirnya bukan hanya menghitung kendaraan. Sistem juga mencoba menjawab
pertanyaan: **dengan kondisi lalu lintas saat ini, pengaturan lampu mana yang
paling masuk akal dan bagaimana hasilnya jika diuji di simpang virtual?**

## 2. Alur Sesuai Gambar Arsitektur

Gambar arsitektur project dapat dibaca dari kiri ke kanan.

### Kotak 1: Traffic Monitoring Data

Ini adalah bahan awal sistem, yaitu video dari kamera CCTV. Dalam project ini,
video rekaman digunakan untuk demo dan pengujian. Program juga sudah disiapkan
agar dapat menerima sumber video lain, termasuk stream RTSP, jika akses kamera
langsung tersedia.

Satu lokasi dapat memiliki beberapa kamera. Setiap kamera dikaitkan dengan
salah satu lengan simpang: Utara, Selatan, Timur, atau Barat.

### Kotak 2: YOLO + ByteTrack

Bagian ini berada di directory `cv/`. Program utama yang digunakan adalah
`vehicle_counter_pingit.py`.

Cara mudah memahaminya:

1. Video dibaca gambar demi gambar.
2. YOLO mencari kendaraan pada gambar.
3. Kendaraan dikelompokkan menjadi motor, mobil, bus, atau truk.
4. Setiap kendaraan diberi nomor ID oleh ByteTrack.
5. ID tersebut membantu sistem mengenali kendaraan yang sama pada gambar
   berikutnya, sehingga satu kendaraan tidak dihitung berkali-kali.
6. Sistem melihat apakah kendaraan melewati garis hitung.
7. Sistem juga melihat kendaraan yang berada di area tertentu untuk memperkirakan
   kepadatan dan antrean.

Ada tiga hasil penting dari pembacaan video:

| Hasil | Arti sederhana | Kegunaan |
|---|---|---|
| Crossing | Kendaraan yang melewati garis hitung | Mengukur arus kendaraan |
| Zona | Kendaraan yang terlihat berada di area kamera | Mengukur kondisi kepadatan |
| Antrean | Kendaraan di zona yang bergerak sangat sedikit | Memperkirakan antrean |

Hasil ini disimpan sementara sebagai CSV di `cv/output/`. File crossing
menunjukkan kendaraan yang benar-benar melewati garis. File snapshot zona
menunjukkan keadaan kendaraan yang terlihat pada saat tertentu. Keduanya tidak
boleh dianggap sebagai angka yang sama, karena satu mengukur arus dan satu lagi
mengukur keberadaan kendaraan.

### Catatan penting tentang hasil YOLO

Hasil YOLO dan ByteTrack menjadi dasar semua tahap setelahnya. Jika ada
kendaraan yang tidak terbaca ketika kondisi sangat padat, angka pada tahap
berikutnya juga dapat ikut berubah. Validasi manual project menunjukkan rata-rata
akurasi crossing 48,7% pada delapan sampel. Karena itu, angka sistem sebaiknya
disebut sebagai hasil pemantauan atau estimasi, bukan hitungan lapangan yang
sempurna.

## 3. Traffic State Builder

Bagian ini berada di `backend/app/pipeline/traffic_state_builder.py`.

Traffic State Builder bertugas mengubah banyak catatan kecil dari YOLO menjadi
ringkasan yang lebih mudah dipakai. Data biasanya dirangkum dalam jendela waktu
5 detik.

Contohnya, dari banyak catatan kendaraan pada lengan Selatan, sistem membuat
ringkasan seperti:

- berapa kendaraan yang lewat;
- berapa motor, mobil, bus, dan truk yang terlihat;
- berapa kendaraan yang sedang mengantre;
- berapa perkiraan panjang antrean;
- seberapa penuh area pengamatan terlihat; dan
- kecepatan rata-rata, jika suatu saat sumber data kecepatan sudah tersedia.

Ringkasan ini dibuat untuk setiap lengan simpang. Bentuk datanya disebut
`TrafficState`, yaitu kondisi lalu lintas pada satu waktu tertentu.

Hal yang perlu dipahami adalah `avgSpeedKmh` masih kosong (`null`) karena data
CV saat ini belum mengukur kecepatan dalam jarak dunia nyata. Nilai kosong ini
lebih jujur daripada mengisinya dengan nol, karena nol dapat disalahpahami
sebagai kendaraan benar-benar berhenti.

## 4. Backend dan Database

Backend berada di directory `backend/` dan menggunakan FastAPI. Backend dapat
dianggap sebagai penghubung atau penerima data di tengah sistem.

Tugas utamanya adalah:

- menerima dan merapikan data dari proses CV;
- menyimpan data ke Supabase PostgreSQL;
- menyediakan data lalu lintas kepada frontend;
- menyediakan status lampu lalu lintas;
- meminta atau menjalankan forecast;
- menghubungkan data lalu lintas dengan scenario generator dan SUMO; dan
- mengirim hasil rekomendasi serta metrik simulasi ke dashboard.

Beberapa bagian penting di dalamnya:

| Lokasi | Peran |
|---|---|
| `app/api/routes/` | Pintu API yang dipanggil frontend |
| `app/services/` | Aturan pengambilan data dan pembuatan rekomendasi |
| `app/pipeline/` | Penyusunan data mentah menjadi Traffic State |
| `app/schemas/` | Bentuk data yang boleh keluar-masuk API |
| `app/db/` | Model dan akses data database |
| `app/core/` | Pengaturan umum, termasuk konfigurasi dan akses |
| `tests/` | Pemeriksaan agar backend tetap berjalan benar |

Di database, data kendaraan tidak hanya disimpan sebagai satu angka besar.
Sistem menyimpan waktu pengamatan, simpang, lengan, jumlah kendaraan, antrean,
dan kepadatan. Kemudian data tersebut dirangkum menjadi data kondisi per lengan
yang siap dibaca oleh simulasi dan dashboard.

## 5. Forecasting atau Peramalan

Bagian peramalan berada di directory `forecasting/` dan layanan pemanggilnya
berada di backend.

Tujuan forecasting adalah memperkirakan jumlah kendaraan beberapa saat ke
depan berdasarkan riwayat kondisi sebelumnya. Idenya, sistem tidak hanya
menunggu kondisi menjadi macet, tetapi dapat melihat kemungkinan perubahan
kondisi lebih awal.

Project memiliki percobaan model LSTM dari beberapa dataset. Model tersebut
berhasil dilatih dan dievaluasi pada dataset PeMS04 dan TMU, tetapi dataset itu
berasal dari sensor jalan di luar negeri, bukan dari simpang bersinyal
Indonesia. Karena itu, hasilnya belum boleh dianggap sebagai prediksi final
untuk Simpang Pingit.

Dalam alur aplikasi, jika forecast belum tersedia atau tidak dapat digunakan,
sistem menggunakan volume terakhir sebagai cadangan. Dengan begitu, dashboard
dan rekomendasi tetap dapat berjalan.

## 6. Scenario Generator

Scenario generator berada di directory `simulation/`. Fungsinya membuat
beberapa pilihan pengaturan lampu lalu lintas berdasarkan kondisi yang masuk.

Saat ini terdapat tiga jenis kandidat utama:

| Kandidat | Penjelasan mudah |
|---|---|
| Baseline | Pilihan pembanding dengan aturan dasar |
| Aggressive | Memberi perhatian lebih besar pada lengan yang permintaannya tinggi |
| Balanced | Membagi waktu hijau secara lebih seimbang sesuai kebutuhan lengan |

Kandidat Aggressive dan Balanced menggunakan perhitungan berbasis PKJI 2023.
Baseline dipertahankan sebagai pembanding agar sistem dapat melihat apakah
pilihan baru memberikan hasil yang lebih baik daripada aturan dasar.

Setiap kandidat berisi rencana seperti urutan lengan yang mendapat lampu hijau,
lama lampu hijau, lama lampu kuning, dan panjang satu siklus lampu.

## 7. Digital Twin dengan SUMO

SUMO adalah simpang virtual yang meniru kondisi lalu lintas. File jaringan
utamanya berada di `simulation/network/` dan menggambarkan Simpang Pingit.

Cara kerjanya:

1. Sistem mengambil kondisi lalu lintas dari database.
2. Sistem memasukkan permintaan kendaraan ke simpang virtual.
3. Satu kandidat pengaturan lampu dijalankan.
4. SUMO mencatat apa yang terjadi pada kendaraan.
5. Proses yang sama dilakukan untuk kandidat lain.
6. Hasil setiap kandidat dibandingkan.

SUMO membantu tim menguji rencana lampu tanpa langsung mengubah lampu di jalan
asli. Metrik yang diperhatikan antara lain:

- rata-rata waktu tunggu kendaraan;
- panjang antrean;
- jumlah kendaraan yang berhasil lewat;
- tingkat pelayanan atau LOS; dan
- hasil setiap lengan secara terpisah.

Dengan cara ini, sistem tidak hanya berkata “gunakan skenario Balanced”, tetapi
juga dapat menunjukkan alasan berdasarkan hasil pengujian simulasi.

## 8. Decision Engine dan Rekomendasi

Bagian pengambilan keputusan berada di `decision_engine/` dan terhubung ke
backend.

Peran decision engine adalah memilih atau menyusun rekomendasi pengaturan lampu
berdasarkan kondisi lalu lintas. Untuk penggunaan utama saat ini, sistem masih
menggunakan rule-based engine dan scenario generator.

PPO sudah memiliki kode lingkungan, training, evaluasi, dan integrasi. Namun
PPO belum menjadi pilihan default karena hasilnya masih harus diperlakukan dengan
hati-hati dan checkpoint model tidak selalu tersedia di setiap komputer.

Jadi, penjelasan yang aman untuk presentasi adalah: **sistem produksi saat ini
menggunakan aturan dan hasil scenario generator, sedangkan PPO merupakan jalur
eksperimen atau pilihan lanjutan yang dapat diaktifkan secara khusus.**

## 9. Hasil yang Masuk ke Dashboard

Frontend berada di directory `frontend/` dan menggunakan Next.js. Dashboard
adalah tujuan akhir dari seluruh alur project.

Dashboard mengambil data dari backend dan Supabase, lalu menyajikannya dalam
bentuk yang mudah dibaca operator. Halaman dan komponen pentingnya meliputi:

| Bagian dashboard | Isi yang ditampilkan |
|---|---|
| Dashboard utama | Ringkasan kondisi simpang dan metrik utama |
| Camera Feed | Video atau sumber kamera yang sedang dipantau |
| Traffic State | Jumlah kendaraan, antrean, dan kepadatan per lengan |
| Signal Status | Lengan yang sedang mendapat giliran serta sisa waktunya |
| Recommendation | Saran fase dan durasi lampu hijau |
| Forecast | Perkiraan kondisi lalu lintas berikutnya bila tersedia |
| Digital Twin | Visualisasi kendaraan dan lampu di SUMO |
| Hasil simulasi | Delay, antrean, throughput, dan LOS |
| History | Riwayat rekomendasi dan perbandingan antar siklus |
| Settings dan Account | Pengaturan serta akses pengguna |

Pada dashboard, pengguna tidak perlu melihat proses teknis di belakang layar.
Pengguna cukup melihat keadaan simpang, memahami lengan mana yang lebih padat,
melihat status lampu, dan membandingkan hasil beberapa skenario.

## 10. Urutan Data Sampai Tampil di Layar

Berikut contoh alur lengkap dari awal sampai akhir:

1. CCTV merekam kendaraan di simpang.
2. YOLO mendeteksi kendaraan pada frame yang diproses.
3. ByteTrack menjaga agar kendaraan yang sama memiliki ID yang sama.
4. Program menghitung kendaraan yang melewati garis dan kendaraan yang berada
   di zona.
5. Hasil per beberapa detik disimpan sebagai data mentah.
6. Backend menggabungkan data tersebut menjadi kondisi Utara, Selatan, Timur,
   dan Barat.
7. Data kondisi disimpan di Supabase dan dapat dibaca oleh layanan lain.
8. Forecast, jika tersedia, memperkirakan kondisi berikutnya.
9. Scenario generator membuat Baseline, Aggressive, dan Balanced.
10. SUMO menjalankan dan membandingkan ketiga pilihan tersebut.
11. Decision engine dan layanan rekomendasi memilih hasil yang akan ditampilkan.
12. Frontend mengambil data melalui API atau Supabase.
13. Dashboard menampilkan angka lalu lintas, status sinyal, rekomendasi, dan
    hasil simulasi kepada pengguna.

## 11. Penjelasan Directory Project

| Directory | Isi dan fungsi utama |
|---|---|
| `cv/` | Membaca video, deteksi YOLO, tracking ByteTrack, crossing, zona, dan antrean |
| `backend/` | API, pengolahan data, database, status sinyal, forecast, dan rekomendasi |
| `forecasting/` | Dataset, persiapan data, training, evaluasi, dan percobaan LSTM |
| `simulation/` | Network SUMO, pembuatan kandidat, worker, dan pengukuran hasil simulasi |
| `decision_engine/` | Aturan keputusan, PPO, training, evaluasi, dan pemilihan engine |
| `frontend/` | Dashboard Next.js, kamera, digital twin, rekomendasi, forecast, dan riwayat |
| `docs/` | Kontrak data, cara kerja, SOP demo, status, audit, dan hasil pengujian |
| `scripts/` | Script pendukung untuk menjalankan atau memeriksa bagian project |
| `docker/` | Berkas pendukung bila project dijalankan dengan Docker |
| `cache/` | Data sementara hasil proses yang dipakai untuk menjaga tampilan tetap responsif |
| `catatan-pribadi/` | Catatan penjelasan dan pembelajaran internal tiap bagian project |

File di root project seperti `run_ingest.py` membantu memindahkan data hasil CV
ke database. File `requirements*.txt` berisi daftar kebutuhan program untuk
bagian-bagian project.

## 12. Kesimpulan Singkat untuk Presentasi

SmartTwin mengubah video CCTV menjadi informasi lalu lintas yang dapat dipakai
untuk mengambil keputusan. YOLO dan ByteTrack membaca serta mengikuti kendaraan.
Traffic State Builder merangkum hasilnya per lengan simpang. Backend menyimpan
dan menyediakan data tersebut. Scenario generator membuat beberapa pilihan
pengaturan lampu, lalu SUMO menguji pilihan itu di simpang virtual. Hasil
terbaik, status lampu, kondisi lalu lintas, dan metrik simulasi akhirnya
ditampilkan pada dashboard agar mudah dipantau oleh pengguna.

Kalimat paling sederhananya:

> **Dari video CCTV, sistem menghitung kendaraan, memahami kondisi simpang,
> menguji pilihan pengaturan lampu di simulasi, lalu menampilkan hasil dan
> rekomendasinya di dashboard.**

## 13. Catatan Status

Penjelasan ini mengikuti kondisi project yang tercatat pada 6 September 2026.
Untuk status pekerjaan paling terbaru, bukti pengujian, dan pekerjaan yang masih
tersisa, gunakan `docs/STATUS-DAN-SISA-KERJA.md` sebagai sumber utama.
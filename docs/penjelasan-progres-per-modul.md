# Penjelasan Progres Per Modul — Bahan Demo & Presentasi

> 🎤 **Ini bahan PENJELASAN, bukan pelacak status.** Angka dan status di sini bersumber dari **[`STATUS-DAN-SISA-KERJA.md`](STATUS-DAN-SISA-KERJA.md)** — kalau suatu saat berbeda, **dokumen itu yang benar**, bukan yang ini. Tujuan dokumen ini cuma satu: membantu menjelaskan tiap modul secara runtut saat demo ke dosen pembimbing/juri.

**Kondisi per 29 Agustus 2026: ≈87% harfiah / ≈90% fungsional.**

Tiap modul di bawah punya pola sama: **apa fungsinya → sudah sejauh mana → buktinya apa → batasannya apa.** Bagian "batasan" jangan dilewati — justru itu yang paling menunjukkan kualitas kerja riset.

---

## Kotak 1 — Traffic Monitoring Data (Sumber Video) — 100%

**Fungsinya:** menyediakan rekaman lalu lintas sebagai masukan sistem.

**Sudah sejauh mana:** 4 kamera CCTV Simpang Pingit, rekaman 43 menit, terproses penuh (538 jendela waktu per kamera, nol error).

**Buktinya:** `cv/videos/CCTV_1..4.mp4`, hasil di `cv/output/`.

**Yang perlu dijelaskan jujur:** sistem memproses **rekaman**, bukan siaran langsung. Tapi ini **keputusan, bukan keterbatasan** — antarmuka masukannya sudah menerima RTSP maupun file secara identik (parameter `--sumber`, sudah diuji: URL RTSP diterima dan gagal di tahap koneksi, bukan ditolak sistem). Kami pakai rekaman karena tidak ada akses ke stream CCTV operasional Dishub.

---

## Kotak 2 — YOLO + ByteTrack (Deteksi & Pelacakan) — 60%

**Fungsinya:** mendeteksi kendaraan di tiap frame dan melacaknya antar-frame, lalu menghitung yang melintasi garis hitung.

**Sudah sejauh mana:** YOLO26s + ByteTrack, resolusi inferensi 1280 (bukan 640 — karena motor di kejauhan hilang di resolusi rendah, padahal motor 79,3% dari seluruh arus). Model terpisah per kamera supaya pelacakan tidak bocor antar-video.

**Buktinya:** `cv/vehicle_counter_pingit.py`, hasil hitungan di `cv/output/crossing_simpang.csv` (2.152 baris).

**Yang perlu dijelaskan jujur — ini angka terpenting untuk ditanya duluan:**

> **Akurasi penghitungan 48,7%** (rata-rata 8 sampel, divalidasi manual — hitung mata vs hitung sistem). Rentangnya lebar: 22% sampai 96%.

Kenapa segitu, sudah kami investigasi — bukan sekadar "belum tahu":
1. **Kendaraan cepat/jauh telat terdeteksi.** Sistem butuh posisi frame sebelumnya untuk tahu ada yang "melintas". Kalau kendaraan baru terdeteksi setelah lewat garis, lintasannya tidak tercatat.
2. **Motor berdempetan tidak terpisah.** YOLO gagal memisahkan motor yang bertumpuk rapat jadi objek individual.

Buktinya pola ini nyata: sampel dengan kendaraan renggang mencapai **96,1%**, sampel padat turun ke **35–40%**.

**Sudah dicoba diperbaiki, hasilnya jujur dilaporkan:** menurunkan ambang deteksi (0.35→0.25) ternyata **memperburuk** (50,8%→36,9%), jadi dibatalkan. Dokumen lengkap: [`hasil-validasi-akurasi-cv.md`](hasil-validasi-akurasi-cv.md).

---

## Kotak 3 — Traffic State Builder — 90%

**Fungsinya:** mengubah deteksi per-kendaraan jadi ringkasan per-lengan tiap 5 detik: volume, panjang antrean, kepadatan, kecepatan rata-rata.

**Sudah sejauh mana:** jalan penuh, dua sumber digabung — `crossing_simpang.csv` (aliran/kendaraan lewat) + `snapshot_zona.csv` (kehadiran/kepadatan, 10.452 baris).

**Buktinya:** `backend/app/pipeline/cv_csv_bridge.py` → tabel `trafficStates` di Supabase.

**Yang perlu dijelaskan jujur:** lengan **utara** diwakili zona badan simpang (`simpang_tengah`) sebagai proxy, karena sudut CCTV_2 menangkap badan simpang, bukan lengan utara terpisah. Ini keterbatasan sudut kamera, sudah dicatat di metadata model.

---

## Kotak 4 — Virtual Intersection (Model SUMO) — 100%

**Fungsinya:** kembaran digital simpang di simulator SUMO — tempat menguji skenario lampu sebelum diterapkan.

**Sudah sejauh mana:** selesai penuh. Network **asli Simpang Pingit** dari OpenStreetMap (bukan simpang generik), TLS id `SIMPANG_CENTER`. Program lampu dipasang dinamis lewat TraCI: 8 fase (4 hijau adaptif + 4 kuning).

**Buktinya:** `simulation/network/simpang4_pingit.net.xml.gz`, koordinat asli 110.358–110.364 BT.

**Poin kuat untuk disampaikan:** program lampunya **tidak statis** — durasi hijau tiap lengan dipasang ulang dari keputusan sistem, bukan jadwal tetap bawaan peta.

---

## Kotak 5 — Realtime Traffic State — 90%

**Fungsinya:** menyediakan kondisi lalu lintas terkini ke seluruh sistem.

**Sudah sejauh mana:** backend membaca Supabase tiap permintaan, dashboard polling tiap 5 detik.

**Yang perlu dijelaskan jujur:** ini "realtime terhadap rekaman" — dashboard memutar data mengikuti posisi video yang sedang diputar, bukan jam dinding. Konsisten dengan Kotak 1.

---

## Kotak 6 — Traffic Forecast (LSTM) — 92%

**Fungsinya:** memprediksi kondisi lalu lintas **60 detik ke depan**, supaya keputusan lampu tidak cuma bereaksi tapi juga antisipatif.

**Sudah sejauh mana:** model LSTM per-lengan (satu jaringan, 8 fitur masukan termasuk penanda lengan), memprediksi 12 langkah × 5 detik. Sudah tersambung ke pengambil keputusan, bobot 30%.

**Buktinya — dua tingkat:**
1. **Model mengalahkan tebakan naif** (MAE **1,65** vs **2,30**) — "tebakan naif" = asumsi kondisi berikutnya sama dengan sekarang.
2. **Dampaknya diuji, bukan diasumsikan:** pada 10 snapshot berbeda, dengan forecast vs tanpa forecast — delay membaik **10 dari 10**, antrean **9 dari 10**, throughput **10 dari 10**. Dokumen: [`hasil-studi-forecast-multi-snapshot.md`](hasil-studi-forecast-multi-snapshot.md).

**Yang perlu dijelaskan jujur:** data uji model masih kecil (16 sequence), dan data latih baru dari 1 sesi rekaman 45 menit. Karena itu bobot forecast sengaja dibuat **konservatif 30%** — sistem tetap 70% berpegang pada kondisi aktual. Itu keputusan sadar, bukan kelalaian.

---

## Kotak 7 — Scenario Generator — 90%

**Fungsinya:** membuat beberapa pilihan pengaturan lampu untuk diuji, bukan langsung memakai satu tebakan.

**Sudah sejauh mana:** menghasilkan **3 kandidat** tiap keputusan — `baseline` (hasil perhitungan langsung), `aggressive` (+1 detik ke lengan tersibuk), `balanced` (ditarik lebih merata).

**Buktinya:** `simulation/scenario_generator.py`.

**Poin kuat:** angka `+1 detik` pada kandidat agresif **bukan tebakan**. Awalnya +20% (ilustratif), lalu diuji sapuan 28–34 detik di SUMO — ternyata semua penambahan memperburuk delay, dan +1 detik degradasinya paling kecil. Dokumen: [`hasil-kalibrasi-kandidat-agresif.md`](hasil-kalibrasi-kandidat-agresif.md).

---

## Kotak 8 — Traffic Simulation — 92%

**Fungsinya:** menjalankan tiap kandidat di SUMO untuk melihat dampaknya **sebelum** dipakai di lampu sungguhan.

**Sudah sejauh mana:** tiap kandidat dijalankan 90 langkah simulasi, dengan horizon yang disamakan supaya kandidat berdurasi pendek tidak diuntungkan secara tidak adil.

**Buktinya — sudah divalidasi, bukan sekali jalan:** 3 snapshot × 3 seed = **9 run per kandidat**. Kandidat `balanced` menang **7 dari 9**. Dokumen: [`hasil-validasi-multisnapshot-multiseed.md`](hasil-validasi-multisnapshot-multiseed.md).

**Poin kuat:** ini menjawab "apakah hasilnya cuma kebetulan?" — kami uji berulang dengan seed berbeda, bukan sekali lalu diklaim.

---

## Kotak 9 — Performance Analysis (Delay/Antrean/Throughput/LOS) — 90%

**Fungsinya:** mengukur seberapa baik tiap kandidat.

**Sudah sejauh mana:** keempat metrik yang ada di diagram semuanya dihitung nyata dari simulasi:

| Metrik | Dari mana |
|---|---|
| Delay | Akumulasi waktu tunggu kendaraan di SUMO |
| Panjang antrean | Jumlah kendaraan berhenti (definisi "halting" SUMO) |
| Throughput | Kendaraan yang selesai perjalanan |
| **LOS** | **Standar HCM 2000** (kelas A–F dari delay rata-rata) |

**Yang perlu dijelaskan jujur:** konversi antrean ke meter memakai asumsi **7 meter per kendaraan** — estimasi, bukan pengukuran lapangan. Dan LOS dihitung untuk simpang secara keseluruhan, belum per lengan.

---

## Kotak 10 — Adaptive Decision Engine (PPO) — 65% harfiah / 90% fungsional

**Fungsinya:** memilih pengaturan lampu terbaik.

**Ini kotak yang paling perlu penjelasan hati-hati.** Ada dua lapis:

**Yang JALAN sekarang (dipakai sistem):** Scenario Generator — menguji 3 kandidat lewat simulasi SUMO nyata, lalu memilih skor gabungan delay+antrean terendah.

**PPO — sudah dilatih, belum diaktifkan:**
- Environment Gymnasium di atas SUMO, sudah terintegrasi ke backend dengan fallback otomatis
- Training **berhasil belajar** — reward naik monoton di seluruh rentang latihan
- **Tapi gerbang kualitas otomatis menolaknya**: kami syaratkan PPO unggul di **ketiga** metrik; dia baru menang 2 dari 3 (throughput selalu kalah)

**Kami tidak berhenti di "belum lolos" — kami investigasi kenapa, dan menemukan 2 kelemahan:**
1. **Fungsi reward buta terhadap throughput.** Nilainya mentok di 15 kendaraan/langkah, padahal kondisi nyata 18–26. Jadi menambah throughput tidak menambah nilai sama sekali — PPO tidak punya alasan mengejarnya.
2. **Simulator memberi PPO kendali yang tidak ada di sistem asli.** Environment membolehkan PPO memilih "mulai dari lampu mana", padahal produksi selalu mulai dari urutan pertama. Akibatnya 80,5% keunggulan PPO berasal dari perbandingan yang tidak mencerminkan kenyataan.

**Keduanya sudah diperbaiki dan sedang dilatih ulang.**

**Kalimat untuk dosen/juri:**
> "PPO berhasil dilatih dan menunjukkan pembelajaran nyata. Tapi evaluasi otomatis kami menolaknya untuk diaktifkan karena belum unggul di semua metrik. Kami memilih tetap memakai metode yang sudah terverifikasi daripada mengaktifkan model yang buktinya belum kuat."

---

## Kotak 11 — Signal Timing Recommendation — 88%

**Fungsinya:** menghasilkan rekomendasi durasi hijau untuk keempat lengan, dalam rotasi.

**Sudah sejauh mana:** rotasi tetap **utara → timur → selatan → barat**, durasi tiap lengan dihitung adaptif dari kondisi lalu lintas + forecast. Berjalan dengan jam server sungguhan (bukan simulasi di browser), sehingga semua pengguna melihat fase yang sama.

**Poin kuat:** satu sumber kebenaran — panel "Status Sinyal" dan "Rekomendasi" membaca rencana siklus yang **sama persis**, jadi tidak mungkin menampilkan angka berbeda untuk lengan yang sama.

---

## Kotak 12 — Dashboard — 92%

**Fungsinya:** menampilkan seluruh sistem ke pengguna.

**Sudah sejauh mana:** Next.js, 13 halaman ter-build bersih. Menampilkan statistik per lengan, status lampu dengan hitung mundur, rekomendasi 4 lengan, video CCTV, dan Digital Twin SUMO.

**Poin kuat untuk ditunjukkan saat demo:** ada **badge sumber keputusan** — "Diuji simulasi SUMO" vs "Estimasi langsung". Jadi penonton bisa melihat langsung di layar apakah keputusan yang tampil benar-benar melewati simulasi atau tidak. Sistem tidak menyamarkan asal keputusannya.

---

## Ringkasan untuk penutup presentasi

**Yang sudah terbukti bekerja:**
- Rantai penuh CCTV → deteksi → data → simulasi → keputusan → dashboard, semuanya tersambung
- Simpang asli, bukan simulasi generik
- Keputusan diuji simulasi sebelum dipakai, dengan LOS standar HCM 2000
- Forecast LSTM terbukti membantu di 10 dari 10 pengujian

**Yang jujur kami sampaikan sebagai keterbatasan:**
- Akurasi deteksi CV 48,7% — sudah diinvestigasi sampai akar penyebabnya
- PPO belum diaktifkan — evaluasi otomatis menolak, sedang diperbaiki
- Data latih baru 1 sesi rekaman — karena itu forecast dibobot konservatif

**Kalimat penutup yang saya sarankan:**
> "Kami membangun gerbang kualitas otomatis yang bisa menolak pekerjaan kami sendiri. PPO tidak lolos, dan kami tidak memaksakannya. Menurut kami itu bagian dari rekayasa yang benar — mengukur jujur, lalu memutuskan berdasarkan bukti."

---

*Sumber angka: [`STATUS-DAN-SISA-KERJA.md`](STATUS-DAN-SISA-KERJA.md). Bukti pengujian: [`hasil-validasi-akurasi-cv.md`](hasil-validasi-akurasi-cv.md), [`hasil-studi-forecast-multi-snapshot.md`](hasil-studi-forecast-multi-snapshot.md), [`hasil-validasi-multisnapshot-multiseed.md`](hasil-validasi-multisnapshot-multiseed.md), [`hasil-kalibrasi-kandidat-agresif.md`](hasil-kalibrasi-kandidat-agresif.md).*

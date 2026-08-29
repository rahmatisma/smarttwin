# Rencana CV Live + Deploy Penuh di RunPod — untuk Final Makassar

> 🔵 **Ini dokumen CARA KERJA (desain), bukan status.** Ditulis 29 Agustus 2026 dari permintaan Rahmat. **Bukan untuk video 31 Agustus** — sistem saat ini (CSV + `run_ingest.py` manual) tetap dipakai untuk itu, tidak berubah. Dokumen ini untuk pengembangan setelahnya, menuju final KMIPN di Makassar, karena Rahmat akan bawa laptop (bukan PC ber-GPU) dan berencana proses 4 kamera secara paralel/langsung.

## 1. Kenapa ini dibutuhkan

Dua masalah berbeda yang mendorong rencana ini:

1. **Laptop tidak cukup kuat.** GPU yang selama ini dipakai (GTX 1650 SUPER, 4GB VRAM) sudah jadi bottleneck bahkan untuk proses batch 1 kamera (lihat `docs/STATUS-DAN-SISA-KERJA.md` — catatan CUDA venv terpisah, GPU 5,1× lebih cepat dari CPU tapi tetap terbatas VRAM-nya). Untuk final, laptop yang dibawa kemungkinan lebih lemah lagi.
2. **Rahmat ingin 4 kamera diproses langsung/live secara paralel** — bukan lagi round-robin satu-thread seperti sekarang (yang didesain untuk file rekaman berujung, bukan stream tanpa akhir).

## 2. Dua perubahan arsitektur yang dibutuhkan — jangan digabung jadi satu langkah besar

### 2.1 CV: dari round-robin satu-thread jadi paralel per kamera

**Sekarang** (`jalankan_gabungan()` di `vehicle_counter_pingit.py:1782`): 1 loop, 1 thread, baca kamera gantian (1 frame CCTV_1, 1 frame CCTV_2, dst). Ini cocok untuk file rekaman yang pasti selesai — kalau lambat, ya lebih lama, tapi tetap selesai.

**Masalahnya untuk live:** stream tidak menunggu. Kalau 1 thread kewalahan melayani 4 kamera real-time, feed live akan terus "ketinggalan" dari kejadian aslinya — backlog menumpuk tanpa henti, bukan cuma lebih lambat.

**Yang dibutuhkan:** 4 proses terpisah (bukan 4 thread — YOLO/PyTorch lebih aman di proses terpisah karena GIL Python + isolasi CUDA context), masing-masing:
- Load model YOLO sendiri (artinya VRAM dipakai ~4×, bukan 1×)
- Baca 1 kamera RTSP sendiri
- Jalan terus-menerus (bukan `--durasi` tetap)

Ini **bukan** ubah logika deteksi/hitung sama sekali — `hitung_crossing()`, `hitung_kendaraan_di_zona()`, dll. tetap persis sama. Yang berubah cuma **cara memanggilnya**: ganti `jalankan_gabungan()` (1 loop gantian) jadi pembungkus `multiprocessing`/`concurrent.futures.ProcessPoolExecutor` yang menjalankan 4 instance independen.

### 2.2 Ingest: dari CSV+manual jadi tulis langsung per-jendela

**Sekarang:** CV tulis CSV (`crossing_simpang.csv`, `snapshot_zona.csv`) → manusia jalankan `run_ingest.py` → `backend/app/pipeline/cv_csv_bridge.py::ingest()` baca CSV lewat `_load_merged()` (`cv_csv_bridge.py:99`, pakai `pd.read_csv` langsung ke file) → tulis ke Supabase.

**Masalahnya untuk live:** CSV-sebagai-perantara berarti selalu ada jeda "tunggu file selesai, baru orang jalankan ingest manual" — persis pola yang bikin insiden 29 Agustus (CSV ditimpa test run) bisa terjadi sama sekali.

**Yang dibutuhkan — refactor kecil, bukan tulis ulang:**
```
_load_merged(cross_path, density_path)          # SEKARANG: baca file
    -> pd.read_csv(cross_path), pd.read_csv(density_path)
    -> _merge_dataframes(df_cross, df_density)   # BARU: logika gabung asli, dipisah jadi fungsi sendiri

_load_merged() jadi wrapper tipis yang panggil _merge_dataframes()
   setelah baca CSV -- perilaku lama utuh, tidak ada yang rusak.

CV (proses paralel di atas) panggil _merge_dataframes() LANGSUNG
   tiap jendela 5 detik selesai -- tanpa lewat file CSV sama sekali.
```
Ini **reuse logika `ingest()` yang sudah teruji**, cuma titik masuknya beda (DataFrame langsung, bukan path file).

**CSV tidak perlu dihapus** — tetap berguna untuk debug/arsip/training LSTM batch (seperti sekarang), cuma bukan lagi satu-satunya jalur ke Supabase.

## 3. Spesifikasi RunPod untuk sistem PENUH (beda dari pod PPO-saja)

| Komponen | Rekomendasi | Alasan |
|---|---|---|
| **GPU** | **16GB+ VRAM** (mis. RTX 4080/4090, A5000, A6000) | 4 proses YOLO paralel × ~3-4GB VRAM per instance (model + CUDA context) + headroom |
| **vCPU** | 12–16 core | 4 proses CV (masing-masing butuh CPU buat decode frame + ByteTrack, bukan cuma GPU) + SUMO worker + backend + LSTM serving berjalan bersamaan |
| **RAM** | 32 GB | 4 model YOLO ter-load + buffer video 4 stream + servis lain |
| **Disk** | 100 GB+, **pakai Network Volume** (persisten) | Model, checkpoint, log, CSV arsip — jangan taruh di storage pod biasa yang hilang kalau pod di-restart |
| **Networking** | Expose port backend (8000) & frontend (3000) lewat proxy RunPod | Supaya dashboard bisa diakses dari luar pod (juri/tim) |

**Ini beda dari pod PPO training** (CPU-only, 4-8 vCPU, 8-16GB RAM) — kalau mau hemat biaya, **pisahkan 2 pod**: 1 CPU pod murah buat training PPO (sudah dibahas), 1 GPU pod lebih mahal cuma dinyalakan saat butuh live demo/testing sistem penuh — jangan sewa GPU pod 24 jam kalau cuma dipakai pas demo.

## 4. Pertanyaan terbuka yang perlu dijawab sebelum mulai coding

1. **Sumber 4 kamera di Makassar itu apa?** RTSP sungguhan dari CCTV venue (kalau panitia kasih akses), atau tetap video rekaman yang di-loop lewat `--sumber` (S-5 sudah siap untuk ini)? Ini menentukan apakah kerjaan di bagian 2.1/2.2 di atas benar-benar perlu, atau cukup jalankan sistem yang sudah ada dengan `--sumber` menunjuk ke file yang di-loop.
2. **Siapa yang mengakses dashboard saat demo?** Kalau cuma laptop Rahmat sendiri yang perlu lihat, tidak perlu expose port ke publik — cukup SSH tunnel/port-forward. Kalau juri perlu akses dari perangkat mereka sendiri, baru perlu setup proxy publik RunPod.
3. **Budget & durasi sewa.** GPU pod 16GB+ jauh lebih mahal dari CPU pod — perlu dihitung berapa lama pod ini perlu menyala (cuma saat demo, atau standby beberapa hari selama kompetisi).

## 5. Urutan kerja yang disarankan (setelah 31 Agustus)

1. **Jawab bagian 4 dulu** (terutama #1) — ini menentukan apakah bagian 2.1/2.2 di bawah ini benar-benar perlu dikerjakan sama sekali.
2. Kalau perlu live sungguhan: kerjakan **2.2 dulu** (refactor ingest, risiko rendah, reuse logika lama) sebelum **2.1** (paralelisasi CV, lebih kompleks — proses terpisah, penanganan reconnect RTSP yang putus, dst).
3. Uji di GPU pod kecil dulu (1 kamera paralel) sebelum commit ke pod besar 4 kamera sekaligus.
4. Baru setelah itu pertimbangkan expose port publik (bagian 4 #2) kalau memang dibutuhkan.

---

*Rujukan: `docs/STATUS-DAN-SISA-KERJA.md` (status Fase 1/2, S-5 --sumber), `cv/vehicle_counter_pingit.py` (logika CV asli, tidak berubah), `backend/app/pipeline/cv_csv_bridge.py` (logika ingest yang di-reuse), `cv/CATATAN.md` (kejadian CSV tertimpa 29 Agustus — jangan terulang di desain live ini).*

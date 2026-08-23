# Dashboard Realtime — cara kerja, cara jalanin, dan kenapa desainnya begini

Ditulis setelah sesi debugging panjang (24 Agustus 2026) supaya orang berikutnya yang megang bagian ini tidak perlu mengulang proses trial-and-error yang sama. Kalau ada yang mau mengubah arsitektur di sini, baca dulu bagian "Kenapa bukan live-push" sebelum mulai.

## Ringkasan alur data

```
vehicle_counter_copy.py (proses video, 4 kamera)
        |
        v
cv/output/crossing_simpang.csv       (ALIRAN — kendaraan yang lewat garis)
cv/output/percobaan_logic_simpang.csv (KEHADIRAN — kendaraan di dalam zona)
        |
        v
python run_ingest.py                 (baca 2 CSV, isi ke Supabase)
        |
        v
Supabase: trafficStates + trafficApproachStates
        |
        v
frontend/src/lib/supabaseData.ts::fetchTrafficState()
        |
        v
Dashboard (StatsRow, CameraFeedPanel, dst)
```

Ini **bukan** live-push (CV tidak mengirim data secara langsung ke backend saat berjalan). Datanya batch: proses video sampai selesai dulu, baru di-ingest sekali, baru dashboard baca dari database. Lihat bagian di bawah kenapa ini pilihan sadar, bukan keterbatasan yang belum sempat dibenerin.

## Cara jalanin dari nol

1. **Proses video jadi CSV:**
   ```powershell
   cd cv
   .venv\Scripts\python.exe vehicle_counter_copy.py --durasi <durasi_video_penuh_detik> --tanpa-tampilan
   ```
   Tanpa `--kamera`, otomatis proses ke-4 kamera (CCTV_1–4) sekaligus dalam satu proses (round-robin, single-threaded). `--tanpa-tampilan` supaya tidak ada popup `cv2.imshow` per kamera.

2. **Masukkan hasilnya ke database:**
   ```powershell
   cd ..
   backend\.venv\Scripts\python.exe run_ingest.py
   ```
   Aman dijalankan berkali-kali (upsert berdasarkan `intersectionId + windowStart + windowEnd`, bukan insert terus-terusan). **Penting:** kalau baru selesai bikin ulang CSV dari nol, ingest ulang juga supaya `createdAt` seluruh batch konsisten (lihat bug #2 di bawah).

3. **Nyalain backend & frontend** (masing-masing di terminal terpisah, biarkan tetap kebuka):
   ```powershell
   cd backend
   .venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```
   ```powershell
   cd frontend
   npm run dev
   ```

4. Buka `http://localhost:3000`, pilih CCTV atau "Semua Lengan", putar videonya. Angka di kartu statistik akan mengikuti posisi video (lihat mekanisme di bawah).

## Kenapa bukan live-push (CV kirim data langsung sambil jalan)

Sempat dibangun versi live: `vehicle_counter_copy.py --realtime --push-backend` memproses video pada kecepatan wall-clock 1:1 sambil mem-POST tiap window 5 detik langsung ke `POST /api/v1/traffic/ingest`, dan dashboard baca `GET /api/v1/traffic/live` (in-memory, tanpa Supabase). **Ini sudah dibangun dan terbukti jalan** (diuji end-to-end lewat `TestClient`) — tapi di-revert karena diagnosa nyata di mesin dev: proses 30 detik video untuk **satu** kamera saja makan waktu **lebih dari 3 menit** wall-clock. Artinya kecepatan proses YOLO di CPU lokal jauh di bawah kecepatan video asli, jadi `--realtime` (yang nunggu/nge-throttle biar sinkron ke tempo video) percuma — CV-nya justru selalu ketinggalan, bukan kecepetan.

Kalau nanti pindah ke server dengan GPU beneran (rencana: RunPod), bottleneck ini hilang dan arsitektur live-push jadi masuk akal dipakai lagi. Kodenya tidak perlu didesain ulang dari nol — tinggal cek riwayat git di sekitar tanggal 23–24 Agustus 2026 untuk referensi (file yang terlibat: `backend/app/services/live_traffic_state.py`, `cv/backend_writer.py`, endpoint `/api/v1/traffic/ingest` & `/live` di `backend/app/api/routes/traffic.py`, flag `--push-backend`/`--realtime` di `vehicle_counter_copy.py`).

## Mekanisme "ikut posisi video" (bukan cuma snapshot statis)

Awalnya setelah pindah ke database, dashboard cuma nampilin **satu baris terakhir** (snapshot beku) — angkanya diem terus walau videonya diputar. Ini diperbaiki: `fetchTrafficState()` sekarang mencocokkan posisi `<video>.currentTime` ke jam rekaman di database, dalam **batch ingest yang paling baru** (dikelompokkan lewat `createdAt`). Jadi kalau video di detik ke-120, dia cari baris `trafficStates` yang jamnya = jam-mulai-batch + 120 detik.

Konsekuensi dari cara ini:
- Update di dashboard granular **per 5 detik** (mengikuti `WINDOW_DETIK` di CV), bukan tiap frame. Videonya sendiri mulus 30fps, tapi angka statistiknya "loncat" tiap 5 detik — ini disengaja/inheren, bukan bug. Kalau mau lebih presisi, `WINDOW_DETIK` di `vehicle_counter_copy.py` perlu diperkecil dan videonya diproses ulang dari awal.
- Ditambah jeda maksimal ~1 detik dari interval polling dashboard (`setInterval` tiap 1000ms di `page.tsx`).
- Angka di dashboard itu **rata-rata 5 detik**, bukan snapshot sesaat. Kalau dibandingkan manual ke overlay "ZONA MONITOR" bawaan `vehicle_counter_copy.py` (yang nampilin angka SATU FRAME PERSIS), wajar beda sedikit — dua-duanya benar, cuma ukuran yang berbeda.

## Rencana ke depan: pindah ke RunPod

Rencananya (per 24 Agustus 2026, belum dieksekusi — RunPod belum di-setup, dan **cakupannya juga belum diputuskan**) `vehicle_counter_copy.py` akan dijalankan di RunPod (server GPU cloud) untuk deployment/demo, bukan di laptop dev. Yang belum jelas: apakah RunPod cuma megang bagian CV/YOLO-nya, atau seluruh stack (backend+frontend) ikut pindah ke sana. Dua-duanya punya alur yang beda — ditulis di bawah, pilih salah satu begitu sudah diputuskan.

### Opsi A — RunPod cuma jalanin CV/YOLO (kemungkinan besar ini yang dipakai)

Backend (FastAPI), frontend, dan Supabase tetap di tempat sekarang. RunPod cuma dipakai buat bagian yang butuh GPU.

```
┌─────────────────────────────┐         internet          ┌──────────────────────────┐
│ RunPod (GPU pod)             │ ──── POST /ingest ──────> │ Backend (FastAPI)         │
│  - video mentah (lihat        │      (butuh URL publik,   │  - tetap di mesin/hosting │
│    "Video mentahnya dari      │       bukan 127.0.0.1)    │    sekarang               │
│    mana" di bawah)            │                            │                           │
│  - vehicle_counter_copy.py    │                            │                           │
│    --realtime --push-backend  │                            │                           │
└─────────────────────────────┘                            └───────────┬──────────────┘
                                                                          │
                                                                          v
                                                                  Supabase (sudah cloud,
                                                                  tidak perlu pindah)
                                                                          │
                                                                          v
                                                              Frontend (Next.js) — tetap
                                                              di tempat sekarang, baca
                                                              lewat backend/Supabase
                                                                          │
                                                                          v
                                                                  Browser pengguna
```

**Yang WAJIB diubah supaya ini jalan:** `cv/backend_writer.py` (kalau sudah di-rebuild sesuai checklist di bawah) baca URL backend dari env var `SMARTTWIN_BACKEND_URL`, default-nya `http://127.0.0.1:8000` — itu cuma nyambung kalau CV dan backend jalan di MESIN YANG SAMA. Begitu CV pindah ke RunPod (mesin lain, di internet), itu harus diganti ke URL publik backend yang bisa diakses dari luar (domain/IP + port yang di-expose, bukan localhost). Backend juga perlu bisa nerima koneksi dari luar (bukan cuma `127.0.0.1`) dan idealnya ada autentikasi sederhana di endpoint `/ingest` supaya tidak sembarang orang bisa nge-POST data palsu.

### Opsi B — Semuanya (CV + backend + frontend) pindah ke RunPod

```
┌───────────────────────────────────────────────────┐
│ RunPod                                              │
│                                                      │
│  vehicle_counter_copy.py --realtime --push-backend  │
│         │ (POST ke localhost/pod, satu mesin)       │
│         v                                            │
│  Backend (FastAPI)                                   │
│         │                                            │
│         v                                            │
│  Frontend (Next.js), di-expose lewat port RunPod      │
│                                                      │
└──────────────────────────┬──────────────────────────┘
                            │ internet
                            v
                    Supabase (tetap cloud terpisah,
                    tidak ikut pindah)
                            │
                            v
                     Browser pengguna
```

Lebih simpel dari sisi jaringan (CV→backend tetap satu mesin, `127.0.0.1` masih valid), tapi berarti RunPod juga nanggung beban serving frontend ke pengguna — biasanya bukan itu tujuan RunPod (dia dioptimasi buat compute GPU, bukan hosting web biasa), jadi opsi ini kurang lazim kecuali memang mau satu server buat semuanya.

### Video mentahnya dari mana (berlaku buat opsi manapun)

`cv/videos/*.mp4` itu gitignored — tidak ikut ke-clone/ke-deploy otomatis. RunPod butuh salinan video itu sendiri. Karena video mentah sudah ada di HuggingFace dataset (`rahmatisma/smarttwin-cctv`, folder `videos/simpang4-pingit/`, lihat nama file `cam-<uuid>_CCTV_N.mp4`), cara paling gampang: pas setup pod, download langsung dari situ pakai `huggingface_hub.hf_hub_download()` (perlu `HF_TOKEN` di environment pod), bukan upload manual dari laptop.

### Konsekuensi lain

Ini punya konsekuensi langsung ke arsitektur di atas, di luar soal topologi jaringan:

- **Live-push jadi masuk akal lagi.** Bottleneck yang bikin arsitektur push di-revert (lihat bagian "Kenapa bukan live-push") murni soal kecepatan CPU lokal, bukan soal desainnya salah. Begitu ada GPU yang sanggup proses YOLO ≥1x kecepatan video real, `--realtime --push-backend` (atau versi rebuild-nya) jadi pilihan yang valid — dashboard bisa update tiap window CV selesai dihitung, tanpa nunggu proses selesai total kayak sekarang.
- **Tidak perlu ganti framework.** Backend sudah FastAPI, itu sudah cukup buat pola push/serving live — nggak ada alasan pindah ke Flask atau framework lain cuma buat fitur ini.
- **Ini menyelesaikan masalah kecepatan, BUKAN kelengkapan fitur.** Pindah ke RunPod tidak otomatis memunculkan Longest Queue atau Average Speed (lihat bagian "Keterbatasan yang MEMANG belum ada" di bawah) — itu tetap butuh kerja CV terpisah, di server manapun dia jalan.
- **Belum boleh dites/dibangun ulang sebelum RunPod-nya benar-benar siap.** Tanpa GPU sungguhan, tidak ada cara memverifikasi versi live-push jalan benar atau tidak (sama seperti kejadian 24 Agustus — butuh dites langsung baru ketahuan masalahnya). Kodenya sudah pernah dibangun & terbukti jalan (diuji lewat `TestClient`) sebelum di-revert, jadi tinggal dibangun ulang dari referensi riwayat git di sekitar 23–24 Agustus 2026 saat RunPod sudah siap — bukan didesain ulang dari nol.

Checklist singkat kalau RunPod sudah siap dan mau lanjut ke live-push:
1. Rebuild `backend/app/services/live_traffic_state.py`, `cv/backend_writer.py`, endpoint `POST /api/v1/traffic/ingest` & `GET /api/v1/traffic/live` di `backend/app/api/routes/traffic.py`, dan flag `--push-backend`/`--realtime` di `vehicle_counter_copy.py` (lihat riwayat git untuk isi persisnya).
2. Tes SATU kamera dulu (`--kamera CCTV_1 --durasi 30 --realtime --push-backend`) sebelum jalanin ke-4 kamera sekaligus, dan ukur wall-clock time-nya — pastikan beneran ≥1x kecepatan video sebelum lanjut ke run penuh 43 menit.
3. Kalau sudah stabil, `frontend/src/lib/supabaseData.ts::fetchTrafficState()` perlu diarahkan balik ke endpoint live (`GET /api/v1/traffic/live`) alih-alih query Supabase yang dijelaskan di atas.

## Bug yang sempat ditemukan & diperbaiki (24 Agustus 2026)

1. **Pemetaan kamera→lengan salah** di `TrafficStateBuilder.loadCvOutput()` (`backend/app/pipeline/traffic_state_builder.py`). Awalnya memetakan cuma dari kolom `kamera`, padahal CCTV_2 framenya punya DUA garis crossing sekaligus (`MAGELANG` → utara, `DIPONEGORO` → timur). Akibatnya baris DIPONEGORO ikut ke-groupby-sum ke utara, timur kehilangan data crossing. Sudah diperbaiki: mapping sekarang dari `label_garis` (untuk crossing) dan `lengan` (untuk density) — lihat `CROSS_LABEL_MAP`/`DENSITY_LENGAN_MAP` di file yang sama. Catatan desain: density utara diambil dari zona `simpang_tengah` milik CCTV_2 sebagai **proxy** (bukan pengukuran murni lengan utara, karena tidak ada kamera yang memotret ruas Magelang terpisah dari tengah simpang) — ini keputusan sadar, bukan bug.

2. **`createdAt` tidak konsisten satu batch** di `bulk_upsert_traffic_states` (`backend/app/services/traffic_repository.py`). Kolom `createdAt` awalnya mengandalkan default database, yang cuma keisi pas baris BARU dibuat — baris yang sudah ada (kena UPDATE lewat upsert) tidak ikut ter-refresh. Akibatnya satu ingest CSV yang sama bisa punya banyak `createdAt` berbeda-beda tercecer (campuran dari beberapa kali run), bikin mekanisme "ikut posisi video" di atas cuma dapat sebagian kecil baris. Sudah diperbaiki: `createdAt` sekarang dikirim eksplisit di payload, satu timestamp yang sama untuk seluruh baris dalam satu kali panggilan `ingestCvOutput()`.

3. **Bug pencocokan ID hasil upsert** juga di `bulk_upsert_traffic_states` — timestamp yang dikirim (naive, tanpa offset zona waktu) dan yang dibalikin Supabase (ada offset `+00:00`) direpresentasikan beda sebagai string, jadi dict lookup buat mencocokkan `trafficStateId` ke baris `trafficApproachStates` selalu gagal. Sudah diperbaiki lewat helper `_normalize_timestamp_key()`.

4. **Constraint `UNIQUE` yang hilang** di tabel `trafficStates` Supabase (kombinasi `intersectionId, windowStart, windowEnd`) — didokumentasikan di `docs/database.md` tapi ternyata tidak pernah benar-benar dibuat di database asli. Tanpa ini, `bulk_upsert_traffic_states` selalu gagal (`42P10`) dan jatuh ke jalur cadangan yang insert satu-satu (538 request berurutan, bisa belasan menit). Sudah ditambahkan lewat migration `add_unique_traffic_window`.

5. **`source: "cv_test"` mencemari tabel produksi** — `backend/tests/test_traffic_pipeline.py` menulis ke Supabase yang sama dengan yang dipakai dashboard (bukan database tes terpisah). Kalau lihat baris aneh dengan `source = 'cv_test'` di `trafficStates`, itu sampah dari test suite, bukan data CV asli.

## Keterbatasan yang MEMANG belum ada (bukan bug, jangan dikejar sebagai bug)

- **Longest Queue selalu 0.0 m** — `vehicle_counter_copy.py` tidak pernah menghitung antrean dalam meter (beda dengan `vehicle_counter.py` lama yang punya `QUEUE_SPACE_M`, tapi logika itu sengaja tidak dibawa pas pindah ke pendekatan zona). `queueLengthVeh`/`queueLengthMEst` di-hardcode 0 di `loadCvOutput()`.
- **Average Speed selalu N/A** — belum ada logika hitung kecepatan sama sekali di CV manapun. Butuh kalibrasi jarak piksel-ke-dunia-nyata + tracking kecepatan antar-frame, belum pernah dibangun.

Dua-duanya butuh kerja CV baru (bukan backend/frontend), dan tidak otomatis kepenuhan cuma dengan pindah ke server yang lebih kuat (RunPod menyelesaikan masalah **kecepatan**, bukan menambah **logika** yang belum ada).

## Gotcha operasional yang sempat bikin bingung

- **Video hasil anotasi bisa ketimpa tanpa sadar.** `vehicle_counter_copy.py` upload otomatis ke HuggingFace (`videos/simpang4-pingit/annotated/anotasi_CCTV_N.mp4`) tiap kali selesai jalan — kalau jalanin cuma buat tes cepat satu kamera/durasi pendek, video anotasi ASLI (durasi penuh) ke-timpa versi tes yang pendek, karena nama filenya sama persis. HuggingFace masih nyimpen riwayat commit-nya kalau perlu di-restore (`HfApi.list_repo_commits()` + `hf_hub_download(..., revision=<commit_sha>)`).
- **Cache video lokal (`backend/cache/videos/<video_id>.mp4`) tidak otomatis refresh** kalau file di HuggingFace berubah — sekali ke-cache, tetap dipakai walau sumbernya sudah diganti. Kalau baru restore/ganti video di HuggingFace, hapus manual file cache yang bersangkutan.
- **Bisa ada lebih dari satu `next dev` nyala bareng** tanpa ketahuan — Next.js 16 punya deteksi lock-file, tapi kalau instance lama tidak ke-kill dengan benar (mis. proses anak yang beda PID dari yang kelihatan di task manager), server baru start di port lain (3001) sementara browser masih nyambung ke yang lama, jadi perubahan kode kelihatan "tidak pernah kepakai". Kalau curiga begini: `netstat -ano | grep ":3000"` buat cari PID sebenarnya, bukan asal `taskkill` PID pertama yang kelihatan.
- **Jangan `git checkout --` file yang statusnya `M` dari SEBELUM sesi kerja dimulai** tanpa cek dulu isinya — kalau versi commit terakhirnya ternyata rusak/belum selesai di-merge, itu bakal menimpa kerjaan yang belum sempat di-commit dengan versi yang lebih buruk. Selalu `git status` dan baca diff dulu sebelum revert massal.

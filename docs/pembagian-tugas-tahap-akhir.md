# Pembagian Tugas Tahap Akhir — H-6 (25–31 Agustus 2026)

Disusun dari audit progres per modul malam 25 Agustus (lihat rekap commit di `pembagian-tugas-24-agustus.md` dan desain LSTM di `rencana-lstm-forecast.md`). Skor kesiapan MVP keseluruhan saat ini **~72%**. Dokumen ini bukan daftar bug lagi — ini rencana ke depan: apa yang harus dikerjakan 6 hari ke depan supaya demo 31 Agustus solid, dibagi per orang.

**Prinsip pembagian:** tetap di jalur masing-masing yang sudah terbukti malam ini (Rahmat = backend/CV/simulasi, Yuli = LSTM, Melpi = frontend) — bukan dirombak, biar tidak ada waktu terbuang re-onboarding ke area baru.

---

## 0. Keputusan tim — SUDAH DISEPAKATI 25 Agustus malam

1. **Format model LSTM: PyTorch.** Yuli pegang penyesuaian `realtime_forecast_service.py` supaya baca `.pt` (bukan `.keras`). Training pipeline PyTorch yang sudah jalan (5 detik resample, horizon 60s→15s) tidak perlu ditulis ulang.
2. **Scenario Generator: dibangun versi RINGAN dulu, PPO jadi upaya paralel/bonus.** Bukan "terima simplifikasi" dan bukan "all-in PPO" — jalan tengah: bangun kotak 7 (Scenario Generator ringan, 3 kandidat), loop 8-9 (simulasi pendek per kandidat), dan LOS di kotak 9, dengan aturan seleksi sederhana menggantikan kotak 10 (PPO) buat SEKARANG. Detail di 1.5. PPO tetap diusahakan Rahmat secara paralel di RunPod (lihat 1.6) — kalau berhasil sebelum 31 Agustus, tinggal ditukar karena interface-nya sudah disiapkan sama bentuknya (lihat catatan arsitektur di 1.6).
3. **CV antrean (Fase 2 LSTM): jadi dikerjakan** oleh Rahmat (lihat 1.2).

---

## 1. Rahmat — Backend, CV, Integrasi Simulasi

### 1.1 [P0 — hari ini] Commit fix regresi `sumo_controller.py`
- [ ] Commit fix `SUMO_BIN_DIR` yang sempat terhapus tanpa sengaja di commit LSTM Yuli (sudah diperbaiki, belum di-commit)
- [ ] Jalankan `run_tls_simulation.py` sekali penuh buat mastiin simulasi beneran jalan lagi, bukan cuma lolos import

### 1.2 [P1 — besar, mulai secepatnya] Logika antrean CV (Fase 2 LSTM)
- [ ] Desain ulang definisi "antrean" buat pendekatan zona (bukan crossing lama) — lihat catatan teknis lama di `docs/realtime-dashboard.md` (`QUEUE_SPACE_M`, `STOPPED_PIXEL_THRESHOLD`, dst dari `vehicle_counter.py` versi lama)
- [ ] Implementasi logika deteksi kendaraan berhenti, jalankan ke rekaman yang ada
- [ ] Hasilkan CSV baru dengan `queueLengthVeh`/`queueLengthMEst` yang bukan nol lagi
- [ ] Estimasi waktu proses ulang video sudah pernah dihitung ~5 jam (lihat `docs/realtime-dashboard.md`) — alokasikan waktu mesin, bukan cuma waktu kerja
- [ ] Serahkan ke Yuli begitu CSV siap, biar dia retrain 4 fitur penuh

### 1.3 [P1] Satukan metrik simulasi
- [ ] `run_simulation.py` sudah punya `averageWaitingTimeSeconds`, throughput per-approach — tapi terpisah dari `run_tls_simulation.py` yang dipakai live
- [ ] Pindahkan/sambungkan logika metrik itu ke `run_tls_simulation.py`, atau minimal ke `SimulationResultWriter`, biar hasil simulasi live juga punya delay/queue/throughput, bukan cuma step count & posisi kendaraan

### 1.4 [P2 — kalau sempat] Bersihkan sisa kode basi
- [ ] `decision_engine/run_decision.py` masih manggil `.decide()` yang sudah tidak ada — perbaiki atau hapus kalau memang sudah tidak dipakai
- [ ] `backend/tests/test_simulation_service.py` masih file kosong — isi minimal smoke test, atau hapus kalau memang tidak akan diisi

### 1.5 [P1 — prioritas baru, isi kotak 7/9/10 di diagram arsitektur] Scenario Generator ringan + LOS
Mengisi gap yang ketauan pas cocokkan kode ke diagram arsitektur asli (`data-contract.md` / proposal). Bukan Scenario Generator penuh — versi yang realistis buat 6 hari:
- [ ] **Generator kandidat (kotak 7):** fungsi kecil yang hasilkan 3 varian rencana durasi hijau per keputusan — (a) hasil `RuleBasedEngine` apa adanya, (b) versi lebih agresif ke lengan tersibuk (+20%), (c) versi lebih merata antar lengan
- [ ] **Loop simulasi pendek (kotak 8):** tiap kandidat dijalankan lewat logika `run_tls_simulation.py` yang sudah ada, dibungkus loop 3x, jendela pendek (60-120 detik simulasi, bukan sejam)
- [ ] **Satukan Performance Analysis (kotak 9):** delay & throughput sudah ada di `run_simulation.py` (lihat 1.3) — pastikan dihitung per-kandidat, bukan cuma 1x jalan
- [ ] **Tambah LOS (Level of Service, kotak 9):** belum ada sama sekali. Standar HCM, cukup 1 fungsi lookup dari rata-rata delay per kendaraan ke huruf A-F
- [ ] **Aturan seleksi (ganti kotak 10 buat sekarang):** pilih kandidat dengan skor gabungan delay+queue paling rendah (atau throughput tertinggi) — deterministik, bukan RL. **Tulis di laporan teknis kenapa ini yang dipakai** ("kami jalankan beberapa skenario dan pilih berdasarkan performa terukur, aturan seleksi deterministik menggantikan PPO karena keterbatasan waktu")
- [ ] **Desain interface-nya supaya PPO gampang ditukar nanti:** pastikan apa pun yang menghasilkan pilihan akhir (aturan seleksi di atas) punya bentuk method sama dengan `RuleBasedEngine.recommend(state, currentGreenSeconds, currentPhase)` → keluarin `Recommendation` yang field-nya sama. Kalau PPO (1.6) berhasil, tinggal ganti instance engine-nya, tidak perlu ubah `run_tls_simulation.py`/`recommendation_service.py`

### 1.6 [P2 — bonus paralel, non-blocking] PPO di RunPod
Diusahakan Rahmat di luar jalur utama, TIDAK boleh mengganggu 1.1-1.5. Kalau sampai 31 Agustus belum berhasil, sistem tetap jalan penuh pakai 1.5 — bukan kegagalan, itu memang rencananya dari awal.
- [ ] Time-box: kasih diri sendiri maksimal ~2 hari buat lihat tanda-tanda belajar (reward naik, bukan datar/acak). Kalau di hari ke-2 belum ada sinyal positif, stop, jangan tunggu sampai mepet tenggat
- [ ] Cek dulu spesifikasi RunPod yang dipakai: berapa vCPU, bukan cuma GPU-nya — SUMO jalan di CPU, GPU cuma bantu di bagian neural network PPO-nya, bukan simulasinya
- [ ] Kalau berhasil: `PPOEngine` harus punya method `.recommend(state, currentGreenSeconds, currentPhase)` persis sama bentuknya dengan `RuleBasedEngine`/hasil 1.5, biar tinggal ditukar tanpa ubah kode lain

---

## 2. Yuli — LSTM (dedicated, per kesepakatan 25 Agustus)

### 2.1 [P0 — keputusan dulu, baru kerja] Selesaikan mismatch format model
Pilih salah satu, diskusikan dengan Rahmat karena dia yang pegang `realtime_forecast_service.py`:
- **Opsi A:** Ubah `realtime_forecast_service.py` buat load PyTorch (`torch.load`) alih-alih Keras — kerjaan backend, tapi model training Yuli tidak perlu diubah
- **Opsi B:** Ubah `train.py` balik ke TensorFlow/Keras biar cocok sama serving yang sudah ada — kerjaan Yuli doang, tidak perlu sentuh backend

Rekomendasi: **Opsi A** — script training PyTorch Yuli sudah jalan & teruji (5 detik resample, horizon 60s→15s sudah cocok rencana sesi lampu), sayang kalau ditulis ulang. Lebih murah ubah satu service backend daripada tulis ulang training pipeline yang sudah benar.

### 2.2 [P0] Selesaikan training & commit hasil
- [ ] Latih pakai 2 fitur asli dulu (`vehicleCount`, `densityIndex`) — sesuai Fase 1 di `rencana-lstm-forecast.md`
- [ ] Commit model + scaler ke `forecasting/outputs/` (sekarang cuma ada `.gitkeep`, repo belum punya bukti LSTM sama sekali)
- [ ] Update `forecasting/README.md` bagian status kalau ada perubahan desain dari rencana lama

### 2.3 [P1 — setelah Rahmat kelar CV antrean] Retrain 4 fitur
- [ ] Begitu CSV antrean dari Rahmat (item 1.2) siap, retrain pipeline yang sama dengan 4 fitur penuh
- [ ] Update tabel status fitur di `rencana-lstm-forecast.md` bagian 2

### 2.4 [P2 — kalau sempat] Sambungkan forecast ke Decision Engine
- [ ] Belum ada kode yang menyambungkan hasil forecast ke `RuleBasedEngine.recommend()` — desain pola opsional (`forecast: ForecastResult | None`) sudah dibahas di `rencana-lstm-forecast.md` bagian 8
- [ ] Kalau tidak sempat sebelum 31 Agustus: dokumentasikan sebagai keterbatasan yang jujur, jangan diklaim terintegrasi kalau belum

---

## 3. Melpi — Frontend

### 3.1 [P0 — cepat, blocker deploy] Perbaiki build produksi yang gagal
- [ ] `npm run build` gagal di `/settings` — error `useSearchParams() should be wrapped in a suspense boundary`
- [ ] Fix: bungkus komponen yang pakai `useSearchParams()` dengan `<Suspense>` boundary (pola standar Next.js App Router)
- [ ] Verifikasi `npm run build` sukses penuh setelah fix, bukan cuma halaman itu doang

### 3.2 [P1] Keputusan sumber data Recommendation Panel
- [ ] `RecommendationPanel.tsx` baca tabel `recommendations` di Supabase langsung (lewat `feed_to_supabase.py`), BUKAN lewat endpoint backend `/recommendation` yang baru dibenerin Rahmat malam ini
- [ ] Ini belum tentu bug — tapi perlu diputuskan sadar: tetap begini (decision_engine → Supabase → frontend), atau pindah ke jalur backend API? Diskusikan dengan Rahmat/Yuli, dokumentasikan keputusannya biar tidak dikira kelupaan pas ditanya juri

### 3.3 [P2] Rapikan detail kecil
- [ ] Digital Twin: state awal (`signalStatuses`) hardcode 32s/18s sebelum data live masuk — kasih indikator visual "memuat..." biar tidak kelihatan seperti data asli
- [ ] `CameraFeedPanel.tsx` masih ada `console.log` development di `onTimeUpdate` — hapus sebelum submit final

---

## 4. Yang TIDAK perlu dikerjakan (biar tidak buang waktu H-6)

- **Scenario Generator versi PENUH** (bukan yang ringan di 1.5) — jangan generate skenario dalam jumlah besar/kompleks, cukup 3 kandidat sesuai 1.5
- **Halaman History** — sudah diputuskan di luar scope demo, data mock-nya boleh dibiarkan
- **Auth (login/register/account)** kecuali bagian yang mematahkan build (`/settings`, lihat 3.1) — sisanya sudah diputuskan tidak prioritas
- **PPO di luar jam yang dialokasikan Rahmat sendiri (1.6)** — Yuli dan Melpi TIDAK perlu ikut bantu PPO, fokus di jalur masing-masing. Kalau Rahmat kehabisan waktu di 1.6, itu sudah di-time-box, bukan alasan geser prioritas 1.1-1.5

---

## 5. Checklist sinkronisasi tim (isi pas rapat, bukan solo)

- [x] Format model LSTM: **PyTorch** disepakati (item 2.1)
- [x] Scenario Generator: **versi ringan dibangun (1.5), PPO paralel non-blocking (1.6)** disepakati
- [ ] Sudah sepakat siapa yang dokumentasikan keputusan Recommendation Panel (item 3.2) ke laporan teknis?
- [ ] Rahmat sudah commit fix `sumo_controller.py` (item 1.1)?
- [ ] Rahmat sudah time-box PPO (item 1.6) — jangan biarkan tanpa batas waktu jelas

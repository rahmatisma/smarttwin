# Indeks Dokumentasi SmartTwin

> Catatan perapian repository dan hasil audit terbaru:
> [`CATATAN-PERAPIAN-DAN-HASIL-AUDIT.md`](CATATAN-PERAPIAN-DAN-HASIL-AUDIT.md).
> Dokumen tersebut mencatat perubahan dokumentasi dan temuan audit, bukan
> menggantikan status resmi proyek di bawah ini.

Dirapikan **28 Agustus 2026**. Sebelumnya ada 20 dokumen yang saling bertentangan dan banyak berisi tugas yang sudah selesai — itu bikin tim bingung. Sekarang tinggal 14, dan **cuma ada 3 jenis**:

| Jenis | Isinya | Berubah kapan |
|---|---|---|
| 🟢 **STATUS** | Sudah sampai mana, apa yang belum | Tiap ada kemajuan |
| 🔵 **CARA KERJA** | Bagaimana sesuatu bekerja & kenapa desainnya begitu | Jarang |
| 🟠 **HASIL UJI** | Bukti pengujian untuk laporan teknis | Tidak pernah (arsip) |

---

## 🟢 STATUS — cuma ada SATU

### **[`STATUS-DAN-SISA-KERJA.md`](STATUS-DAN-SISA-KERJA.md)** ← baca ini duluan

**Kalau cuma boleh baca satu dokumen, baca ini.** Isinya: persentase tiap kotak diagram, daftar yang **sudah selesai** (biar tidak dikerjakan ulang), daftar **sisa kerja** dengan pemilik & estimasi waktu, dan contoh jawaban untuk juri.

> ⚠️ **Jangan bikin dokumen status baru.** Kalau ada item selesai, pindahkan ke bagian "Sudah Selesai" di dokumen itu. Kebiasaan bikin dokumen status baru tiap audit itu yang bikin repo ini punya 20 file `.md` yang saling bertentangan.

### **[`penjelasan-progres-per-modul.md`](penjelasan-progres-per-modul.md)** — bahan demo/presentasi

Penjelasan tiap kotak diagram untuk **dijelaskan ke orang lain** (dosen pembimbing, juri): apa fungsinya, sudah sejauh mana, buktinya apa, batasannya apa — plus kalimat siap-pakai untuk pertanyaan sulit. **Bukan pelacak status** — angkanya bersumber dari `STATUS-DAN-SISA-KERJA.md` di atas; kalau berbeda, yang di atas yang benar.

### Catatan per-sesi — **bukan pelacak status**

Dokumen "apa yang berubah di satu sesi kerja", supaya tidak perlu membaca diff mentah. Ditulis sekali lalu dibiarkan (arsip), tidak dipelihara seperti dokumen status.

| Dokumen | Isinya |
|---|---|
| [`audit_final_31agustus.md`](audit_final_31agustus.md) | Audit menyeluruh 31 Agustus: verifikasi klaim "selesai" ke kode/DB/test, termasuk temuan 2 commit revert dini hari yang menghapus perbaikan dashboard |
| [`catatan-perubahan-1-september.md`](catatan-perubahan-1-september.md) | Perubahan 1 September: isolasi SUMO dashboard vs `/digitaltwin`, panel "Hasil Simulasi", kartu durasi sinyal + grafik tren, dan 5 bug (termasuk `Server disconnected` yang ternyata masalah HTTP/2, bukan jaringan) |

---

## 🔵 CARA KERJA — rujukan teknis

### Wajib buat semua orang

| Dokumen | Isinya |
|---|---|
| [`alur-kerja-sistem-non-teknis.md`](alur-kerja-sistem-non-teknis.md) | Alur kerja sistem dari kamera sampai rekomendasi lampu, dengan flowchart, **tanpa istilah pemrograman** — buat dibaca siapa saja (termasuk dosen pembimbing) yang mau paham cara kerja sistem tanpa harus baca kode |
| [`../CLAUDE.md`](../CLAUDE.md) | Konteks proyek, konvensi, ringkasan arsitektur. Paling singkat, buat orientasi awal |
| [`data-contract.md`](data-contract.md) | Kontrak **semantik** antar modul — field apa saja yang ada dan artinya apa (gaya Pydantic, snake_case). Kalau ubah field yang menyeberang modul, sepakati di sini dulu |
| [`sop-demo-end-to-end.md`](sop-demo-end-to-end.md) | **Urutan nyalakan sistem sebelum demo/rekaman.** Wajib diikuti — kalau worker tidak jalan, dashboard diam-diam melewati kotak 7/8/9 tanpa error |
| [`MODEL-DAN-DATASET-CARD.md`](MODEL-DAN-DATASET-CARD.md) | Ringkasan model CV/LSTM/PPO, metrik yang boleh diklaim, serta keterbatasannya |

### Sesuai bagianmu

**Backend / integrasi API:**
- [`../backend/docs/data-contract.md`](../backend/docs/data-contract.md) — bentuk request/response endpoint yang **literal** + penamaan camelCase yang benar-benar dipakai kode. Beda dari `data-contract.md` root (itu konseptual, ini ejaan nyata)
- [`../backend/docs/traffic-state-builder.md`](../backend/docs/traffic-state-builder.md) — cara `TrafficState` dibangun
- [`database.md`](database.md) — skema database. ⚠️ Ini draft awal dan **sebagian sudah terbukti salah** (lihat banner di atas filenya). Kalau butuh skema pasti, cek langsung ke Supabase

**Frontend:**
- `KONTRAK-DIGITAL-TWIN-SCENARIOS.md` — ⚠️ **BELUM ADA.** Entri ini masuk lewat commit `40feb8c` (Yuli) tapi filenya tidak pernah dibuat — tidak ada di disk maupun riwayat git. Isinya direncanakan: endpoint tiga kandidat, mapping nama skenario, state UI, dan cara menjalankan kandidat terpilih di SUMO. Sementara belum ada, rujuk `kontrak-rekomendasi-scenario-generator.md` di bawah + kode `backend/app/api/routes/digital_twin.py`.
- [`kontrak-rekomendasi-scenario-generator.md`](kontrak-rekomendasi-scenario-generator.md) — arti tiap nilai `recommendation.source` dan kapan boleh menampilkan badge/metrik SUMO
- [`audit-kontrak-scenario-result.md`](audit-kontrak-scenario-result.md) — pemetaan field kontrak vs payload runtime

**LSTM / forecast:**
- [`rencana-lstm-forecast.md`](rencana-lstm-forecast.md) — apa yang diprediksi, dari data apa, kenapa begitu. **Dokumen desain, bukan status** — checklist di dalamnya sudah tidak dipelihara
- [`../forecasting/README.md`](../forecasting/README.md) — pipeline training & runtime

**Simulasi / SUMO:**
- [`rencana-scenario-generator.md`](rencana-scenario-generator.md) — arsitektur kotak 7-9, batasan yang sengaja ada. **Dokumen desain, bukan status**
- [`../simulation/README.md`](../simulation/README.md) — cara jalanin skrip simulasi

**Decision Engine / PPO:**
- [`../decision_engine/README-PPO.md`](../decision_engine/README-PPO.md) — penjelasan konseptual: beda LSTM vs PPO vs Rule-Based vs Scenario Generator. Baca ini dulu kalau belum pernah menyentuh reinforcement learning
- [`../decision_engine/README-PPO-UNTUK-TIM.md`](../decision_engine/README-PPO-UNTUK-TIM.md) — panduan operasional: instalasi, smoke test, training, evaluasi, pemasangan endpoint. ⚠️ Perintah di dalamnya memakai path `D:\LOMBA\kmipn\smarttwin`, sesuaikan dengan lokasi repo Anda

**CV:**
- [`../cv/CATATAN.md`](../cv/CATATAN.md) — catatan serah terima CV

**Setup pertama kali:**
- [`onboarding-notes.md`](onboarding-notes.md) — jebakan Windows, kebiasaan venv, cara set `SUMO_HOME`. Baca sebelum setup biar tidak mengulang debugging yang sama
- [`runbook-runpod.md`](runbook-runpod.md) — **cara menyalakan ulang sistem penuh di pod RunPod setelah Stop Pod**: apa yang hilang vs persisten, `runpod_setup.sh` + 3 terminal (backend/frontend/worker), pod ID/URL proxy, dan troubleshooting SUMO (DISPLAY/Xvfb, `findSumo`, route file)

---

## 🟠 HASIL UJI — bukti untuk laporan teknis

Jangan diubah. Ini yang dikutip di laporan dan dipakai menjawab juri.

| Dokumen | Membuktikan apa |
|---|---|
| [`hasil-studi-forecast.md`](hasil-studi-forecast.md) | Dampak forecast: delay −2,20s, antrean −7m, throughput +3 (satu snapshot) |
| [`hasil-studi-forecast-multi-snapshot.md`](hasil-studi-forecast-multi-snapshot.md) | Dampak forecast pada 20 snapshot satu sesi dengan horizon identik: delay 20/20, antrean 17/20, throughput 19/20; ketiganya membaik 17/20 |
| [`hasil-validasi-multisnapshot-multiseed.md`](hasil-validasi-multisnapshot-multiseed.md) | Kandidat `balanced` menang 7 dari 9 run (3 snapshot × 3 seed) |
| [`hasil-kalibrasi-kandidat-agresif.md`](hasil-kalibrasi-kandidat-agresif.md) | Kenapa kandidat agresif jadi +1 detik, bukan +20% (sweep 28–34 detik) — **digantikan rumus PKJI, lihat baris di bawah** |
| [`hasil-implementasi-pkji-aggressive-balanced.md`](hasil-implementasi-pkji-aggressive-balanced.md) | 5 Sep: kandidat `aggressive`/`balanced` sekarang dihitung dari rumus PKJI 2023 (Flow Ratio + koreksi Degree of Saturation), bukan tempelan heuristik lama. Asumsi yang harus disebut jujur ke juri + kalimat siap-jawab |
| [`hasil-run-antrean-25-agustus.md`](hasil-run-antrean-25-agustus.md) | Run CV 4 kamera × 43 menit, 538 jendela, data antrean asli |
| [`hasil-validasi-akurasi-cv.md`](hasil-validasi-akurasi-cv.md) | Akurasi deteksi CV vs hitung manual: 48,7% rata-rata (8 sampel) — dilaporkan apa adanya, bukan dipoles |
| [`audit-bug-ppo-sebelum-training-ke-5.md`](audit-bug-ppo-sebelum-training-ke-5.md) | Audit sistematis seluruh jalur PPO sebelum training v5: 11 bug terukur (E-P), termasuk 5 percobaan berbeda mengejar Bug P (fairness antar-lengan) yang akhirnya diterima sebagai keterbatasan terdokumentasi |
| [`hasil-evaluasi-ppo-v4-80k.md`](hasil-evaluasi-ppo-v4-80k.md) | Evaluasi checkpoint PPO v4 80k: perbaikan Bug A/B/D bertahan, tapi 2 bug baru (E & F). **Angkanya usang, sudah digantikan v5** — dipertahankan sebagai riwayat |
| [`hasil-evaluasi-ppo-v5.md`](hasil-evaluasi-ppo-v5.md) | Evaluasi resmi PPO v5 (checkpoint 60k, final): menang 7/seri 2/kalah 0 dari 9 perbandingan 3-seed vs rule-based. Termasuk penjelasan kenapa ini TIDAK berarti Bug P sudah selesai |

---

## Dokumen yang DIHAPUS 28 Agustus

Dihapus karena isinya sudah selesai atau **bertentangan** dengan kondisi kode sekarang. Riwayatnya tetap ada di git (`git log --diff-filter=D --name-only`).

| Dihapus | Alasan |
|---|---|
| `pembagian-tugas-tahap-akhir.md` | 307 baris, hampir semua checklist sudah selesai. Sisa item pindah ke `STATUS-DAN-SISA-KERJA.md` |
| `status-integrasi-diagram-arsitektur.md` | Temuan utamanya ("0% keputusan lewat simulasi") **sudah tidak berlaku** sejak integrasi cache skenario |
| `audit-24-agustus.md` | Semua temuannya sudah diperbaiki. Skor 62% menyesatkan |
| `pembagian-tugas-24-agustus.md` | Digantikan versi tahap akhir, yang juga sudah digantikan |
| `roadmap.md` | Berhenti disinkronkan 17 Agustus, sudah berbanner "superseded" sejak lama |
| `realtime-dashboard.md` | **Menyesatkan** — merujuk `vehicle_counter_copy.py` yang sudah tidak ada dan CSV yang sudah tidak dipakai ingest |

# Indeks Dokumentasi SmartTwin

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

---

## 🔵 CARA KERJA — rujukan teknis

### Wajib buat semua orang

| Dokumen | Isinya |
|---|---|
| [`../CLAUDE.md`](../CLAUDE.md) | Konteks proyek, konvensi, ringkasan arsitektur. Paling singkat, buat orientasi awal |
| [`data-contract.md`](data-contract.md) | Kontrak **semantik** antar modul — field apa saja yang ada dan artinya apa (gaya Pydantic, snake_case). Kalau ubah field yang menyeberang modul, sepakati di sini dulu |
| [`sop-demo-end-to-end.md`](sop-demo-end-to-end.md) | **Urutan nyalakan sistem sebelum demo/rekaman.** Wajib diikuti — kalau worker tidak jalan, dashboard diam-diam melewati kotak 7/8/9 tanpa error |

### Sesuai bagianmu

**Backend / integrasi API:**
- [`../backend/docs/data-contract.md`](../backend/docs/data-contract.md) — bentuk request/response endpoint yang **literal** + penamaan camelCase yang benar-benar dipakai kode. Beda dari `data-contract.md` root (itu konseptual, ini ejaan nyata)
- [`../backend/docs/traffic-state-builder.md`](../backend/docs/traffic-state-builder.md) — cara `TrafficState` dibangun
- [`database.md`](database.md) — skema database. ⚠️ Ini draft awal dan **sebagian sudah terbukti salah** (lihat banner di atas filenya). Kalau butuh skema pasti, cek langsung ke Supabase

**Frontend:**
- [`kontrak-rekomendasi-scenario-generator.md`](kontrak-rekomendasi-scenario-generator.md) — arti tiap nilai `recommendation.source` dan kapan boleh menampilkan badge/metrik SUMO
- [`audit-kontrak-scenario-result.md`](audit-kontrak-scenario-result.md) — pemetaan field kontrak vs payload runtime

**LSTM / forecast:**
- [`rencana-lstm-forecast.md`](rencana-lstm-forecast.md) — apa yang diprediksi, dari data apa, kenapa begitu. **Dokumen desain, bukan status** — checklist di dalamnya sudah tidak dipelihara
- [`../forecasting/README.md`](../forecasting/README.md) — pipeline training & runtime

**Simulasi / SUMO:**
- [`rencana-scenario-generator.md`](rencana-scenario-generator.md) — arsitektur kotak 7-9, batasan yang sengaja ada. **Dokumen desain, bukan status**
- [`../simulation/README.md`](../simulation/README.md) — cara jalanin skrip simulasi

**CV:**
- [`../cv/CATATAN.md`](../cv/CATATAN.md) — catatan serah terima CV

**Setup pertama kali:**
- [`onboarding-notes.md`](onboarding-notes.md) — jebakan Windows, kebiasaan venv, cara set `SUMO_HOME`. Baca sebelum setup biar tidak mengulang debugging yang sama

---

## 🟠 HASIL UJI — bukti untuk laporan teknis

Jangan diubah. Ini yang dikutip di laporan dan dipakai menjawab juri.

| Dokumen | Membuktikan apa |
|---|---|
| [`hasil-studi-forecast.md`](hasil-studi-forecast.md) | Dampak forecast: delay −2,20s, antrean −7m, throughput +3 (satu snapshot) |
| [`hasil-validasi-multisnapshot-multiseed.md`](hasil-validasi-multisnapshot-multiseed.md) | Kandidat `balanced` menang 7 dari 9 run (3 snapshot × 3 seed) |
| [`hasil-kalibrasi-kandidat-agresif.md`](hasil-kalibrasi-kandidat-agresif.md) | Kenapa kandidat agresif jadi +1 detik, bukan +20% (sweep 28–34 detik) |
| [`hasil-run-antrean-25-agustus.md`](hasil-run-antrean-25-agustus.md) | Run CV 4 kamera × 43 menit, 538 jendela, data antrean asli |

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

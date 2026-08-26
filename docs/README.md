# Indeks Dokumen — mulai dari sini

Ditulis 27 Agustus 2026 setelah bersih-bersih dokumen (2 file dihapus karena basi/duplikat-membingungkan, 2 file diberi banner peringatan karena sebagian isinya sudah terbukti salah/usang — lihat bagian "Sudah dibersihkan" di bawah). Kalau bingung mulai baca dari mana, ikuti urutan di bagian 1.

---

## 1. WAJIB dibaca semua orang, urutannya begini

1. **`../CLAUDE.md`** (root repo) — konteks proyek, konvensi, ringkasan arsitektur pipa data. Paling singkat, paling penting buat orientasi awal.
2. **`data-contract.md`** — kontrak schema resmi antar-modul (CV → Traffic State → Forecast → Simulasi → Decision Engine). Kalau ubah field apa pun yang menyeberang modul, ini yang harus disepakati dulu.
3. **`pembagian-tugas-tahap-akhir.md`** — **dokumen paling penting di seluruh repo.** Status kerjaan terkini, siapa pegang apa, checklist per item, dan section 6-8 berisi peta status arsitektur + rencana integrasi yang sedang berjalan. Kalau cuma boleh baca SATU dokumen, baca ini.
4. **`status-integrasi-diagram-arsitektur.md`** — jawaban jujur "apakah sistem ini sudah jalan selaras seperti diagram arsitektur". Penting buat semua orang karena temuannya (jalur live dan jalur simulasi itu 2 pipeline terpisah) memengaruhi kerjaan semua orang sekarang.

## 2. Baca sesuai bagianmu

**Yuli (LSTM + kerjaan cache baru):**
- `rencana-lstm-forecast.md` — desain forecast, status tiap fitur, keterbatasan yang harus ditulis jujur di laporan
- `rencana-scenario-generator.md` bagian 4.1 — rancangan `scenario_worker.py` (cache background job) yang jadi kerjaan utama sekarang

**Melpi (frontend + kerjaan SUMO baru):**
- `realtime-dashboard.md` — cara dashboard narik data live, kenapa desainnya begini (bagian video/TrafficState fetch — TIDAK mencakup siklus lampu, itu lebih baru, ada di `pembagian-tugas-tahap-akhir.md` item 1.7)
- `rencana-scenario-generator.md` bagian 4.1 ("Melpi — frontend") dan 4.2 (siklus 4-lengan ke SUMO — domain baru, beda dari frontend biasa, baca pelan-pelan)

**Rahmat (backend/CV, kapasitas terbatas sekarang):**
- `hasil-run-antrean-25-agustus.md` — detail run CV antrean kalau perlu rujukan teknis
- `onboarding-notes.md` — kalau setup ulang environment di mesin baru

## 3. Historis — background/konteks, TIDAK perlu dibaca kecuali penasaran "kenapa begini"

Bukan basi karena isinya salah, tapi karena statusnya sudah digantikan dokumen yang lebih baru. Aman dilewati kalau cuma mau tahu status SEKARANG (baca bagian 1 saja).

- `audit-24-agustus.md` — audit menyeluruh 24 Agustus, cikal-bakal `pembagian-tugas-24-agustus.md`
- `pembagian-tugas-24-agustus.md` — versi SEBELUM `pembagian-tugas-tahap-akhir.md`, masih dirujuk dokumen saat ini sebagai riwayat, bukan status aktif
- `roadmap.md` — rencana 16-hari ASLI, berhenti disinkronkan 17 Agustus. **Sudah diberi banner peringatan** di bagian atas file — jangan jadikan acuan status, cuma untuk lihat scope/timeline awal

## 4. Hati-hati — sebagian isinya sudah terbukti salah

- **`database.md`** — draft skema database awal (2131 baris, belum dirapikan dari transkrip obrolan). Minimal SATU bagian (skema `simulationMetrics`) sudah terbukti tidak cocok dengan skema Supabase yang sebenarnya — **sudah diberi banner peringatan** di bagian atas file. Kalau butuh skema tabel yang benar, cek langsung ke Supabase, jangan percaya dokumen ini mentah-mentah.

---

## Sudah dibersihkan 27 Agustus 2026

**Dihapus** (basi total, nol referensi valid dari dokumen lain, tidak ada info yang hilang — semua sudah tercakup dokumen lebih baru):
- `PROGRESS_REPORT.md` (root) — snapshot status 22 Agustus, seluruh rekomendasinya sudah dikerjakan/digantikan (Scenario Generator, kalibrasi north, keputusan PPO, dst.), nol dokumen lain yang merujuknya
- `backend/docs/data-contract.md` — **nama sama** dengan `docs/data-contract.md` di atas tapi ISINYA BEDA dan SALING KONTRADIKSI (yang di backend maksa camelCase mutlak, padahal kontrak resmi pakai snake_case di level Python dengan alias camelCase di JSON) — draft lama dari 19 Agustus sebelum kontrak resmi ditetapkan, nol referensi valid selain dari `PROGRESS_REPORT.md` yang juga dihapus

**Diberi banner peringatan, TIDAK dihapus** (masih dirujuk dokumen lain / masih ada nilai historis, tapi isinya sebagian sudah usang/salah — lihat bagian 3 dan 4 di atas):
- `roadmap.md`, `database.md`

**`CLAUDE.md`** juga diperbarui — sebelumnya menyebut `roadmap.md` sebagai "plan of record" (sudah tidak akurat), sekarang menunjuk ke `pembagian-tugas-tahap-akhir.md`.

---

## Dokumen di luar `docs/` (referensi per-modul, baca kalau kerja di modul itu)

- `backend/README.md`, `backend/docs/traffic-state-builder.md` — detail internal backend
- `frontend/README.md` — setup & struktur frontend
- `simulation/README.md` — setup simulasi SUMO
- `forecasting/README.md` — pipeline training LSTM (agregat + per-approach)
- `cv/CATATAN.md`, `cv/_arsip/` — catatan CV, `_arsip/` memang sudah ditandai sendiri sebagai arsip

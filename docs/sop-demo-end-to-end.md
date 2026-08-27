# SOP Demo End-to-End SmartTwin

SOP ini menjalankan alur `ingest -> backend -> worker -> verifikasi cache ->
SUMO`. Gunakan terminal PowerShell terpisah untuk proses yang harus tetap hidup.
Frontend tidak perlu diubah oleh SOP ini.

## 0. Prasyarat

- Jalankan semua perintah dari root repository kecuali disebut lain.
- Pastikan `backend/.env` berisi kredensial Supabase yang benar.
- Pastikan tabel `liveScenarioCache` sudah dibuat menggunakan
  `backend/app/db/live_scenario_cache.sql`.
- Gunakan `simulation/.venv` untuk worker/SUMO dan `backend/.venv` untuk backend.
- Jika SUMO tidak ditemukan otomatis, export `SUMO_HOME` sesuai `CLAUDE.md`.

## 1. Ingest hasil CV

Jalankan setelah CSV CV terbaru selesai dibuat:

```powershell
backend\.venv\Scripts\python.exe run_ingest.py
```

Perintah aman diulang karena ingest memakai upsert. Pastikan output tidak berisi
exception dan jumlah window yang diproses tidak nol.

## 2. Jalankan backend

Terminal kedua:

```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Verifikasi:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Hasil yang diharapkan: `status = ok`.

## 3. Isi cache sekali untuk smoke test

Terminal ketiga:

```powershell
cd simulation
.venv\Scripts\python.exe scenario_worker.py --once --full-cycle
```

Hasil yang diharapkan:

- tiga kandidat SUMO selesai diuji;
- satu kandidat terpilih;
- muncul `Cache diperbarui ...`; dan
- exit code proses adalah 0.

## 4. Verifikasi backend membaca cache

```powershell
$body = @{ intersectionId = "simpang4-pingit" } | ConvertTo-Json
$result = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/recommendation -ContentType "application/json" -Body $body
$result.recommendation | Select-Object source,candidateId,avgDelaySeconds,avgQueueLengthM,los
```

Saat cache segar, `source` harus `scenario-generator` dan field kandidat/delay/
antrean/LOS tidak kosong.

## 5. Jalankan worker terus-menerus untuk demo

Setelah smoke test berhasil:

```powershell
cd simulation
.venv\Scripts\python.exe scenario_worker.py --full-cycle --interval 60
```

Biarkan terminal ini terbuka. Backend menganggap cache basi setelah 120 detik,
jadi interval 60 detik menyediakan satu kesempatan retry sebelum fallback.
Satu iterasi gagal tidak mematikan worker.

## 6. Verifikasi fallback aman

Untuk uji manual tanpa mengubah atau menghapus data, hentikan worker dengan
`Ctrl+C`, tunggu lebih dari 120 detik, lalu ulangi request pada langkah 4.
Endpoint harus tetap HTTP 200 dan `source` kembali ke `rule-based`,
`rule-based+forecast`, atau fallback yang sesuai kondisi data.

Cache rusak/tabel tidak tersedia diverifikasi otomatis oleh test, bukan dengan
merusak tabel demo:

```powershell
cd backend
$env:DEBUG = "false"
.venv\Scripts\python.exe -m pytest -q tests\test_live_scenario_cache.py
```

## 7. Jalankan SUMO penuh dan simpan metrik

Ini terpisah dari worker cache dan dipakai untuk bukti persistence E2E:

```powershell
cd simulation
.venv\Scripts\python.exe run_tls_simulation.py
```

Hasil yang wajib terlihat:

- `STATUS: SUCCESS`;
- `Simulation ID` tidak kosong; dan
- metrik delay/queue/throughput berhasil disimpan ke `simulationMetrics`.

## 8. Checklist H-1 dan sebelum presentasi

- [ ] CSV CV terbaru sudah di-ingest.
- [ ] Backend health menghasilkan `status=ok`.
- [ ] Worker `--full-cycle` hidup dan memperbarui cache tiap 60 detik.
- [ ] `/recommendation.source` adalah `scenario-generator`.
- [ ] `candidateId`, delay, antrean, dan LOS terisi.
- [ ] Satu run SUMO penuh terakhir menghasilkan `STATUS: SUCCESS`.
- [ ] Terminal backend dan worker tidak menampilkan error berulang.

## 9. Pemulihan cepat

- Worker gagal sekali: tunggu iterasi berikutnya; backend tetap tersedia lewat
  fallback.
- Worker gagal berulang: jalankan `--once --full-cycle` untuk memperoleh error
  dan exit code yang jelas.
- Backend gagal start: periksa port 8000 dan nilai boolean `DEBUG` di environment.
- Forecast tidak tersedia: sistem otomatis memakai TrafficState aktual.
- Supabase tidak tersedia: jangan merombak frontend; pulihkan koneksi dan ulangi
  smoke test.

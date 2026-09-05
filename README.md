# SmartTwin — Digital Twin Adaptif untuk Simpang Bersinyal

SmartTwin adalah sistem pemantauan dan pengambilan keputusan lalu lintas yang
menghubungkan Computer Vision, peramalan LSTM, simulasi SUMO, serta decision
engine rule-based/PPO dalam satu dashboard. Studi kasus yang digunakan adalah
Simpang Empat Pingit, Yogyakarta.

Sistem menerima rekaman atau stream CCTV, mengubah hasil deteksi kendaraan
menjadi kondisi lalu lintas per lengan, memprediksi kondisi berikutnya,
menguji beberapa skenario pengaturan lampu di digital twin, lalu menampilkan
rekomendasi dan metrik hasil simulasi kepada pengguna.

> Status proyek, pekerjaan yang sudah selesai, dan pekerjaan yang masih terbuka
> dicatat di [docs/STATUS-DAN-SISA-KERJA.md](docs/STATUS-DAN-SISA-KERJA.md).
> Catatan perapian repository dan hasil audit terbaru ada di
> [docs/CATATAN-PERAPIAN-DAN-HASIL-AUDIT.md](docs/CATATAN-PERAPIAN-DAN-HASIL-AUDIT.md).

## Alur sistem

```text
CCTV / Video
     |
     v
YOLO + ByteTrack
     |
     v
Traffic State Builder ---> LSTM Forecast
     |                         |
     +-------------------------+
     |
     v
Scenario Generator / Decision Engine
     |
     v
SUMO Digital Twin
     |
     v
Analisis Kinerja dan Rekomendasi Lampu
     |
     v
Dashboard Next.js
```

## Modul utama

| Direktori | Tanggung jawab |
|---|---|
| `cv/` | Deteksi, tracking, crossing count, dan ekstraksi metrik CCTV |
| `backend/` | API FastAPI, integrasi Supabase/Hugging Face, dan orkestrasi layanan |
| `forecasting/` | Persiapan data, training, evaluasi, dan inferensi LSTM |
| `decision_engine/` | Decision engine rule-based, PPO, training, dan evaluasi |
| `simulation/` | Network SUMO, scenario generator, worker, dan evaluasi simulasi |
| `frontend/` | Dashboard Next.js, autentikasi, CCTV, rekomendasi, dan digital twin |
| `docs/` | Status resmi, kontrak data, SOP demo, dan bukti pengujian |

## Teknologi

- Backend: Python, FastAPI, Pydantic, Supabase, dan Hugging Face Hub.
- Frontend: Next.js, React, TypeScript, Tailwind CSS, dan Recharts.
- Computer Vision: YOLO, ByteTrack, dan OpenCV.
- Forecasting: PyTorch LSTM.
- Decision engine: rule-based dan PPO dengan Stable-Baselines3/Gymnasium.
- Digital twin: Eclipse SUMO dan TraCI.

## Persiapan lokal

Prasyarat utama:

- Python 3.10 atau versi yang kompatibel dengan dependency proyek.
- Node.js dan npm.
- Akun/proyek Supabase.
- Token Hugging Face bila fitur penyimpanan video digunakan.

Salin template environment dan isi nilainya tanpa memasukkan secret ke Git:

```powershell
Copy-Item .env.example .env
```

Environment frontend dibuat terpisah pada `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
AUTH_REQUIRED=false
OPERATOR_ROLES=operator,admin,service_role
MAX_VIDEO_UPLOAD_BYTES=1073741824
```

`SUPABASE_SERVICE_ROLE_KEY` hanya boleh digunakan di server dan tidak boleh
diberi prefix `NEXT_PUBLIC_`.

Untuk deployment publik, ubah `AUTH_REQUIRED=true`. Endpoint mutasi backend
kemudian membutuhkan access token Supabase dan role operator/admin pada
`app_metadata.role`. Nilai `false` ditujukan untuk demo lokal yang terisolasi.

## Menjalankan backend

Dari root repository:

```powershell
python -m venv backend/.venv
backend\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Untuk menjalankan demo secara stabil, gunakan perintah berikut **tanpa
`--reload`**:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
```

Mode ini disarankan ketika menjalankan CCTV dan Digital Twin. SUMO akan terus
berjalan di background selama proses backend tidak ditutup. Durasi rekaman
CCTV yang berulang tidak menghentikan SUMO; kendaraan tetap diperbarui dan
fase Signal Status mengikuti clock CCTV.

Secara default scenario worker tidak ikut dimulai ketika backend hidup, sehingga
SUMO baru berjalan saat UI memintanya. Timeline dashboard tetap mengulang sumber
rekaman ketika habis. Autostart Scenario Generator dapat diaktifkan secara
opsional dengan `SCENARIO_WORKER_AUTOSTART=true`; mode ini langsung menjalankan
tiga kandidat SUMO di background.

Untuk pengembangan kode backend, hot reload dapat diaktifkan secara terpisah:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 5
```

> **Catatan:** setiap perubahan file pada mode `--reload` membuat Uvicorn
> mematikan instance backend lama dan memulai instance baru. Controller SUMO
> juga berhenti selama proses reload, sehingga mode ini tidak disarankan saat
> demo atau simulasi jangka panjang.

Dokumentasi API tersedia di `http://127.0.0.1:8000/docs`.

## Menjalankan frontend

```powershell
Set-Location frontend
npm install
npm run dev
```

Dashboard dapat dibuka melalui `http://localhost:3000`.

## Menjalankan scenario worker secara manual

Worker dapat dijalankan dari root repository bila hasil perbandingan tiga
kandidat Scenario Generator memang diperlukan:

```powershell
backend\.venv\Scripts\python.exe simulation\scenario_worker.py --replay --full-cycle --interval 60
```

Untuk urutan demo lengkap, gunakan
[docs/sop-demo-end-to-end.md](docs/sop-demo-end-to-end.md).

## Pengujian

Backend:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend:

```powershell
Set-Location frontend
npm run lint
npm run build
```

Sebagian test backend mengakses Supabase secara langsung. Kegagalan koneksi
tidak selalu berarti unit test rusak; periksa apakah environment dan akses
jaringan tersedia. Tetap bedakan kegagalan koneksi eksternal dari kegagalan
kontrak endpoint atau logika lokal.

## Sumber data utama

| Data | Penghasil | Konsumen utama |
|---|---|---|
| `trafficLaneMetrics` | CV | Traffic State Builder |
| `trafficStates` | Backend | Dashboard, LSTM, PPO, dan SUMO |
| `trafficApproachStates` | Traffic State Builder | LSTM, PPO, dashboard, dan SUMO |
| `forecastPredictions` | LSTM | Decision engine, dashboard, dan simulasi |
| `recommendations` | Decision engine/scenario generator | Dashboard dan pengontrol sinyal |
| `simulationMetrics` | SUMO | Dashboard dan evaluasi |

Kontrak field lintas modul dijelaskan di
[docs/data-contract.md](docs/data-contract.md), sedangkan bentuk request dan
response backend dijelaskan di
[backend/docs/data-contract.md](backend/docs/data-contract.md).

## Dokumentasi penting

- [Indeks dokumentasi](docs/README.md)
- [Status dan sisa kerja](docs/STATUS-DAN-SISA-KERJA.md)
- [Catatan perapian dan hasil audit](docs/CATATAN-PERAPIAN-DAN-HASIL-AUDIT.md)
- [Alur sistem nonteknis](docs/alur-kerja-sistem-non-teknis.md)
- [SOP demo end-to-end](docs/sop-demo-end-to-end.md)
- [Penjelasan progres per modul](docs/penjelasan-progres-per-modul.md)

## Aturan kontribusi singkat

1. Jangan commit `.env`, `.env.local`, token, dataset besar, cache, atau video.
2. Perubahan kontrak data harus diperiksa pada CV, backend, forecasting,
   simulation, decision engine, dan frontend yang menggunakannya.
3. Jalankan test/lint yang relevan sebelum menyerahkan perubahan.
4. Jangan membuat dokumen status baru. Perbarui dokumen status resmi yang
   sudah ada agar informasi tim tidak saling bertentangan.
5. Catat pekerjaan perapian atau hasil audit di dokumen khusus, tanpa menandai
   temuan sebagai selesai sebelum implementasi dan verifikasinya benar-benar ada.

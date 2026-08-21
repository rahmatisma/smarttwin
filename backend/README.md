# SmartTwin Backend

Backend API untuk **SmartTwin Traffic Digital Twin**.

Backend menjadi penghubung antara **Computer Vision, Traffic State Builder, database Supabase, forecasting, recommendation engine, simulation, dan frontend Next.js**.

```text
YOLO + ByteTrack
       │
       ▼
Traffic State Builder
       │
       ▼
FastAPI Backend
       │
       ├──► Supabase PostgreSQL
       │
       ├──► Forecast
       │
       ├──► Recommendation
       │
       └──► Simulation
              │
              ▼
        Next.js Frontend
```

---

# 1. Tech Stack

| Komponen          | Teknologi              |
| ----------------- | ---------------------- |
| Backend Framework | FastAPI                |
| Language          | Python 3.10+           |
| Validation        | Pydantic v2            |
| Server            | Uvicorn                |
| Database          | Supabase PostgreSQL    |
| Database Client   | Supabase Python Client |
| Testing           | Pytest                 |
| Computer Vision   | YOLO + ByteTrack       |
| Forecast          | LSTM / model forecast  |
| Simulation        | SUMO                   |
| Recommendation    | PPO / rule-based       |
| Video Storage     | Hugging Face Hub       |
| Frontend          | Next.js                |

---

# 2. Arsitektur Sistem

Secara umum SmartTwin bekerja dengan alur berikut:

```text
                       SMARTTWIN
                           │
                           ▼
                  ┌─────────────────┐
                  │  CCTV / Video   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ YOLO + ByteTrack│
                  └────────┬────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Traffic State       │
                │ Builder              │
                └──────────┬──────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ FastAPI Backend │
                  └────────┬────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        Supabase       Forecast     Recommendation
        PostgreSQL
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                     Simulation
                        (SUMO)
                           │
                           ▼
                    Next.js Dashboard
```

---

# 3. Struktur Backend

```text
backend/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── health.py
│   │       ├── traffic.py
│   │       ├── signal.py
│   │       ├── forecast.py
│   │       ├── recommendation.py
│   │       └── cctv.py
│   │
│   ├── schemas/
│   │   ├── traffic.py
│   │   ├── signal.py
│   │   ├── forecast.py
│   │   └── recommendation.py
│   │
│   ├── services/
│   │   ├── traffic_service.py
│   │   ├── signal_service.py
│   │   ├── forecast_service.py
│   │   ├── recommendation_service.py
│   │   ├── supabase_client.py
│   │   ├── cctv_service.py
│   │   ├── hf_storage_service.py
│   │   ├── cv_trigger_service.py
│   │   └── ws_manager.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   ├── base.py
│   │   ├── models/
│   │   │   ├── intersection.py
│   │   │   ├── approach.py
│   │   │   ├── lane.py
│   │   │   ├── camera.py
│   │   │   ├── video.py
│   │   │   ├── processing_job.py
│   │   │   ├── traffic_state.py
│   │   │   ├── forecast.py
│   │   │   ├── signal_status.py
│   │   │   ├── recommendation.py
│   │   │   └── simulation.py
│   │   │
│   │   └── repositories/
│   │       ├── traffic_repository.py
│   │       ├── cctv_repository.py
│   │       ├── forecast_repository.py
│   │       ├── signal_repository.py
│   │       ├── recommendation_repository.py
│   │       └── simulation_repository.py
│   │
│   ├── pipeline/
│   │   └── traffic_state_builder.py
│   │
│   ├── models/
│   │   ├── yolo/
│   │   ├── lstm/
│   │   └── ppo/
│   │
│   ├── simulation/
│   │   ├── sumo/
│   │   └── scenarios/
│   │
│   └── core/
│       └── config.py
│
├── cv/
│
├── tests/
│
├── migrations/
│
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

---

# 4. Fungsi Setiap Folder

## 4.1 `app/`

Folder utama aplikasi backend.

Semua logic utama FastAPI berada di dalam folder ini.

```text
app/
├── api/
├── schemas/
├── services/
├── db/
├── pipeline/
├── models/
├── simulation/
└── core/
```

---

# 5. `app/main.py`

`main.py` adalah **entry point FastAPI**.

File ini bertugas membuat aplikasi FastAPI dan mendaftarkan router.

Secara konsep:

```text
main.py
   │
   ├── membuat FastAPI()
   │
   ├── mendaftarkan route
   │
   └── menjalankan API
```

Ketika menjalankan:

```bash
uvicorn app.main:app --reload
```

Uvicorn mencari object:

```text
app.main
    └── app
```

kemudian menjalankan aplikasi FastAPI tersebut.

---

# 6. `app/api/routes/`

Folder ini berisi **endpoint API**.

Route bertugas menerima request dari frontend atau service lain, kemudian meneruskannya ke service yang sesuai.

Contoh:

```text
Frontend
   │
   │ GET /api/v1/traffic/latest
   ▼
traffic.py
   │
   ▼
traffic_service.py
   │
   ▼
Supabase
```

### File

| File                | Fungsi                          |
| ------------------- | ------------------------------- |
| `health.py`         | Mengecek apakah backend hidup   |
| `traffic.py`        | Endpoint traffic state          |
| `signal.py`         | Endpoint status lampu           |
| `forecast.py`       | Endpoint forecasting            |
| `recommendation.py` | Endpoint rekomendasi            |
| `cctv.py`           | Upload dan streaming video CCTV |

---

# 7. `app/schemas/`

Schema berisi **bentuk data yang masuk dan keluar dari API**.

Schema menggunakan Pydantic.

Contoh:

```text
Frontend
   │
   │ JSON
   ▼
Pydantic Schema
   │
   │ valid?
   ├── tidak → HTTP 422
   │
   └── ya
        │
        ▼
      Service
```

Schema menjadi **contract** antara backend dan frontend.

Contoh field traffic:

```text
queueLengthVeh
queueLengthMEst
densityIndex
avgSpeedKmh
```

Frontend tidak boleh membuat nama field sendiri seperti:

```text
queue
density
speed
avgQueue
trafficDensity
```

jika field tersebut tidak ada di contract.

---

# 8. `app/services/`

Service berisi **business logic** aplikasi.

Route sebaiknya tidak berisi seluruh logic database, forecasting, upload file, dan sebagainya.

Contoh:

```text
traffic.py
    │
    ▼
traffic_service.py
    │
    ▼
Supabase
```

### Service utama

| File                        | Fungsi                                     |
| --------------------------- | ------------------------------------------ |
| `traffic_service.py`        | Logic pengambilan dan pengolahan traffic   |
| `signal_service.py`         | Logic status lampu                         |
| `forecast_service.py`       | Logic forecasting                          |
| `recommendation_service.py` | Logic recommendation                       |
| `supabase_client.py`        | Membuat/menyediakan client Supabase        |
| `cctv_service.py`           | Orkestrasi upload CCTV                     |
| `hf_storage_service.py`     | Upload/akses video di Hugging Face         |
| `cv_trigger_service.py`     | Menjalankan proses CV setelah video upload |
| `ws_manager.py`             | Mengelola koneksi WebSocket dashboard      |

---

# 9. `app/db/`

Folder database backend.

```text
app/db/
├── database.py
├── base.py
├── models/
└── repositories/
```

Folder ini bertugas mengorganisasi akses database jika backend menggunakan layer database/ORM.

## `database.py`

Biasanya berisi konfigurasi koneksi database dan session.

## `base.py`

Digunakan sebagai base untuk model database jika menggunakan SQLAlchemy ORM.

## `models/`

Berisi representasi tabel database sebagai model Python.

Contoh:

```text
models/
├── intersection.py
├── approach.py
├── lane.py
├── camera.py
└── traffic_state.py
```

## `repositories/`

Repository bertugas menangani operasi database yang spesifik.

Contoh:

```text
traffic_repository.py
```

dapat menangani:

```text
get_latest_traffic()
get_traffic_history()
save_traffic_state()
```

Dengan demikian service tidak perlu mengetahui detail query database secara langsung.

---

# 10. Supabase

SmartTwin menggunakan **Supabase sebagai PostgreSQL cloud database**.

Secara konsep:

```text
Backend
   │
   │ Supabase Python Client
   ▼
Supabase
   │
   ▼
PostgreSQL
```

Database tidak perlu dijalankan sebagai PostgreSQL server lokal di setiap laptop.

Backend cukup memiliki konfigurasi:

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

Client Supabase kemudian digunakan oleh service:

```python
supabase = get_supabase()
```

dan dapat melakukan operasi seperti:

```python
supabase.table("trafficStates").select("*").execute()
```

---

# 11. `app/pipeline/`

Folder ini berisi pipeline pengolahan traffic.

File utama:

```text
traffic_state_builder.py
```

Traffic State Builder bertugas mengubah data hasil Computer Vision menjadi struktur traffic state yang sesuai contract.

Alurnya:

```text
YOLO + ByteTrack
       │
       ▼
Traffic Lane Metrics
       │
       ▼
Traffic State Builder
       │
       ├── TrafficState
       │
       └── ApproachState
```

Jadi Traffic State Builder bukan database.

Ia adalah **processing layer**.

Database digunakan sebagai **persistence layer**.

---

# 12. `app/models/`

Folder ini digunakan untuk model machine learning.

```text
models/
├── yolo/
├── lstm/
└── ppo/
```

### `yolo/`

Berisi model atau konfigurasi Computer Vision.

### `lstm/`

Berisi model forecasting apabila LSTM digunakan.

### `ppo/`

Berisi model reinforcement learning untuk adaptive traffic signal recommendation.

---

# 13. `app/simulation/`

Folder untuk Digital Twin dan simulasi SUMO.

```text
simulation/
├── sumo/
└── scenarios/
```

### `sumo/`

Berisi konfigurasi/integrasi SUMO.

### `scenarios/`

Berisi skenario simulasi.

Contoh:

```text
Scenario A
Current Signal Timing

Scenario B
Recommended Signal Timing
```

Hasil simulasi kemudian dapat dibandingkan menggunakan:

```text
Delay
Queue
Throughput
Waiting Time
Emission
```

---

# 14. `app/core/`

Berisi konfigurasi dasar aplikasi.

File utama:

```text
config.py
```

Biasanya digunakan untuk membaca:

```text
.env
```

Contoh konfigurasi:

```env
APP_NAME=SmartTwin Backend
APP_VERSION=0.1.0
DEBUG=true

CORS_ORIGINS=http://localhost:3000

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

HF_TOKEN=
HF_REPO_ID=rahmatisma/smarttwin-cctv
```

**Secret tidak boleh dimasukkan ke Git.**

Gunakan:

```text
.env
```

untuk nilai sebenarnya.

Sedangkan:

```text
.env.example
```

hanya menjadi template.

---

# 15. `tests/`

Berisi automated test untuk backend.

Contoh:

```text
tests/
├── test_database_connection.py
├── test_database_tables.py
└── test_traffic_state_repository.py
```

Test dapat dijalankan menggunakan:

```bash
python -m pytest -q
```

atau test tertentu:

```bash
python -m pytest tests/test_database_connection.py -q
```

---

# 16. `migrations/`

Folder untuk menyimpan perubahan struktur database apabila nantinya digunakan migration system.

Contoh perubahan:

```text
Migration 001
Create intersections

Migration 002
Create approaches

Migration 003
Create traffic states
```

Tujuannya agar perubahan schema dapat dilacak dan direproduksi.

---

# 17. `cv/`

Folder Computer Vision memiliki environment/dependency yang dapat dipisahkan dari backend.

Alurnya:

```text
FastAPI
   │
   │ trigger
   ▼
cv/process_uploaded_video.py
   │
   ▼
YOLO + ByteTrack
   │
   ▼
Traffic Metrics
   │
   ▼
Supabase
```

Backend dapat menjalankan proses CV sebagai subprocess.

Hal ini membuat dependency CV seperti:

```text
torch
ultralytics
opencv
```

tidak harus dicampur dengan dependency utama FastAPI.

---

# 18. Bagaimana FastAPI Bekerja?

FastAPI dapat dipahami sebagai **pintu masuk sistem backend**.

Contoh user membuka dashboard:

```text
Next.js
   │
   │ HTTP Request
   ▼
FastAPI
   │
   ▼
Route
   │
   ▼
Service
   │
   ▼
Database / Model / Storage
   │
   ▼
Response
   │
   ▼
Next.js
```

Misalnya frontend meminta:

```http
GET /api/v1/traffic/latest
```

Maka:

```text
1. Request masuk ke FastAPI

2. FastAPI mencari route traffic

3. Route memanggil traffic_service

4. Service mengambil data

5. Data divalidasi menggunakan Pydantic

6. FastAPI mengembalikan JSON

7. Frontend menerima JSON
```

---

# 19. Contoh Request FastAPI

Misalnya frontend mengirim:

```http
POST /api/v1/traffic/state
```

dengan JSON:

```json
{
  "intersectionId": "simpang4-pingit",
  "windowStart": "2026-08-22T10:00:00Z",
  "windowEnd": "2026-08-22T10:00:05Z",
  "approaches": []
}
```

FastAPI:

```text
Request
   │
   ▼
Route
   │
   ▼
Pydantic Schema
   │
   ├── invalid → 422
   │
   └── valid
        │
        ▼
      Service
        │
        ▼
     Supabase
```

---

# 20. FastAPI Dalam SmartTwin

FastAPI bukan tempat semua proses dilakukan.

FastAPI bertindak sebagai **orchestrator/API layer**.

```text
                    FASTAPI
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
   Supabase        Hugging Face       CV Process
       │               │                │
       │               │                ▼
       │               │           YOLO + ByteTrack
       │               │                │
       │               │                ▼
       │               │         Traffic State Builder
       │               │
       └───────────────┼────────────────┘
                       │
                       ▼
                  API Response
                       │
                       ▼
                 Next.js Dashboard
```

---

# 21. CCTV Upload Flow

Ketika user meng-upload video CCTV:

```text
Next.js
   │
   │ multipart/form-data
   ▼
POST /api/v1/cctv/upload
   │
   ▼
FastAPI
   │
   ├──────────────► Hugging Face
   │                 │
   │                 └── menyimpan file video
   │
   ├──────────────► Supabase
   │                 │
   │                 └── menyimpan metadata video
   │
   └──────────────► CV Trigger
                       │
                       ▼
                    YOLO +
                   ByteTrack
                       │
                       ▼
                Traffic Metrics
                       │
                       ▼
                    Supabase
```

Database menyimpan **metadata**, bukan file video besar.

---

# 22. Hugging Face

Hugging Face digunakan sebagai storage untuk video CCTV.

```text
Frontend
    │
    ▼
FastAPI
    │
    ├──────────► Supabase
    │             metadata
    │
    └──────────► Hugging Face
                  video file
```

Environment:

```env
HF_TOKEN=
HF_REPO_ID=rahmatisma/smarttwin-cctv
```

Token Hugging Face adalah secret dan tidak boleh di-commit.

---

# 23. Traffic Realtime

SmartTwin menggunakan WebSocket untuk mengirim update traffic secara realtime ke dashboard.

```text
CV Processing
      │
      │ window selesai
      ▼
POST /api/v1/traffic/notify
      │
      ▼
FastAPI
      │
      ▼
TrafficWsManager
      │
      │ WebSocket broadcast
      ▼
Next.js Dashboard
```

Dashboard cukup membuka:

```text
/ws
```

dan mempertahankan koneksi.

Tidak diperlukan polling berkala seperti:

```text
GET
GET
GET
GET
GET
```

secara terus-menerus.

---

# 24. Traffic Data — Source of Truth

Contract traffic menjadi sumber kebenaran antara:

```text
CV
Backend
Forecast
Frontend
```

Field utama:

```text
queueLengthVeh
queueLengthMEst
densityIndex
avgSpeedKmh
```

### `avgSpeedKmh`

Jika tersedia:

```text
avgSpeedKmh = nilai speed
```

Jika tidak tersedia:

```text
avgSpeedKmh = null
```

Frontend harus menampilkan:

```text
N/A
```

Jangan mengubah:

```text
null
```

menjadi:

```text
0
```

karena:

```text
null ≠ 0
```

`null` berarti data tidak tersedia.

---

# 25. Traffic Metrics

### `queueLengthVeh`

Estimasi jumlah kendaraan yang sedang berada dalam antrean.

### `queueLengthMEst`

Estimasi panjang antrean dalam meter.

Nilai ini adalah:

```text
estimasi
```

dan bukan pengukuran meter yang sepenuhnya terkalibrasi.

### `densityIndex`

`densityIndex` adalah index kepadatan yang digunakan sistem.

**Bukan `vehicles/km`.**

Jangan menginterpretasikannya sebagai satuan kendaraan per kilometer.

---

# 26. Endpoint

| Method    | Endpoint                                | Fungsi                           |
| --------- | --------------------------------------- | -------------------------------- |
| GET       | `/api/health`                           | Cek backend                      |
| GET       | `/api/traffic/latest`                   | Ambil traffic terbaru            |
| POST      | `/api/traffic/state`                    | Kirim traffic state              |
| GET       | `/api/signal/status`                    | Status lampu                     |
| POST      | `/api/signal/status`                    | Update status lampu              |
| POST      | `/api/forecast`                         | Prediksi traffic                 |
| POST      | `/api/recommendation`                   | Rekomendasi signal               |
| POST      | `/api/v1/cctv/upload`                   | Upload video CCTV                |
| GET       | `/api/v1/cctv/videos/{video_id}/stream` | Stream video CCTV                |
| WebSocket | `/api/v1/traffic/ws`                    | Realtime traffic                 |
| POST      | `/api/v1/traffic/notify`                | Push update traffic ke WebSocket |

**Catatan:** endpoint aktual mengikuti prefix/router yang terdaftar di `main.py`. Jika prefix diubah, URL final juga berubah.

---

# 27. Frontend Rule

Frontend hanya menggunakan field yang tersedia pada contract.

Jangan membuat nama field baru seperti:

```text
queue
density
speed
avgQueue
trafficDensity
```

jika field tersebut tidak ada di API.

Gunakan:

```text
queueLengthVeh
queueLengthMEst
densityIndex
avgSpeedKmh
```

Tujuannya:

```text
CV
 │
 ▼
Backend
 │
 ▼
Forecast
 │
 ▼
Frontend
```

menggunakan terminology yang sama.

---

# 28. Environment Variables

File:

```text
.env
```

digunakan untuk konfigurasi lokal dan secret.

Contoh:

```env
APP_NAME=SmartTwin Backend
APP_VERSION=0.1.0
DEBUG=true
CORS_ORIGINS=http://localhost:3000

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

HF_TOKEN=
HF_REPO_ID=rahmatisma/smarttwin-cctv
```

Jangan commit `.env`.

Gunakan:

```text
.env.example
```

sebagai template tanpa secret.

---

# 29. Installation

Masuk ke backend:

```bash
cd backend
```

Buat virtual environment:

```bash
python -m venv .venv
```

Aktifkan:

### Windows PowerShell

```powershell
.venv\Scripts\activate
```

Install dependency:

```bash
pip install -r requirements.txt
```

---

# 30. Menjalankan Backend

Gunakan:

```bash
uvicorn app.main:app --reload
```

atau:

```bash
python -m uvicorn app.main:app --reload
```

Default server:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

---

# 31. Testing

Menjalankan seluruh test:

```bash
python -m pytest -q
```

Menjalankan test tertentu:

```bash
python -m pytest tests/test_database_connection.py -q
```

Contoh:

```bash
python -m pytest tests/test_database_tables.py -q
```

---

# 32. Prinsip Arsitektur

SmartTwin menggunakan pemisahan tanggung jawab:

```text
Route
  │
  │ menerima request
  ▼
Schema
  │
  │ validasi data
  ▼
Service
  │
  │ business logic
  ▼
Repository / External Service
  │
  ├── Supabase
  ├── Hugging Face
  ├── CV
  ├── Forecast
  └── Simulation
```

Tujuannya agar setiap bagian memiliki tanggung jawab yang jelas.

### Route

```text
"Menerima dan mengembalikan HTTP request/response."
```

### Schema

```text
"Menentukan bentuk dan validasi data."
```

### Service

```text
"Menjalankan business logic."
```

### Repository

```text
"Menangani akses database."
```

### Pipeline

```text
"Mengubah data mentah menjadi traffic state."
```

### Model

```text
"Menjalankan machine learning."
```

### Simulation

```text
"Menjalankan skenario Digital Twin/SUMO."
```

---

# 33. Gambaran Besar Sistem

```text
                         CCTV
                           │
                           ▼
                    YOLO + ByteTrack
                           │
                           ▼
                Traffic State Builder
                           │
                           ▼
                     FastAPI
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
          Supabase      Forecast    Recommendation
        PostgreSQL          │            │
              │             │            │
              └─────────────┼────────────┘
                            ▼
                         SUMO
                            │
                            ▼
                     Performance
                       Analysis
                            │
                            ▼
                     Next.js Dashboard
```

FastAPI menjadi **penghubung utama antar-komponen**, tetapi bukan tempat semua proses berat dijalankan.

Computer Vision, forecasting, recommendation, database, storage, dan simulation tetap memiliki layer masing-masing.

---

# 34. Development Rule

Sebelum mengubah contract atau schema:

1. Cek schema Pydantic.
2. Cek service terkait.
3. Cek repository/database.
4. Cek endpoint.
5. Cek frontend yang menggunakan field tersebut.
6. Pastikan perubahan tidak memutus pipeline CV → Backend → Frontend.

Untuk perubahan database:

```text
Schema Database
      ↓
Repository
      ↓
Service
      ↓
API
      ↓
Frontend
```

Untuk perubahan traffic contract:

```text
CV
 ↓
Traffic State Builder
 ↓
Pydantic Schema
 ↓
API
 ↓
Frontend
```

**Jangan mengubah satu layer saja jika perubahan tersebut mengubah contract antar-layer.**

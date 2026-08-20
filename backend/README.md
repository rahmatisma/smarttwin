# SmartTwin Backend

Backend API untuk **SmartTwin Traffic Digital Twin**.

Backend menjadi penghubung antara:

```text
YOLO + ByteTrack
       ↓
Traffic State Builder
       ↓
FastAPI Backend
       ↓
Forecast / Recommendation
       ↓
Next.js Frontend
```

---

## 1. Tech Stack

| Komponen       | Teknologi             |
| -------------- | --------------------- |
| Backend        | FastAPI               |
| Language       | Python 3.10+          |
| Validation     | Pydantic v2           |
| Server         | Uvicorn               |
| Testing        | Pytest                |
| Forecast       | LSTM / model forecast |
| CV             | YOLO + ByteTrack      |
| Simulation     | SUMO                  |
| Recommendation | PPO / rule-based      |

---

## 2. Struktur Backend


```text
backend/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── health.py
│   │       ├── traffic.py
│   │       ├── signal.py
│   │       ├── forecast.py
│   │       └── recommendation.py
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
│   │   └── recommendation_service.py
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
│   ├── pipeline/
│   │   └── traffic_state_builder.py
│   │
│   └── core/
│       └── config.py
│
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```
---

## 3. Data Flow

```text
CV
│
├── vehicle count
├── queue length
├── density index
└── speed (jika tersedia)
│
▼
Traffic State Builder
│
▼
Backend Traffic API
│
├── Frontend Dashboard
├── Forecast
└── Recommendation
```

---

# 4. Database

backend/
│
├── app/
│   ├── api/
│   ├── core/
│   ├── db/                    ← BARU
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
│   ├── schemas/
│   ├── services/
│   └── main.py
│
├── migrations/
├── tests/
├── .env
├── .env.example
└── requirements.txt

# 5. Traffic Data — Source of Truth

### Catatan

`avgSpeedKmh`:

```text
nilai ada     → tampilkan speed
nilai null    → tampilkan "N/A"
```

**Jangan ubah `null` menjadi `0`.**

`densityIndex` **bukan** `vehicles/km`.

`queueLengthMEst` adalah **estimasi**, bukan pengukuran meter yang terkalibrasi penuh.

---

# 6. Endpoint

| Method | Endpoint              | Fungsi                |
| ------ | --------------------- | --------------------- |
| `GET`  | `/api/health`         | Cek backend           |
| `GET`  | `/api/traffic/latest` | Ambil traffic terbaru |
| `POST` | `/api/traffic/state`  | Kirim traffic state   |
| `GET`  | `/api/signal/status`  | Status lampu          |
| `POST` | `/api/signal/status`  | Update status lampu   |
| `POST` | `/api/forecast`       | Prediksi traffic      |
| `POST` | `/api/recommendation` | Rekomendasi signal    |

---

# 7. Frontend Rule

Frontend **hanya menggunakan field yang ada di contract**.

Jangan membuat nama field baru seperti:

```text
queue
density
speed
avgQueue
trafficDensity
```

jika field tersebut sebenarnya sudah tersedia di API.

Gunakan:

```text
queueLengthVeh
queueLengthMEst
densityIndex
avgSpeedKmh
```

Tujuannya supaya:

```text
CV = Backend = Forecast = Frontend
```

menggunakan istilah yang sama.

---

## 8. Run

```bash
cd backend

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt

uvicorn app.main:app --reload

python -m uvicorn app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

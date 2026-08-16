# SmartTwin Backend

Backend API untuk sistem **SmartTwin Traffic Digital Twin**.

Backend dibangun menggunakan **FastAPI** dan bertugas sebagai penghubung antara modul pemantauan lalu lintas, Computer Vision, traffic forecast, simulasi, adaptive signal recommendation, dan frontend dashboard.

## 1. Peran Backend

Backend tidak menjalankan seluruh sistem SmartTwin secara langsung.

Backend berfungsi sebagai API layer dan orchestration layer yang menghubungkan:

```text
Computer Vision
YOLO + ByteTrack
       │
       ▼
Traffic State Builder
       │
       ▼
SmartTwin Backend
       │
       ├── Traffic State
       ├── Signal Status
       ├── Traffic Forecast
       └── Signal Recommendation
       │
       ▼
Next.js Dashboard
```

Backend juga disiapkan agar nantinya dapat terhubung dengan:

```text
LSTM
  │
  ▼
Traffic Forecast

SUMO
  │
  ▼
Traffic Simulation

PPO
  │
  ▼
Adaptive Signal Recommendation
```

## 2. Teknologi

* Python 3.10+
* FastAPI
* Uvicorn
* Pydantic v2
* Pytest

Model AI dan simulator dipisahkan dari dependency API dasar agar backend tetap dapat dijalankan ketika model final belum tersedia.

## 3. Struktur Project

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

## 4. Installation

Masuk ke folder backend:

```bash
cd backend
```

Buat virtual environment:

```bash
python -m venv .venv
```

Aktifkan virtual environment di Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependency:

```bash
pip install -r requirements.txt
```

## 5. Environment Configuration

Salin file environment:

Windows:

```bash
copy .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Kemudian sesuaikan `.env`.

Contoh:

```env
APP_NAME=SmartTwin Backend
APP_VERSION=1.0.0
ENVIRONMENT=development

HOST=0.0.0.0
PORT=8000

FRONTEND_URL=http://localhost:3000

ENABLE_YOLO=false
ENABLE_LSTM=false
ENABLE_PPO=false
ENABLE_SUMO=false
```

File `.env` tidak boleh di-commit ke Git.

## 6. Menjalankan Backend

Jalankan:

```bash
uvicorn app.main:app --reload

atau

./.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Backend akan tersedia di:

```text
http://127.0.0.1:8000
```

Swagger API:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

## 7. Production

Untuk deployment:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`--reload` hanya digunakan untuk development.

## 8. API Endpoint

Endpoint utama:

```text
GET  /api/health

GET  /api/traffic/latest
POST /api/traffic/state

GET  /api/signal/status
POST /api/signal/status

POST /api/forecast

POST /api/recommendation
```

Detail format request dan response terdapat di:

```text
docs/data-contract.md
```

## 9. Testing

Jalankan:

```bash
pytest
```

atau:

```bash
pytest -v
```

## 10. Model Integration

Backend menggunakan pendekatan adapter.

Artinya API tidak langsung bergantung pada implementasi internal model.

Contoh:

```text
YOLO
  ↓
YOLODetector
  ↓
TrafficStateBuilder
  ↓
TrafficService
  ↓
API
```

Untuk forecast:

```text
LSTM
  ↓
LSTMPredictor
  ↓
ForecastService
  ↓
API
```

Untuk adaptive signal:

```text
PPO
  ↓
PPOAgent
  ↓
RecommendationService
  ↓
API
```

Dengan pendekatan ini, perubahan model tidak perlu mengubah contract frontend.

## 11. Status Implementasi

### Backend API

* [x] FastAPI application
* [x] CORS
* [x] Health endpoint
* [x] Traffic endpoint
* [x] Signal endpoint
* [x] Forecast endpoint
* [x] Recommendation endpoint
* [x] Pydantic schemas
* [x] Service layer
* [x] API tests

### Model

* [ ] Final YOLO weight integration
* [ ] Final LSTM weight integration
* [ ] Final PPO weight integration

### Simulation

* [ ] Final SUMO network
* [ ] SUMO route configuration
* [ ] TraCI integration
* [ ] Scenario generation
* [ ] Simulation performance analysis

## 12. Important Development Rule

Frontend harus bergantung pada **API contract**, bukan implementasi internal model.

Contoh:

Frontend hanya perlu mengetahui:

```text
POST /api/forecast
```

Frontend tidak perlu mengetahui apakah backend menggunakan:

```text
LSTM
XGBoost
GRU
```

Demikian pula frontend hanya menerima recommendation.

Frontend tidak perlu mengetahui apakah recommendation berasal dari:

```text
PPO
rule-based
simulation optimizer
```

Hal ini membuat arsitektur SmartTwin lebih mudah dikembangkan dan diuji.

## 13. Deployment

Backend dapat di-host sebagai service terpisah dari frontend.

Contoh:

```text
Frontend
https://smarttwin.example.com

Backend
https://api.smarttwin.example.com
```

Frontend kemudian menggunakan base URL backend.

Jangan menggunakan `localhost` pada konfigurasi frontend ketika sistem sudah di-deploy.

## 14. Development Principle

Backend dipertahankan sebagai layer yang stabil.

Perubahan pada:

* YOLO
* ByteTrack
* LSTM
* PPO
* SUMO
* algoritma forecasting

tidak boleh mengubah API contract tanpa alasan yang kuat.

Jika model berubah, ubah adapter/service internal terlebih dahulu.

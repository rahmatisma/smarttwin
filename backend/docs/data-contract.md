# SmartTwin Data Contract

## 1. Overview

Dokumen ini mendefinisikan kontrak data antara komponen-komponen dalam sistem **SmartTwin Traffic Digital Twin**.

Data contract digunakan sebagai acuan bersama untuk:

* Backend API
* Frontend Dashboard
* Computer Vision
* Traffic State Builder
* Traffic Forecast
* Traffic Simulation
* Adaptive Signal Recommendation

Contract ini mendefinisikan **data yang dipertukarkan**, bukan implementasi internal dari model atau algoritma.

Model dan simulator dapat berubah selama pengembangan selama output dan input yang digunakan oleh API tetap mengikuti contract ini.

---

# 2. System Data Flow

Secara umum, pertukaran data dalam SmartTwin mengikuti alur:

```text
Traffic Camera
      │
      ▼
Computer Vision
YOLO + ByteTrack
      │
      ▼
Traffic State Builder
      │
      ▼
SmartTwin Backend
      │
      ├───────────────┐
      │               │
      ▼               ▼
Traffic Forecast   Traffic Simulation
      │               │
      └───────┬───────┘
              ▼
     Adaptive Recommendation
              │
              ▼
       Frontend Dashboard
```

Pada tahap development, beberapa komponen dapat menggunakan data simulasi atau mock data karena model dan simulator final belum tersedia.

---

# 3. Contract Principles

## 3.1 API sebagai Interface

Frontend berkomunikasi dengan backend melalui API.

Frontend tidak bergantung langsung pada:

* YOLO
* ByteTrack
* LSTM
* PPO
* SUMO

Perubahan pada implementasi internal tidak boleh mengubah API tanpa alasan yang jelas.

---

## 3.2 Model Independence

Data contract tidak mengunci jenis model.

Contoh forecasting dapat menggunakan:

```text
LSTM
XGBoost
GRU
model lainnya
```

selama menghasilkan format forecast yang sesuai contract.

Demikian juga recommendation dapat berasal dari:

```text
PPO
rule-based
optimization
simulation-based decision
```

selama menghasilkan format recommendation yang sesuai contract.

---

## 3.3 Mock Data

Sebelum model final tersedia, backend diperbolehkan menggunakan:

```text
mock data
demo data
simulated data
```

Mock data harus tetap mengikuti contract yang sama dengan data production.

Dengan demikian frontend dapat dikembangkan sebelum model final selesai.

---

# 4. Base API

Development:

```text
http://127.0.0.1:8000/api
```

Production:

```text
https://<backend-domain>/api
```

Semua endpoint menggunakan JSON kecuali dinyatakan lain.

Request dengan body menggunakan:

```text
Content-Type: application/json
```

---

# 5. Data Types

Contract menggunakan tipe data berikut:

| Type     | Description          |
| -------- | -------------------- |
| string   | Text atau identifier |
| integer  | Bilangan bulat       |
| float    | Bilangan desimal     |
| boolean  | `true` atau `false`  |
| datetime | ISO 8601 timestamp   |
| object   | JSON object          |
| array    | JSON array           |

---

# 6. Timestamp

Semua timestamp menggunakan format ISO 8601.

Contoh:

```text
2026-08-16T10:30:00Z
```

Backend sebaiknya menggunakan UTC untuk penyimpanan dan komunikasi antar-komponen.

Frontend bertanggung jawab mengubah timestamp ke timezone lokal jika diperlukan untuk tampilan.

---

# 7. Intersection Identifier

Setiap kondisi lalu lintas dan signal status harus memiliki identifier persimpangan.

Format:

```text
intersection_id
```

Contoh:

```text
intersection_01
```

Identifier harus konsisten pada seluruh data yang berkaitan dengan persimpangan yang sama.

---

# 8. Traffic State

Traffic State merupakan representasi kondisi lalu lintas aktual pada suatu persimpangan.

Traffic State dapat berasal dari:

```text
Computer Vision
Simulation
Mock Data
```

## 8.1 Endpoint

### GET `/traffic/latest`

Mengambil traffic state terbaru.

### POST `/traffic/state`

Mengirim traffic state terbaru ke backend.

---

# 9. Traffic State Schema

Format:

```json
{
  "intersection_id": "intersection_01",
  "timestamp": "2026-08-16T10:30:00Z",
  "total_vehicle_count": 42,
  "car_count": 22,
  "motorcycle_count": 14,
  "truck_count": 4,
  "bus_count": 2,
  "average_speed_kmh": 28.5,
  "total_queue_length": 17,
  "lanes": {},
  "source": "computer_vision"
}
```

## 9.1 Fields

| Field                 | Type     | Required | Description                                  |
| --------------------- | -------- | -------: | -------------------------------------------- |
| `intersection_id`     | string   |      Yes | ID persimpangan                              |
| `timestamp`           | datetime |      Yes | Waktu data dibuat                            |
| `total_vehicle_count` | integer  |      Yes | Total kendaraan terdeteksi                   |
| `car_count`           | integer  |      Yes | Jumlah mobil                                 |
| `motorcycle_count`    | integer  |      Yes | Jumlah sepeda motor                          |
| `truck_count`         | integer  |      Yes | Jumlah truk                                  |
| `bus_count`           | integer  |      Yes | Jumlah bus                                   |
| `average_speed_kmh`   | float    |      Yes | Rata-rata kecepatan kendaraan                |
| `total_queue_length`  | integer  |      Yes | Total panjang antrean dalam satuan kendaraan |
| `lanes`               | object   |      Yes | Informasi lalu lintas per lane               |
| `source`              | string   |      Yes | Sumber data                                  |

Semua nilai jumlah kendaraan harus bernilai `>= 0`.

`average_speed_kmh` harus bernilai `>= 0`.

---

# 10. Lane Traffic

Jika sistem menyediakan informasi per lane, field `lanes` dapat berisi:

```json
{
  "north": {
    "lane_id": "north",
    "vehicle_count": 15,
    "car_count": 8,
    "motorcycle_count": 5,
    "truck_count": 1,
    "bus_count": 1,
    "average_speed_kmh": 25.2,
    "queue_length": 7,
    "density": 0.62
  }
}
```

## 10.1 Lane Fields

| Field               | Type    | Required | Description                     |
| ------------------- | ------- | -------: | ------------------------------- |
| `lane_id`           | string  |      Yes | Identifier lane                 |
| `vehicle_count`     | integer |      Yes | Total kendaraan pada lane       |
| `car_count`         | integer |      Yes | Mobil                           |
| `motorcycle_count`  | integer |      Yes | Sepeda motor                    |
| `truck_count`       | integer |      Yes | Truk                            |
| `bus_count`         | integer |      Yes | Bus                             |
| `average_speed_kmh` | float   |      Yes | Rata-rata kecepatan             |
| `queue_length`      | integer |      Yes | Panjang antrean dalam kendaraan |
| `density`           | float   |      Yes | Kepadatan lalu lintas           |

`density` menggunakan nilai antara:

```text
0.0 - 1.0
```

Jika sistem belum dapat menghitung density secara valid, nilainya dapat menggunakan:

```text
0.0
```

atau nilai yang sesuai dengan implementasi yang disepakati kemudian.

---

# 11. Vehicle Class

Jenis kendaraan yang digunakan oleh contract:

```text
car
motorcycle
truck
bus
```

Mapping dari Computer Vision harus distandardisasi sebelum data dikirim ke backend.

Contoh yang benar:

```json
{
  "class_name": "car"
}
```

Nama class internal dari model tidak menjadi bagian dari contract.

Misalnya model dapat menggunakan label internal yang berbeda, tetapi Traffic State Builder harus mengubahnya ke kategori contract.

---

# 12. Traffic Source

Field:

```text
source
```

digunakan untuk mengetahui sumber Traffic State.

Nilai yang dapat digunakan:

```text
computer_vision
simulation
mock
```

Contoh:

```json
{
  "source": "computer_vision"
}
```

Pada tahap development, backend dapat menggunakan:

```json
{
  "source": "mock"
}
```

---

# 13. Traffic Response

### GET `/traffic/latest`

Response:

```json
{
  "success": true,
  "data": {
    "intersection_id": "intersection_01",
    "timestamp": "2026-08-16T10:30:00Z",
    "total_vehicle_count": 42,
    "car_count": 22,
    "motorcycle_count": 14,
    "truck_count": 4,
    "bus_count": 2,
    "average_speed_kmh": 28.5,
    "total_queue_length": 17,
    "lanes": {},
    "source": "computer_vision"
  },
  "message": "Latest traffic state retrieved successfully."
}
```

---

# 14. Signal Status

Signal Status menggambarkan kondisi lampu lalu lintas pada persimpangan.

Data dapat berasal dari:

```text
SUMO
Traffic Signal Controller
Mock Data
```

## 14.1 Endpoint

### GET `/signal/status`

Mengambil status signal terbaru.

### POST `/signal/status`

Mengirim status signal terbaru ke backend.

---

# 15. Signal Status Schema

```json
{
  "intersection_id": "intersection_01",
  "timestamp": "2026-08-16T10:30:00Z",
  "current_phase": "NS_GREEN",
  "phase_name": "North-South Green",
  "remaining_seconds": 24,
  "cycle_time_seconds": 90,
  "phases": {},
  "source": "simulation"
}
```

## 15.1 Fields

| Field                | Type     | Required | Description        |
| -------------------- | -------- | -------: | ------------------ |
| `intersection_id`    | string   |      Yes | ID persimpangan    |
| `timestamp`          | datetime |      Yes | Waktu status       |
| `current_phase`      | string   |      Yes | ID fase aktif      |
| `phase_name`         | string   |      Yes | Nama fase aktif    |
| `remaining_seconds`  | integer  |      Yes | Sisa waktu fase    |
| `cycle_time_seconds` | integer  |      Yes | Total waktu siklus |
| `phases`             | object   |      Yes | Daftar fase        |
| `source`             | string   |      Yes | Sumber signal      |

---

# 16. Signal Phase

Contoh:

```json
{
  "phase_id": "NS_GREEN",
  "state": "green",
  "duration_seconds": 35,
  "remaining_seconds": 24
}
```

## Fields

| Field               | Type    | Required | Description     |
| ------------------- | ------- | -------: | --------------- |
| `phase_id`          | string  |      Yes | ID fase         |
| `state`             | string  |      Yes | Status fase     |
| `duration_seconds`  | integer |      Yes | Durasi fase     |
| `remaining_seconds` | integer |      Yes | Sisa waktu fase |

Nilai `state` yang digunakan:

```text
green
yellow
red
```

---

# 17. Forecast

Forecast merupakan prediksi kondisi lalu lintas untuk periode waktu mendatang.

Forecast dapat menggunakan model apa pun yang memenuhi contract.

Contract tidak menentukan:

* jenis model
* arsitektur model
* jumlah layer
* input shape internal
* hyperparameter
* weight format

---

# 18. Forecast Endpoint

### POST `/forecast`

Request:

```json
{
  "intersection_id": "intersection_01",
  "horizon_minutes": 15
}
```

## 18.1 Request Fields

| Field             | Type    | Required | Description                  |
| ----------------- | ------- | -------: | ---------------------------- |
| `intersection_id` | string  |      Yes | ID persimpangan              |
| `horizon_minutes` | integer |      Yes | Horizon prediksi dalam menit |

`horizon_minutes` minimal:

```text
1
```

dan maksimal:

```text
120
```

---

# 19. Forecast Response

```json
{
  "success": true,
  "intersection_id": "intersection_01",
  "horizon_minutes": 15,
  "model": "pending",
  "predictions": [
    {
      "timestamp": "2026-08-16T10:31:00Z",
      "predicted_vehicle_count": 43.2,
      "predicted_queue_length": 17.4,
      "predicted_speed_kmh": 28.1
    }
  ]
}
```

---

# 20. Forecast Point

Setiap prediction point memiliki:

| Field                     | Type     | Required | Description               |
| ------------------------- | -------- | -------: | ------------------------- |
| `timestamp`               | datetime |      Yes | Waktu prediksi            |
| `predicted_vehicle_count` | float    |      Yes | Prediksi jumlah kendaraan |
| `predicted_queue_length`  | float    |      Yes | Prediksi antrean          |
| `predicted_speed_kmh`     | float    |      Yes | Prediksi kecepatan        |

Nilai prediksi tidak boleh bernilai negatif.

---

# 21. Forecast Model

Field:

```text
model
```

menunjukkan status atau sumber model yang digunakan.

Selama model belum tersedia:

```text
pending
```

Contoh setelah model selesai:

```text
lstm
```

atau model lain sesuai implementasi final.

Frontend tidak boleh bergantung pada nama model untuk menjalankan fungsi utama dashboard.

---

# 22. Signal Recommendation

Recommendation merupakan rekomendasi pengaturan signal berdasarkan kondisi lalu lintas dan hasil proses decision engine.

Decision engine dapat menggunakan:

```text
PPO
rule-based
optimization
simulation
```

Contract tidak mengunci metode tersebut.

---

# 23. Recommendation Endpoint

### POST `/recommendation`

Request:

```json
{
  "intersection_id": "intersection_01",
  "simulation_horizon_minutes": 15
}
```

## Request Fields

| Field                        | Type    | Required | Description      |
| ---------------------------- | ------- | -------: | ---------------- |
| `intersection_id`            | string  |      Yes | ID persimpangan  |
| `simulation_horizon_minutes` | integer |      Yes | Horizon evaluasi |

Nilai horizon:

```text
1 - 120 menit
```

---

# 24. Recommendation Response

```json
{
  "success": true,
  "recommendation": {
    "intersection_id": "intersection_01",
    "timestamp": "2026-08-16T10:30:00Z",
    "recommended_phase": "NS_GREEN",
    "recommended_green_seconds": 40,
    "current_green_seconds": 35,
    "expected_delay_reduction_percent": 8.5,
    "confidence": 0.75,
    "reason": "Antrean berada pada tingkat sedang. Green time disesuaikan secara moderat.",
    "metrics": {
      "queue_length": 17,
      "vehicle_count": 42,
      "average_speed_kmh": 28.5
    },
    "source": "pending"
  }
}
```

---

# 25. Recommendation Fields

| Field                              | Type     | Required | Description                        |
| ---------------------------------- | -------- | -------: | ---------------------------------- |
| `intersection_id`                  | string   |      Yes | ID persimpangan                    |
| `timestamp`                        | datetime |      Yes | Waktu recommendation               |
| `recommended_phase`                | string   |      Yes | Fase yang direkomendasikan         |
| `recommended_green_seconds`        | integer  |      Yes | Durasi green yang direkomendasikan |
| `current_green_seconds`            | integer  |      Yes | Durasi green saat ini              |
| `expected_delay_reduction_percent` | float    |      Yes | Estimasi pengurangan delay         |
| `confidence`                       | float    |      Yes | Tingkat keyakinan recommendation   |
| `reason`                           | string   |      Yes | Penjelasan recommendation          |
| `metrics`                          | object   |      Yes | Metrics yang digunakan             |
| `source`                           | string   |      Yes | Sumber recommendation              |

---

# 26. Confidence

Nilai:

```text
0.0 - 1.0
```

Contoh:

```text
0.75
```

berarti tingkat confidence sebesar 75%.

Confidence harus merepresentasikan confidence dari decision engine yang digunakan.

Jika model belum menyediakan confidence yang valid, backend dapat menggunakan nilai sementara selama tahap development.

---

# 27. Recommendation Source

Nilai `source` dapat menunjukkan sumber recommendation.

Selama PPO belum tersedia:

```text
pending
```

Setelah decision engine final tersedia:

```text
ppo
```

atau nilai lain sesuai implementasi.

Frontend tidak boleh bergantung pada source untuk menentukan struktur data.

---

# 28. Metrics

Field `metrics` berisi metrik yang digunakan untuk menghasilkan recommendation.

Contoh:

```json
{
  "queue_length": 17,
  "vehicle_count": 42,
  "average_speed_kmh": 28.5
}
```

Metrics dapat bertambah pada versi contract berikutnya jika diperlukan.

Frontend sebaiknya hanya menggunakan metrics yang memang diperlukan untuk visualisasi.

---

# 29. Simulation Data

SUMO belum menjadi bagian wajib dari contract pada tahap awal.

Ketika SUMO sudah terintegrasi, simulator dapat menghasilkan data seperti:

```text
delay
waiting time
queue length
throughput
speed
emission
```

Data tersebut dapat digunakan oleh:

```text
Performance Analyzer
Recommendation Engine
Dashboard
```

Namun detail komunikasi internal dengan SUMO, termasuk:

```text
TraCI
.net.xml
.rou.xml
.sumocfg
```

bukan bagian dari public API contract.

---

# 30. Performance Metrics

Format metrics yang disiapkan untuk hasil simulasi:

```json
{
  "delay_seconds": 120.5,
  "queue_length": 18,
  "waiting_time_seconds": 95.2,
  "throughput": 42,
  "emission": 1250.5
}
```

## Fields

| Field                  | Type  | Description                                   |
| ---------------------- | ----- | --------------------------------------------- |
| `delay_seconds`        | float | Total atau rata-rata delay                    |
| `queue_length`         | float | Panjang antrean                               |
| `waiting_time_seconds` | float | Waktu tunggu                                  |
| `throughput`           | float | Kendaraan yang berhasil melewati persimpangan |
| `emission`             | float | Nilai emisi sesuai output simulator           |

Satuan emission akan ditentukan berdasarkan konfigurasi simulator final.

---

# 31. Error Contract

Backend menggunakan HTTP status code untuk menunjukkan status request.

Status umum:

| Status | Meaning                  |
| -----: | ------------------------ |
|  `200` | Request berhasil         |
|  `400` | Request tidak valid      |
|  `404` | Resource tidak ditemukan |
|  `422` | Validation error         |
|  `500` | Internal server error    |

Contoh validation error:

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": [
        "body",
        "horizon_minutes"
      ],
      "msg": "Input should be greater than or equal to 1"
    }
  ]
}
```

Frontend harus menangani error response dan tidak menganggap semua request selalu berhasil.

---

# 32. Missing Data

Jika data belum tersedia, backend tidak boleh mengarang data production.

Pada tahap development, gunakan:

```text
mock
pending
null
```

sesuai konteks field.

Contoh:

```json
{
  "model": "pending"
}
```

digunakan ketika model forecast belum tersedia.

Mock data harus diberi penanda:

```json
{
  "source": "mock"
}
```

agar dapat dibedakan dari data Computer Vision atau Simulation.

---

# 33. Contract and Model Integration

Model internal harus mengikuti boundary berikut:

```text
YOLO
  ↓
YOLO Adapter
  ↓
Traffic State Builder
  ↓
Traffic State Contract
  ↓
Backend API
```

Forecast:

```text
Forecast Model
  ↓
Forecast Adapter
  ↓
Forecast Service
  ↓
Forecast Contract
  ↓
Backend API
```

Recommendation:

```text
Decision Engine
  ↓
Recommendation Adapter
  ↓
Recommendation Service
  ↓
Recommendation Contract
  ↓
Backend API
```

Simulation:

```text
SUMO
  ↓
Simulation Adapter
  ↓
Performance Analyzer
  ↓
Simulation Metrics
```

---

# 34. Frontend Boundary

Frontend hanya berkomunikasi dengan public API.

Frontend tidak mengakses:

```text
YOLO weight
LSTM weight
PPO weight
SUMO files
TraCI
model configuration
```

Frontend hanya menggunakan API contract.

---

# 35. Development State

Pada saat contract ini dibuat, status komponen adalah:

| Component          | Status         |
| ------------------ | -------------- |
| Backend API        | In Development |
| Frontend Dashboard | In Development |
| YOLO               | Not Final      |
| ByteTrack          | Not Final      |
| LSTM               | Not Final      |
| PPO                | Not Final      |
| SUMO               | Not Final      |

Karena itu beberapa response dapat menggunakan:

```text
mock
pending
```

selama proses development.

Contract tidak dianggap gagal hanya karena model belum tersedia.

---

# 36. Contract Stability

Perubahan berikut tidak seharusnya mengubah public API:

```text
YOLO weight update
YOLO architecture update
ByteTrack implementation update
LSTM model update
Forecast algorithm update
PPO model update
PPO hyperparameter update
SUMO configuration update
SUMO network update
```

Perubahan public API hanya dilakukan jika struktur kebutuhan data memang berubah.

---

# 37. Future API Versioning

Jika terjadi perubahan contract yang breaking, gunakan versioning.

Contoh:

```text
/api/v1/traffic/latest
/api/v1/signal/status
/api/v1/forecast
/api/v1/recommendation
```

Perubahan non-breaking dapat dilakukan tanpa membuat versi baru.

Contoh non-breaking:

```text
Menambahkan field optional baru.
```

Perubahan breaking:

```text
Menghapus field existing.
Mengubah tipe data field.
Mengubah arti field.
Mengubah struktur response.
```

---

# 38. Summary

Public API SmartTwin pada tahap awal terdiri dari:

```text
GET  /api/health

GET  /api/traffic/latest
POST /api/traffic/state

GET  /api/signal/status
POST /api/signal/status

POST /api/forecast

POST /api/recommendation
```

Contract utama:

```text
Traffic State
Signal Status
Forecast
Recommendation
Performance Metrics
```

Implementasi internal:

```text
YOLO
ByteTrack
LSTM
PPO
SUMO
```

dapat berubah tanpa mengubah contract selama data yang keluar dan masuk tetap mengikuti struktur yang telah ditentukan.

---

# 39. Core Principle

SmartTwin menggunakan prinsip:

```text
Stable Contract
      +
Replaceable Models
      +
Independent Frontend
      +
Independent Backend Services
```

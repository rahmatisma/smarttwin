YESS, aku masih ingat dashboard-nya dari screenshot tadi. Dari tampilan itu, database-nya **nggak cukup cuma menyimpan `trafficState`**. Kita perlu menampung data simpang, lane, CCTV/video, hasil CV, traffic state, signal, forecast, recommendation, simulation, dan history.

Dan karena kamu minta **PostgreSQL + semua nama camelCase + align dengan data contract**, aku sarankan struktur berikut sebagai **baseline database final SmartTwin**.

Aku buat dalam format **README.md** supaya bisa langsung kamu taruh di repo.

---

# SmartTwin Database Schema

Database PostgreSQL untuk SmartTwin — Digital Twin untuk simulasi adaptif pengaturan lampu lalu lintas.

Database bertanggung jawab menyimpan:

* konfigurasi persimpangan
* approach dan lane
* CCTV
* video dataset
* proses Computer Vision
* traffic state
* traffic metrics
* signal status
* signal phase
* recommendation
* forecast
* SUMO simulation
* simulation metrics
* history dashboard
* user dan pengaturan sistem

Video CCTV **tidak disimpan langsung di PostgreSQL**. File video disimpan pada Hugging Face Hub, sedangkan PostgreSQL hanya menyimpan metadata dan URL/repository reference.

---

# 1. Entity Overview

Entity utama:

```text
User
 │
 └── UserSetting

Intersection
 ├── Approach
 │    └── Lane
 │
 ├── Camera
 │    └── CameraVideo
 │         └── CvProcessingJob
 │
 ├── TrafficState
 │    └── TrafficApproachState
 │
 ├── SignalPhase
 │    └── SignalStatus
 │
 ├── Forecast
 │    └── ForecastPrediction
 │
 ├── Recommendation
 │
 └── Simulation
      └── SimulationMetric
```

Secara keseluruhan:

```text
                    ┌──────────────┐
                    │     User     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ UserSetting  │
                    └──────────────┘


┌──────────────────────────────────────────────────────────────┐
│                         INTERSECTION                         │
└───────────────┬──────────────────────┬───────────────────────┘
                │                      │
                ▼                      ▼
        ┌──────────────┐       ┌──────────────┐
        │   Approach   │       │    Camera    │
        └──────┬───────┘       └──────┬───────┘
               │                      │
               ▼                      ▼
        ┌──────────────┐       ┌──────────────┐
        │     Lane     │       │ CameraVideo  │
        └──────────────┘       └──────┬───────┘
                                      │
                                      ▼
                              ┌─────────────────┐
                              │CvProcessingJob  │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  TrafficState   │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────────┐
                              │TrafficApproachState │
                              └─────────────────────┘


┌──────────────────────┐
│    SignalPhase       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    SignalStatus      │
└──────────────────────┘


┌──────────────────────┐
│      Forecast        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ ForecastPrediction   │
└──────────────────────┘


┌──────────────────────┐
│   Recommendation     │
└──────────────────────┘


┌──────────────────────┐
│     Simulation       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  SimulationMetric    │
└──────────────────────┘
```
DATABASE FOUNDATION

[ ] 1. DATABASE_URL Supabase dibuat di .env

[ ] 2. .env masuk .gitignore

[ ] 3. SQLAlchemy database.py selesai

[ ] 4. Test koneksi Supabase
        python -m pytest tests/test_database_connection.py -q

[ ] 5. Test semua tabel Supabase
        python -m pytest tests/test_database_tables.py -q

[ ] 6. Model Intersection selesai

[ ] 7. Model Approach selesai

[ ] 8. Model Lane selesai

[ ] 9. Model TrafficState selesai

[ ] 10. Model ApproachState selesai

[ ] 11. Seed simpang4-pingit

[ ] 12. Seed north/south/east/west

[ ] 13. Cek data di Supabase

[ ] 14. TrafficStateRepository selesai

[ ] 15. Test save TrafficState

[ ] 16. TrafficStateBuilder → PostgreSQL

[ ] 17. Test CSV → Builder → Supabase
---

# 2. Database Tables

## 2.1 `users`

Menyimpan akun pengguna dashboard.

| Column         | Type           | Constraint       | Description      |
| -------------- | -------------- | ---------------- | ---------------- |
| `id`           | `bigserial`    | PK               | ID user          |
| `name`         | `varchar(100)` | NOT NULL         | Nama user        |
| `email`        | `varchar(150)` | UNIQUE, NOT NULL | Email            |
| `passwordHash` | `text`         | NOT NULL         | Password hash    |
| `role`         | `varchar(30)`  | NOT NULL         | Role user        |
| `isActive`     | `boolean`      | NOT NULL         | Status user      |
| `createdAt`    | `timestamptz`  | NOT NULL         | Waktu dibuat     |
| `updatedAt`    | `timestamptz`  | NOT NULL         | Waktu diperbarui |

Role awal:

```text
admin
operator
viewer
```

---

# 2.2 `userSettings`

Menyimpan pengaturan dashboard masing-masing user.

| Column                  | Type          | Constraint            | Description      |
| ----------------------- | ------------- | --------------------- | ---------------- |
| `id`                    | `bigserial`   | PK                    | ID setting       |
| `userId`                | `bigint`      | FK → users.id         | Pemilik setting  |
| `defaultIntersectionId` | `bigint`      | FK → intersections.id | Simpang default  |
| `theme`                 | `varchar(20)` | NOT NULL              | Tema dashboard   |
| `createdAt`             | `timestamptz` | NOT NULL              | Waktu dibuat     |
| `updatedAt`             | `timestamptz` | NOT NULL              | Waktu diperbarui |

Relasi:

```text
users 1 ─────── 1 userSettings
```

---

# 2.3 `intersections`

Ini adalah entity utama SmartTwin.

Contoh:

```text
simpang4-pingit
```

| Column           | Type            | Constraint       | Description       |
| ---------------- | --------------- | ---------------- | ----------------- |
| `id`             | `bigserial`     | PK               | ID internal       |
| `intersectionId` | `varchar(100)`  | UNIQUE, NOT NULL | ID publik simpang |
| `name`           | `varchar(150)`  | NOT NULL         | Nama simpang      |
| `description`    | `text`          | NULL             | Deskripsi         |
| `latitude`       | `decimal(10,7)` | NULL             | Latitude          |
| `longitude`      | `decimal(10,7)` | NULL             | Longitude         |
| `status`         | `varchar(30)`   | NOT NULL         | Status simpang    |
| `createdAt`      | `timestamptz`   | NOT NULL         | Waktu dibuat      |
| `updatedAt`      | `timestamptz`   | NOT NULL         | Waktu diperbarui  |

Contoh:

```text
intersectionId = simpang4-pingit
name = Simpang 4 Pingit
```

---

# 2.4 `approaches`

Menyimpan empat lengan persimpangan.

| Column           | Type           | Constraint            | Description           |
| ---------------- | -------------- | --------------------- | --------------------- |
| `id`             | `bigserial`    | PK                    | ID approach           |
| `intersectionId` | `bigint`       | FK → intersections.id | Simpang               |
| `approach`       | `varchar(10)`  | NOT NULL              | north/south/east/west |
| `name`           | `varchar(100)` | NULL                  | Nama approach         |
| `createdAt`      | `timestamptz`  | NOT NULL              | Waktu dibuat          |

Nilai `approach`:

```text
north
south
east
west
```

Relasi:

```text
intersections 1 ─────── N approaches
```

---

# 2.5 `lanes`

Menyimpan lane pada masing-masing approach.

| Column       | Type          | Constraint         | Description     |
| ------------ | ------------- | ------------------ | --------------- |
| `id`         | `bigserial`   | PK                 | ID lane         |
| `approachId` | `bigint`      | FK → approaches.id | Approach        |
| `laneId`     | `varchar(50)` | NOT NULL           | ID lane         |
| `laneNumber` | `integer`     | NULL               | Nomor lane      |
| `direction`  | `varchar(30)` | NULL               | Arah pergerakan |
| `createdAt`  | `timestamptz` | NOT NULL           | Waktu dibuat    |

Contoh:

```text
north
 ├── lane_1
 ├── lane_2
 └── lane_3
```

**Catatan:** walaupun data CSV sekarang menggunakan `lane_1`, `lane_2`, dst., database tetap memakai `laneId` sebagai nama field camelCase.

---

# 2.6 `cameras`

Menyimpan informasi CCTV.

| Column           | Type           | Constraint            | Description      |
| ---------------- | -------------- | --------------------- | ---------------- |
| `id`             | `bigserial`    | PK                    | ID kamera        |
| `intersectionId` | `bigint`       | FK → intersections.id | Simpang          |
| `cameraId`       | `varchar(100)` | UNIQUE, NOT NULL      | ID kamera        |
| `name`           | `varchar(150)` | NOT NULL              | Nama kamera      |
| `approachId`     | `bigint`       | FK → approaches.id    | Approach kamera  |
| `sourceType`     | `varchar(30)`  | NOT NULL              | Sumber kamera    |
| `sourceUrl`      | `text`         | NULL                  | URL stream       |
| `status`         | `varchar(30)`  | NOT NULL              | Status kamera    |
| `createdAt`      | `timestamptz`  | NOT NULL              | Waktu dibuat     |
| `updatedAt`      | `timestamptz`  | NOT NULL              | Waktu diperbarui |

`sourceType`:

```text
live
uploaded
dataset
```

---

# 2.7 `cameraVideos`

Ini **penting untuk halaman CCTV**.

Video disimpan di Hugging Face, bukan PostgreSQL.

| Column            | Type           | Constraint      | Description      |
| ----------------- | -------------- | --------------- | ---------------- |
| `id`              | `bigserial`    | PK              | ID video         |
| `cameraId`        | `bigint`       | FK → cameras.id | Kamera           |
| `videoName`       | `varchar(255)` | NOT NULL        | Nama video       |
| `storageProvider` | `varchar(30)`  | NOT NULL        | Penyimpanan      |
| `repositoryId`    | `varchar(255)` | NULL            | ID repository HF |
| `filePath`        | `text`         | NULL            | Path file di HF  |
| `fileUrl`         | `text`         | NULL            | URL video        |
| `durationSeconds` | `integer`      | NULL            | Durasi           |
| `fileSizeBytes`   | `bigint`       | NULL            | Ukuran file      |
| `recordedAt`      | `timestamptz`  | NULL            | Waktu rekaman    |
| `uploadedAt`      | `timestamptz`  | NOT NULL        | Waktu upload     |
| `status`          | `varchar(30)`  | NOT NULL        | Status video     |

Contoh:

```text
storageProvider = huggingface
repositoryId = username/smarttwin-cctv
filePath = videos/simpang4-pingit/video01.mp4
```

---

# 2.8 `cvProcessingJobs`

Mencatat proses YOLO + ByteTrack terhadap video.

| Column         | Type           | Constraint           | Description      |
| -------------- | -------------- | -------------------- | ---------------- |
| `id`           | `bigserial`    | PK                   | ID job           |
| `videoId`      | `bigint`       | FK → cameraVideos.id | Video input      |
| `modelName`    | `varchar(100)` | NULL                 | Model CV         |
| `modelVersion` | `varchar(50)`  | NULL                 | Versi model      |
| `startedAt`    | `timestamptz`  | NULL                 | Waktu mulai      |
| `completedAt`  | `timestamptz`  | NULL                 | Waktu selesai    |
| `status`       | `varchar(30)`  | NOT NULL             | Status proses    |
| `outputPath`   | `text`         | NULL                 | Lokasi output    |
| `errorMessage` | `text`         | NULL                 | Error jika gagal |
| `createdAt`    | `timestamptz`  | NOT NULL             | Waktu dibuat     |

Status:

```text
queued
processing
completed
failed
```

---

# 2.9 `trafficStates`

Ini merupakan **parent entity dari TrafficState contract**.

| Column            | Type          | Constraint               | Description  |
| ----------------- | ------------- | ------------------------ | ------------ |
| `id`              | `bigserial`   | PK                       | ID internal  |
| `intersectionId`  | `bigint`      | FK → intersections.id    | Simpang      |
| `windowStart`     | `timestamptz` | NOT NULL                 | Awal window  |
| `windowEnd`       | `timestamptz` | NOT NULL                 | Akhir window |
| `source`          | `varchar(30)` | NOT NULL                 | Sumber data  |
| `processingJobId` | `bigint`      | FK → cvProcessingJobs.id | CV job       |
| `createdAt`       | `timestamptz` | NOT NULL                 | Waktu dibuat |

Contoh:

```text
windowStart = 2026-08-15T16:30:10
windowEnd   = 2026-08-15T16:30:15
```

---

# 2.10 `trafficApproachStates`

Ini bagian **paling penting** untuk menyimpan `ApproachState`.

| Column            | Type               | Constraint            | Description              |
| ----------------- | ------------------ | --------------------- | ------------------------ |
| `id`              | `bigserial`        | PK                    | ID                       |
| `trafficStateId`  | `bigint`           | FK → trafficStates.id | Traffic state            |
| `approachId`      | `bigint`           | FK → approaches.id    | Approach                 |
| `approach`        | `varchar(10)`      | NOT NULL              | north/south/east/west    |
| `volume`          | `integer`          | NOT NULL              | Total kendaraan          |
| `carCount`        | `integer`          | NOT NULL              | Jumlah mobil             |
| `motorcycleCount` | `integer`          | NOT NULL              | Jumlah motor             |
| `busCount`        | `integer`          | NOT NULL              | Jumlah bus               |
| `truckCount`      | `integer`          | NOT NULL              | Jumlah truk              |
| `queueLengthVeh`  | `integer`          | NOT NULL              | Jumlah kendaraan antre   |
| `queueLengthMEst` | `double precision` | NOT NULL              | Estimasi panjang antrean |
| `densityIndex`    | `double precision` | NOT NULL              | Proxy kepadatan          |
| `avgSpeedKmh`     | `double precision` | NULL                  | Kecepatan rata-rata      |

### Sangat penting

Field ini **harus persis**:

```text
volume
carCount
motorcycleCount
busCount
truckCount
queueLengthVeh
queueLengthMEst
densityIndex
avgSpeedKmh
```

Jangan kembali menggunakan:

```text
queueLengthM
densityVehPerKm
```

Dan:

```text
avgSpeedKmh = NULL
```

kalau speed memang belum tersedia.

---

# 2.11 `trafficLaneMetrics`

Nah ini **opsional tetapi aku sangat merekomendasikan untuk SmartTwin** karena data CV awal kamu masih berbentuk:

```text
timestamp + approach + lane
```

Jadi kita bisa menyimpan hasil per-lane sebelum diaggregate menjadi `TrafficApproachState`.

| Column            | Type               | Constraint            | Description        |
| ----------------- | ------------------ | --------------------- | ------------------ |
| `id`              | `bigserial`        | PK                    | ID                 |
| `trafficStateId`  | `bigint`           | FK → trafficStates.id | Traffic state      |
| `laneId`          | `bigint`           | FK → lanes.id         | Lane               |
| `timestamp`       | `timestamptz`      | NOT NULL              | Timestamp CV       |
| `vehicleCount`    | `integer`          | NOT NULL              | Kendaraan crossing |
| `carCount`        | `integer`          | NOT NULL              | Mobil              |
| `motorcycleCount` | `integer`          | NOT NULL              | Motor              |
| `busCount`        | `integer`          | NOT NULL              | Bus                |
| `truckCount`      | `integer`          | NOT NULL              | Truk               |
| `queueLengthVeh`  | `integer`          | NOT NULL              | Antrean lane       |
| `queueLengthMEst` | `double precision` | NOT NULL              | Panjang antrean    |
| `densityIndex`    | `double precision` | NOT NULL              | Density proxy      |

Alurnya:

```text
CV CSV
   ↓
trafficLaneMetrics
   ↓
Traffic State Builder
   ↓
trafficApproachStates
```

Ini akan sangat membantu kalau nanti kalian mau audit kenapa suatu `TrafficState` menghasilkan angka tertentu.

---

# 2.12 `signalPhases`

Menyimpan konfigurasi fase lampu.

| Column             | Type           | Constraint            | Description    |
| ------------------ | -------------- | --------------------- | -------------- |
| `id`               | `bigserial`    | PK                    | ID fase        |
| `intersectionId`   | `bigint`       | FK → intersections.id | Simpang        |
| `phaseId`          | `varchar(50)`  | NOT NULL              | ID fase        |
| `phaseName`        | `varchar(100)` | NOT NULL              | Nama fase      |
| `sequenceOrder`    | `integer`      | NOT NULL              | Urutan         |
| `greenSeconds`     | `integer`      | NOT NULL              | Green          |
| `yellowSeconds`    | `integer`      | NOT NULL              | Yellow         |
| `redSeconds`       | `integer`      | NOT NULL              | Red            |
| `activeApproaches` | `jsonb`        | NOT NULL              | Approach aktif |
| `isActive`         | `boolean`      | NOT NULL              | Status         |

Contoh:

```json
["north", "south"]
```

---

# 2.13 `signalStatuses`

Menyimpan kondisi lampu pada waktu tertentu.

| Column             | Type           | Constraint            | Description  |
| ------------------ | -------------- | --------------------- | ------------ |
| `id`               | `bigserial`    | PK                    | ID           |
| `intersectionId`   | `bigint`       | FK → intersections.id | Simpang      |
| `timestamp`        | `timestamptz`  | NOT NULL              | Waktu        |
| `currentPhase`     | `varchar(50)`  | NOT NULL              | Fase aktif   |
| `phaseName`        | `varchar(100)` | NOT NULL              | Nama fase    |
| `remainingSeconds` | `integer`      | NOT NULL              | Sisa waktu   |
| `cycleTimeSeconds` | `integer`      | NOT NULL              | Waktu siklus |
| `source`           | `varchar(30)`  | NOT NULL              | Sumber       |

Field API tetap:

```text
currentPhase
phaseName
remainingSeconds
cycleTimeSeconds
source
```

---

# 2.14 `forecasts`

Menyimpan metadata satu proses forecasting.

| Column           | Type           | Constraint            | Description      |
| ---------------- | -------------- | --------------------- | ---------------- |
| `id`             | `bigserial`    | PK                    | ID               |
| `intersectionId` | `bigint`       | FK → intersections.id | Simpang          |
| `horizonMinutes` | `integer`      | NOT NULL              | Horizon prediksi |
| `model`          | `varchar(100)` | NOT NULL              | Model            |
| `createdAt`      | `timestamptz`  | NOT NULL              | Waktu prediksi   |

Contoh:

```text
horizonMinutes = 15
model = LSTM
```

---

# 2.15 `forecastPredictions`

Menyimpan setiap titik prediksi.

| Column                     | Type             | Constraint        | Description              |
| -------------------------- | ---------------- | ----------------- | ------------------------ |
| `id`                       | `bigserial`      | PK                | ID                       |
| `forecastId`               | `bigint`         | FK → forecasts.id | Forecast                 |
| `timestamp`                | `timestamptz`    | NOT NULL          | Waktu prediksi           |
| `predictedVehicleCount`    | double precision | NOT NULL          | Prediksi kendaraan       |
| `predictedQueueLengthVeh`  | double precision | NOT NULL          | Prediksi antrean         |
| `predictedQueueLengthMEst` | double precision | NOT NULL          | Prediksi panjang antrean |
| `predictedDensityIndex`    | double precision | NOT NULL          | Prediksi density         |
| `predictedSpeedKmh`        | double precision | NULL              | Prediksi speed           |

---

# 2.16 `recommendations`

Untuk halaman **Signal Recommendation**.

| Column                          | Type               | Constraint            | Description                |
| ------------------------------- | ------------------ | --------------------- | -------------------------- |
| `id`                            | `bigserial`        | PK                    | ID                         |
| `intersectionId`                | `bigint`           | FK → intersections.id | Simpang                    |
| `timestamp`                     | `timestamptz`      | NOT NULL              | Waktu                      |
| `recommendedPhase`              | `varchar(50)`      | NOT NULL              | Fase rekomendasi           |
| `recommendedGreenSeconds`       | `integer`          | NOT NULL              | Green rekomendasi          |
| `currentGreenSeconds`           | `integer`          | NOT NULL              | Green saat ini             |
| `expectedDelayReductionPercent` | `double precision` | NOT NULL              | Estimasi pengurangan delay |
| `confidence`                    | `double precision` | NOT NULL              | Confidence                 |
| `reason`                        | `text`             | NOT NULL              | Alasan                     |
| `source`                        | `varchar(30)`      | NOT NULL              | Sumber                     |
| `createdAt`                     | `timestamptz`      | NOT NULL              | Waktu dibuat               |

Contoh `source`:

```text
ppo
ruleBased
mock
```

Kalau recommendation belum tersedia:

```text
database tidak perlu membuat recommendation palsu.
```

---

# 2.17 `simulations`

Menyimpan setiap eksperimen Digital Twin / SUMO.

| Column             | Type           | Constraint              | Description       |
| ------------------ | -------------- | ----------------------- | ----------------- |
| `id`               | `bigserial`    | PK                      | ID simulation     |
| `intersectionId`   | `bigint`       | FK → intersections.id   | Simpang           |
| `trafficStateId`   | `bigint`       | FK → trafficStates.id   | State input       |
| `recommendationId` | `bigint`       | FK → recommendations.id | Recommendation    |
| `simulationName`   | `varchar(150)` | NOT NULL                | Nama simulasi     |
| `simulationType`   | `varchar(50)`  | NOT NULL                | Jenis simulasi    |
| `engine`           | `varchar(50)`  | NOT NULL                | Simulation engine |
| `status`           | `varchar(30)`  | NOT NULL                | Status            |
| `startedAt`        | `timestamptz`  | NULL                    | Mulai             |
| `completedAt`      | `timestamptz`  | NULL                    | Selesai           |
| `createdAt`        | `timestamptz`  | NOT NULL                | Dibuat            |

Contoh:

```text
simulationType = baseline
simulationType = recommended
engine = SUMO
```

---

# 2.18 `simulationMetrics`

Menyimpan hasil evaluasi SUMO.

Ini yang nantinya dipakai untuk membandingkan:

```text
Before
vs
After recommendation
```

| Column         | Type               | Constraint          | Description |
| -------------- | ------------------ | ------------------- | ----------- |
| `id`           | `bigserial`        | PK                  | ID          |
| `simulationId` | `bigint`           | FK → simulations.id | Simulasi    |
| `metricName`   | `varchar(50)`      | NOT NULL            | Nama metric |
| `metricValue`  | `double precision` | NOT NULL            | Nilai       |
| `unit`         | `varchar(30)`      | NULL                | Satuan      |
| `createdAt`    | `timestamptz`      | NOT NULL            | Waktu       |

Metric:

```text
delay
queue
throughput
waitingTime
emission
```

Atau kalau ingin lebih eksplisit:

```text
averageDelaySeconds
averageQueueLength
throughputVehicles
averageWaitingTimeSeconds
emissionGrams
```

---

# 2.19 `cctvHistory`

Untuk halaman **History CCTV**.

Kalau user membuka history, database bisa mengetahui video apa saja yang pernah diproses.

| Column            | Type          | Constraint               | Description |
| ----------------- | ------------- | ------------------------ | ----------- |
| `id`              | `bigserial`   | PK                       | ID          |
| `cameraId`        | `bigint`      | FK → cameras.id          | Kamera      |
| `videoId`         | `bigint`      | FK → cameraVideos.id     | Video       |
| `processingJobId` | `bigint`      | FK → cvProcessingJobs.id | CV job      |
| `status`          | `varchar(30)` | NOT NULL                 | Status      |
| `startedAt`       | `timestamptz` | NULL                     | Mulai       |
| `completedAt`     | `timestamptz` | NULL                     | Selesai     |
| `createdAt`       | `timestamptz` | NOT NULL                 | Dibuat      |


---

# 3. Relationship

## Core Infrastructure

```text
Intersection
    │
    ├── Approach
    │      │
    │      └── Lane
    │
    └── Camera
           │
           └── CameraVideo
                  │
                  └── CvProcessingJob
```

Cardinality:

```text
Intersection 1 ─── N Approach

Approach 1 ─── N Lane

Intersection 1 ─── N Camera

Camera 1 ─── N CameraVideo

CameraVideo 1 ─── N CvProcessingJob
```

---

# 4. Traffic Data Relationship

```text
CvProcessingJob
       │
       ▼
TrafficState
       │
       ├── TrafficApproachState
       │
       └── TrafficLaneMetrics
```

Cardinality:

```text
TrafficState 1 ─── N TrafficApproachState

TrafficState 1 ─── N TrafficLaneMetrics

Lane 1 ─── N TrafficLaneMetrics
```

Dengan begitu:

```text
CV
 ↓
Lane Metrics
 ↓
Traffic State Builder
 ↓
Approach State
 ↓
Backend
 ↓
Frontend
```

---

# 5. Signal Relationship

```text
Intersection
      │
      ├── SignalPhase
      │
      └── SignalStatus
```

Kemudian:

```text
TrafficState
      │
      ▼
Recommendation
      │
      ▼
Simulation
      │
      ▼
SimulationMetric
```

---

# 6. Forecast Relationship

```text
Intersection
      │
      ▼
Forecast
      │
      ▼
ForecastPrediction
```

---

# 7. Full Entity Relationship

```text
User
 │
 └── UserSetting
        │
        └── Intersection


Intersection
 │
 ├── Approach
 │     │
 │     └── Lane
 │
 ├── Camera
 │     │
 │     └── CameraVideo
 │             │
 │             └── CvProcessingJob
 │
 ├── TrafficState
 │     ├── TrafficApproachState
 │     └── TrafficLaneMetrics
 │
 ├── SignalPhase
 │
 ├── SignalStatus
 │
 ├── Forecast
 │     └── ForecastPrediction
 │
 ├── Recommendation
 │
 └── Simulation
        │
        └── SimulationMetric
```

---

# 8. Dashboard → Database Mapping

Ini penting supaya jelas **kenapa tabel-tabel tersebut ada**.

| Dashboard             | Data Source                                                  |
| --------------------- | ------------------------------------------------------------ |
| Nama simpang          | `intersections`                                              |
| Total kendaraan       | `trafficApproachStates.volume`                               |
| Kecepatan rata-rata   | `trafficApproachStates.avgSpeedKmh`                          |
| Antrean terpanjang    | `trafficApproachStates.queueLengthMEst`                      |
| Indeks kepadatan      | `trafficApproachStates.densityIndex`                         |
| Tanggal               | `trafficStates.windowEnd`                                    |
| Motorcycle            | `trafficApproachStates.motorcycleCount`                      |
| Car                   | `trafficApproachStates.carCount`                             |
| Bus                   | `trafficApproachStates.busCount`                             |
| Truck                 | `trafficApproachStates.truckCount`                           |
| Digital Twin          | `intersections` + `trafficApproachStates` + `signalStatuses` |
| Camera Feed           | `cameras` + `cameraVideos`                                   |
| Signal Status         | `signalStatuses`                                             |
| Signal Recommendation | `recommendations`                                            |
| Traffic Forecast      | `forecasts` + `forecastPredictions`                          |
| CCTV History          | `cctvHistory`                                                |
| Simulation History    | `simulations` + `simulationMetrics`                          |

---

# 9. Data Contract Mapping

Database **tidak harus bernama sama persis dengan entity API**, tetapi data yang keluar dari backend harus mengikuti contract.

Contoh:

```text
DATABASE

trafficApproachStates
    │
    ├── volume
    ├── carCount
    ├── motorcycleCount
    ├── busCount
    ├── truckCount
    ├── queueLengthVeh
    ├── queueLengthMEst
    ├── densityIndex
    └── avgSpeedKmh
             │
             ▼
        Backend Schema
             │
             ▼
        TrafficState
             │
             ▼
         Frontend
```

Jadi tidak ada lagi:

```text
queueLengthM
densityVehPerKm
```

---

# 10. Contoh TrafficState di Database

Misalnya backend menghasilkan:

```json
{
  "intersectionId": "simpang4-pingit",
  "windowStart": "2026-08-15T16:30:10",
  "windowEnd": "2026-08-15T16:30:15",
  "approaches": [
    {
      "approach": "north",
      "volume": 4,
      "carCount": 0,
      "motorcycleCount": 4,
      "busCount": 0,
      "truckCount": 0,
      "queueLengthVeh": 0,
      "queueLengthMEst": 0,
      "densityIndex": 13.68,
      "avgSpeedKmh": null
    }
  ]
}
```

Database menyimpannya sebagai:

```text
intersections
        │
        ▼
trafficStates
        │
        ▼
trafficApproachStates
```

---

# 11. Video Storage Architecture

Video **jangan dimasukkan ke PostgreSQL**.

Gunakan:

```text
                ┌──────────────────────┐
                │      Frontend        │
                │      CCTV Page       │
                └──────────┬───────────┘
                           │
                           ▼
                     Backend API
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
       PostgreSQL                  Hugging Face
             │                           │
             │ metadata                  │ video
             │                           │
             ▼                           ▼
       cameraVideos                 .mp4 files
```

PostgreSQL:

```text
videoName
repositoryId
filePath
fileUrl
fileSizeBytes
durationSeconds
recordedAt
```

Hugging Face:

```text
actual .mp4
```

Jadi database tidak menjadi gudang video 4 GB yang bikin PostgreSQL menangis. 😭

---

# 12. Recommended PostgreSQL Index

Karena SmartTwin akan sering mengambil data berdasarkan simpang + waktu, index berikut penting.

```text
trafficStates
    INDEX (intersectionId, windowStart)

trafficApproachStates
    INDEX (trafficStateId)

trafficLaneMetrics
    INDEX (trafficStateId, laneId)

signalStatuses
    INDEX (intersectionId, timestamp)

forecasts
    INDEX (intersectionId, createdAt)

forecastPredictions
    INDEX (forecastId, timestamp)

recommendations
    INDEX (intersectionId, timestamp)

simulations
    INDEX (intersectionId, createdAt)

cameraVideos
    INDEX (cameraId, recordedAt)

cvProcessingJobs
    INDEX (videoId, createdAt)
```

---

# 13. Tables yang Benar-benar Wajib untuk MVP

Kalau deadline kalian mepet, **jangan langsung implementasi semua 20 tabel**.

Prioritas:

### Phase 1 — sekarang

```text
intersections
approaches
lanes

cameras
cameraVideos

cvProcessingJobs

trafficStates
trafficApproachStates
trafficLaneMetrics
```

Ini cukup untuk:

```text
CCTV
   ↓
CV
   ↓
Traffic State Builder
   ↓
PostgreSQL
   ↓
Backend
   ↓
Dashboard
```

### Phase 2 — setelah Traffic State stabil

```text
signalPhases
signalStatuses

forecasts
forecastPredictions
```

### Phase 3 — setelah PPO/SUMO siap

```text
recommendations

simulations
simulationMetrics
```

### Phase 4 — halaman pendukung

```text
users
userSettings
cctvHistory
systemLogs
```

---

# 14. Final Table List

Jadi kalau ditanya **"database SmartTwin kita sebenarnya punya tabel apa saja?"**, jawabannya:

| No | Table                   | Priority | Fungsi                      |
| -: | ----------------------- | -------- | --------------------------- |
|  1 | `users`                 | 🟡       | Akun                        |
|  2 | `userSettings`          | 🟡       | Pengaturan dashboard        |
|  3 | `intersections`         | 🔴       | Data simpang                |
|  4 | `approaches`            | 🔴       | Lengan simpang              |
|  5 | `lanes`                 | 🔴       | Lajur                       |
|  6 | `cameras`               | 🔴       | CCTV                        |
|  7 | `cameraVideos`          | 🔴       | Metadata video              |
|  8 | `cvProcessingJobs`      | 🔴       | Proses YOLO/ByteTrack       |
|  9 | `trafficStates`         | 🔴       | TrafficState                |
| 10 | `trafficApproachStates` | 🔴       | ApproachState               |
| 11 | `trafficLaneMetrics`    | 🔴       | Data CV per lane            |
| 12 | `signalPhases`          | 🟡       | Konfigurasi fase            |
| 13 | `signalStatuses`        | 🟡       | Kondisi lampu               |
| 14 | `forecasts`             | 🟡       | Forecast                    |
| 15 | `forecastPredictions`   | 🟡       | Detail forecast             |
| 16 | `recommendations`       | 🟡       | PPO/rule recommendation     |
| 17 | `simulations`           | 🟡       | Eksperimen SUMO             |
| 18 | `simulationMetrics`     | 🟡       | Delay/queue/throughput/etc. |
| 19 | `cctvHistory`           | 🟢       | Riwayat CCTV                |
| 20 | `systemLogs`            | 🟢       | Log sistem                  |

**🔴 = harus ada untuk pipeline utama**
**🟡 = diperlukan ketika fitur tersebut mulai diintegrasikan**
**🟢 = pendukung dashboard**

### Yang paling penting untuk kondisi kalian sekarang

Jangan mulai dari `users`, `recommendations`, atau `simulationMetrics`.

Urutan pembangunan yang paling aman:

```text
1. intersections
       ↓
2. approaches
       ↓
3. lanes
       ↓
4. cameras
       ↓
5. cameraVideos
       ↓
6. cvProcessingJobs
       ↓
7. trafficLaneMetrics
       ↓
8. trafficStates
       ↓
9. trafficApproachStates
       ↓
10. Backend API
       ↓
11. Frontend Dashboard
```

Dan **Traffic State Builder yang baru saja kalian selesaikan tetap menjadi layer yang mengubah `trafficLaneMetrics`/CSV CV → `trafficStates` + `trafficApproachStates`**. Jadi database ini tidak merusak arsitektur yang sudah kalian bangun; justru database menjadi persistence layer di antara pipeline/backend dan dashboard.

SQL

-- ============================================================
-- SMARTTWIN DATABASE
-- PostgreSQL
-- ============================================================
--
-- SmartTwin:
-- Digital Twin untuk Simulasi Adaptif
-- Pengaturan Lampu Lalu Lintas
--
-- Semua identifier mengikuti camelCase.
-- PostgreSQL membutuhkan double quote untuk mempertahankan
-- camelCase.
--
-- ============================================================


-- ============================================================
-- OPTIONAL CLEANUP
-- ============================================================
-- Hapus bagian ini kalau database sudah berisi data production.
--
-- DROP TABLE IF EXISTS
--     "simulationMetrics",
--     "simulations",
--     "recommendations",
--     "forecastPredictions",
--     "forecasts",
--     "signalStatuses",
--     "trafficApproachStates",
--     "trafficStates",
--     "cameraVideos",
--     "cameras",
--     "lanes",
--     "approaches",
--     "intersections"
-- CASCADE;


-- ============================================================
-- 1. INTERSECTIONS
-- ============================================================
-- Menyimpan data persimpangan.
--
-- Contoh:
-- simpang4-pingit
--
-- Satu intersection memiliki:
-- - banyak approach
-- - banyak camera
-- - banyak traffic state
-- - banyak signal status
-- - banyak forecast
-- - banyak recommendation
-- - banyak simulation run
-- ============================================================

CREATE TABLE "intersections" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "intersectionId" VARCHAR(100) NOT NULL UNIQUE,

    "name" VARCHAR(255) NOT NULL,

    "latitude" DOUBLE PRECISION,

    "longitude" DOUBLE PRECISION,

    "description" TEXT,

    "isActive" BOOLEAN NOT NULL DEFAULT TRUE,

    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 2. APPROACHES
-- ============================================================
-- Approach = lengan/arah jalan yang menuju persimpangan.
--
-- Contoh simpang 4:
--
-- north
-- south
-- east
-- west
--
-- Satu intersection memiliki 4 approach.
-- ============================================================

CREATE TABLE "approaches" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "intersectionId" BIGINT NOT NULL,

    "approach" VARCHAR(20) NOT NULL,

    "name" VARCHAR(100),

    "sortOrder" INTEGER NOT NULL DEFAULT 0,

    "isActive" BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT "fkApproachIntersection"
        FOREIGN KEY ("intersectionId")
        REFERENCES "intersections" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkApproachDirection"
        CHECK (
            "approach" IN (
                'north',
                'south',
                'east',
                'west'
            )
        ),

    CONSTRAINT "uniqueIntersectionApproach"
        UNIQUE ("intersectionId", "approach")
);


-- ============================================================
-- 3. LANES
-- ============================================================
-- Menyimpan konfigurasi lajur pada setiap approach.
--
-- Contoh:
--
-- north
-- ├── lane_1
-- ├── lane_2
-- └── lane_3
--
-- Data CSV CV masih menggunakan lane_id seperti:
-- lane_1
-- lane_2
-- lane_3
--
-- Tabel ini hanya menyimpan konfigurasi lane,
-- bukan seluruh hasil deteksi kendaraan.
-- ============================================================

CREATE TABLE "lanes" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "approachId" BIGINT NOT NULL,

    "laneId" VARCHAR(50) NOT NULL,

    "laneName" VARCHAR(100),

    "laneIndex" INTEGER,

    "isActive" BOOLEAN NOT NULL DEFAULT TRUE,

    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "fkLaneApproach"
        FOREIGN KEY ("approachId")
        REFERENCES "approaches" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "uniqueApproachLane"
        UNIQUE ("approachId", "laneId")
);


-- ============================================================
-- 4. CAMERAS
-- ============================================================
-- Data kamera/CCTV yang digunakan sistem.
--
-- Kamera bisa berupa:
-- - CCTV publik
-- - kamera ATCS
-- - kamera dataset
-- - kamera upload/manual
-- ============================================================

CREATE TABLE "cameras" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "intersectionId" BIGINT NOT NULL,

    "cameraName" VARCHAR(255) NOT NULL,

    "cameraCode" VARCHAR(100),

    "sourceType" VARCHAR(50) NOT NULL DEFAULT 'dataset',

    "sourceUrl" TEXT,

    "description" TEXT,

    "isActive" BOOLEAN NOT NULL DEFAULT TRUE,

    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "fkCameraIntersection"
        FOREIGN KEY ("intersectionId")
        REFERENCES "intersections" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkCameraSourceType"
        CHECK (
            "sourceType" IN (
                'live',
                'recording',
                'dataset',
                'upload'
            )
        )
);


-- ============================================================
-- 5. VIDEO UPLOADS
-- ============================================================
-- Menyimpan metadata video yang di-upload melalui halaman CCTV.
--
-- FILE VIDEO TIDAK disimpan di PostgreSQL.
--
-- Video:
--
-- Frontend
--    ↓
-- Backend
--    ↓
-- Hugging Face
--
-- PostgreSQL hanya menyimpan:
-- - metadata video
-- - status processing
-- - lokasi file
-- - Hugging Face repository
-- - hasil processing
--
-- Ini jauh lebih aman daripada menyimpan file video
-- 4 GB langsung di PostgreSQL.
-- ============================================================

CREATE TABLE "cameraVideos" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "cameraId" BIGINT,

    "intersectionId" BIGINT NOT NULL,

    "fileName" VARCHAR(255) NOT NULL,

    "fileSizeBytes" BIGINT,

    "mimeType" VARCHAR(100),

    "durationSeconds" DOUBLE PRECISION,

    "storageProvider" VARCHAR(50) NOT NULL DEFAULT 'huggingface',

    "huggingFaceRepoId" VARCHAR(255),

    "huggingFacePath" TEXT,

    "videoUrl" TEXT,

    "status" VARCHAR(50) NOT NULL DEFAULT 'uploaded',

    "processingStartedAt" TIMESTAMPTZ,

    "processingCompletedAt" TIMESTAMPTZ,

    "errorMessage" TEXT,

    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "fkVideoCamera"
        FOREIGN KEY ("cameraId")
        REFERENCES "cameras" ("id")
        ON DELETE SET NULL,

    CONSTRAINT "fkVideoIntersection"
        FOREIGN KEY ("intersectionId")
        REFERENCES "intersections" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkVideoStorageProvider"
        CHECK (
            "storageProvider" IN (
                'huggingface',
                'local',
                'other'
            )
        ),

    CONSTRAINT "checkVideoStatus"
        CHECK (
            "status" IN (
                'uploaded',
                'processing',
                'completed',
                'failed'
            )
        )
);


-- ============================================================
-- 6. TRAFFIC STATES
-- ============================================================
-- Header dari TrafficState.
--
-- Sesuai contract:
--
-- intersectionId
-- windowStart
-- windowEnd
-- approaches
--
-- Satu row = satu TrafficState untuk satu time window.
--
-- Contoh:
--
-- 16:30:10 -> 16:30:15
--
-- menjadi satu TrafficState.
-- ============================================================

CREATE TABLE "trafficStates" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "intersectionId" BIGINT NOT NULL,

    "windowStart" TIMESTAMPTZ NOT NULL,

    "windowEnd" TIMESTAMPTZ NOT NULL,

    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "fkTrafficStateIntersection"
        FOREIGN KEY ("intersectionId")
        REFERENCES "intersections" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkTrafficWindow"
        CHECK ("windowEnd" > "windowStart"),

    CONSTRAINT "uniqueTrafficWindow"
        UNIQUE (
            "intersectionId",
            "windowStart",
            "windowEnd"
        )
);


-- ============================================================
-- 7. APPROACH STATES
-- ============================================================
-- Detail TrafficState untuk setiap approach.
--
-- Field disesuaikan langsung dengan contract:
--
-- approach
-- volume
-- carCount
-- motorcycleCount
-- busCount
-- truckCount
-- queueLengthVeh
-- queueLengthMEst
-- densityIndex
-- avgSpeedKmh
--
-- avgSpeedKmh BOLEH NULL.
--
-- NULL berarti:
-- "data speed belum tersedia"
--
-- BUKAN:
-- 0
-- ============================================================

CREATE TABLE "trafficApproachStates" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "trafficStateId" BIGINT NOT NULL,

    "approachId" BIGINT NOT NULL,

    "volume" INTEGER NOT NULL DEFAULT 0,

    "carCount" INTEGER NOT NULL DEFAULT 0,

    "motorcycleCount" INTEGER NOT NULL DEFAULT 0,

    "busCount" INTEGER NOT NULL DEFAULT 0,

    "truckCount" INTEGER NOT NULL DEFAULT 0,

    "queueLengthVeh" INTEGER NOT NULL DEFAULT 0,

    "queueLengthMEst" DOUBLE PRECISION NOT NULL DEFAULT 0,

    "densityIndex" DOUBLE PRECISION NOT NULL DEFAULT 0,

    "avgSpeedKmh" DOUBLE PRECISION,

    CONSTRAINT "fkApproachStateTrafficState"
        FOREIGN KEY ("trafficStateId")
        REFERENCES "trafficStates" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "fkApproachStateApproach"
        FOREIGN KEY ("approachId")
        REFERENCES "approaches" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkVolume"
        CHECK ("volume" >= 0),

    CONSTRAINT "checkCarCount"
        CHECK ("carCount" >= 0),

    CONSTRAINT "checkMotorcycleCount"
        CHECK ("motorcycleCount" >= 0),

    CONSTRAINT "checkBusCount"
        CHECK ("busCount" >= 0),

    CONSTRAINT "checkTruckCount"
        CHECK ("truckCount" >= 0),

    CONSTRAINT "checkQueueLengthVeh"
        CHECK ("queueLengthVeh" >= 0),

    CONSTRAINT "checkQueueLengthMEst"
        CHECK ("queueLengthMEst" >= 0),

    CONSTRAINT "checkDensityIndex"
        CHECK ("densityIndex" >= 0),

    CONSTRAINT "checkAvgSpeed"
        CHECK (
            "avgSpeedKmh" IS NULL
            OR "avgSpeedKmh" >= 0
        ),

    CONSTRAINT "uniqueTrafficStateApproach"
        UNIQUE (
            "trafficStateId",
            "approachId"
        )
);


-- ============================================================
-- 8. SIGNAL STATUSES
-- ============================================================
-- Menyimpan snapshot status lampu lalu lintas.
--
-- Sesuai contract:
--
-- intersectionId
-- timestamp
-- currentPhase
-- phaseName
-- remainingSeconds
-- cycleTimeSeconds
-- source
--
-- Ini bisa dipakai untuk:
-- - Dashboard
-- - History
-- - monitoring
-- ============================================================

CREATE TABLE "signalStatuses" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "intersectionId" BIGINT NOT NULL,

    "timestamp" TIMESTAMPTZ NOT NULL,

    "currentPhase" VARCHAR(100) NOT NULL,

    "phaseName" VARCHAR(255) NOT NULL,

    "remainingSeconds" INTEGER NOT NULL,

    "cycleTimeSeconds" INTEGER NOT NULL,

    "source" VARCHAR(100) NOT NULL,

    CONSTRAINT "fkSignalStatusIntersection"
        FOREIGN KEY ("intersectionId")
        REFERENCES "intersections" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkRemainingSeconds"
        CHECK ("remainingSeconds" >= 0),

    CONSTRAINT "checkCycleTimeSeconds"
        CHECK ("cycleTimeSeconds" > 0)
);


-- ============================================================
-- 9. FORECASTS
-- ============================================================
-- Header hasil forecasting.
--
-- Sesuai contract:
--
-- intersectionId
-- horizonMinutes
-- model
-- predictions
--
-- predictions disimpan pada tabel terpisah.
-- ============================================================

CREATE TABLE "forecasts" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "intersectionId" BIGINT NOT NULL,

    "horizonMinutes" INTEGER NOT NULL,

    "model" VARCHAR(100) NOT NULL,

    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "fkForecastIntersection"
        FOREIGN KEY ("intersectionId")
        REFERENCES "intersections" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkForecastHorizon"
        CHECK ("horizonMinutes" > 0)
);


-- ============================================================
-- 10. FORECAST PREDICTIONS
-- ============================================================
-- Detail prediction.
--
-- Sesuai contract:
--
-- timestamp
-- predictedVehicleCount
-- predictedQueueLengthVeh
-- predictedQueueLengthMEst
-- predictedDensityIndex
-- predictedSpeedKmh
-- ============================================================

CREATE TABLE "forecastPredictions" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "forecastId" BIGINT NOT NULL,

    "timestamp" TIMESTAMPTZ NOT NULL,

    "predictedVehicleCount" DOUBLE PRECISION NOT NULL,

    "predictedQueueLengthVeh" DOUBLE PRECISION NOT NULL,

    "predictedQueueLengthMEst" DOUBLE PRECISION NOT NULL,

    "predictedDensityIndex" DOUBLE PRECISION NOT NULL,

    "predictedSpeedKmh" DOUBLE PRECISION,

    CONSTRAINT "fkForecastPredictionForecast"
        FOREIGN KEY ("forecastId")
        REFERENCES "forecasts" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkPredictedVehicleCount"
        CHECK ("predictedVehicleCount" >= 0),

    CONSTRAINT "checkPredictedQueueLengthVeh"
        CHECK ("predictedQueueLengthVeh" >= 0),

    CONSTRAINT "checkPredictedQueueLengthMEst"
        CHECK ("predictedQueueLengthMEst" >= 0),

    CONSTRAINT "checkPredictedDensityIndex"
        CHECK ("predictedDensityIndex" >= 0),

    CONSTRAINT "checkPredictedSpeed"
        CHECK (
            "predictedSpeedKmh" IS NULL
            OR "predictedSpeedKmh" >= 0
        ),

    CONSTRAINT "uniqueForecastTimestamp"
        UNIQUE (
            "forecastId",
            "timestamp"
        )
);


-- ============================================================
-- 11. RECOMMENDATIONS
-- ============================================================
-- Hasil Adaptive Decision Engine / PPO.
--
-- Sesuai contract:
--
-- intersectionId
-- timestamp
-- recommendedPhase
-- recommendedGreenSeconds
-- currentGreenSeconds
-- expectedDelayReductionPercent
-- confidence
-- reason
-- source
-- ============================================================

CREATE TABLE "recommendations" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "intersectionId" BIGINT NOT NULL,

    "timestamp" TIMESTAMPTZ NOT NULL,

    "recommendedPhase" VARCHAR(100) NOT NULL,

    "recommendedGreenSeconds" INTEGER NOT NULL,

    "currentGreenSeconds" INTEGER NOT NULL,

    "expectedDelayReductionPercent" DOUBLE PRECISION NOT NULL,

    "confidence" DOUBLE PRECISION NOT NULL,

    "reason" TEXT NOT NULL,

    "source" VARCHAR(100) NOT NULL,

    CONSTRAINT "fkRecommendationIntersection"
        FOREIGN KEY ("intersectionId")
        REFERENCES "intersections" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "checkRecommendedGreenSeconds"
        CHECK ("recommendedGreenSeconds" >= 0),

    CONSTRAINT "checkCurrentGreenSeconds"
        CHECK ("currentGreenSeconds" >= 0),

    CONSTRAINT "checkRecommendationConfidence"
        CHECK (
            "confidence" >= 0
            AND "confidence" <= 1
        )
);


-- ============================================================
-- 12. SIMULATION RUNS
-- ============================================================
-- Menyimpan satu eksekusi simulasi SUMO.
--
-- Contoh:
--
-- Run #1
-- menggunakan:
-- - TrafficState tertentu
-- - scenario tertentu
--
-- Hasilnya dapat dilihat di simulationMetrics.
-- ============================================================

CREATE TABLE "simulations" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "intersectionId" BIGINT NOT NULL,

    "trafficStateId" BIGINT,

    "forecastId" BIGINT,

    "recommendationId" BIGINT,

    "scenarioName" VARCHAR(255) NOT NULL,

    "status" VARCHAR(50) NOT NULL DEFAULT 'pending',

    "startedAt" TIMESTAMPTZ,

    "completedAt" TIMESTAMPTZ,

    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    "errorMessage" TEXT,

    CONSTRAINT "fkSimulationIntersection"
        FOREIGN KEY ("intersectionId")
        REFERENCES "intersections" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "fkSimulationTrafficState"
        FOREIGN KEY ("trafficStateId")
        REFERENCES "trafficStates" ("id")
        ON DELETE SET NULL,

    CONSTRAINT "fkSimulationForecast"
        FOREIGN KEY ("forecastId")
        REFERENCES "forecasts" ("id")
        ON DELETE SET NULL,

    CONSTRAINT "fkSimulationRecommendation"
        FOREIGN KEY ("recommendationId")
        REFERENCES "recommendations" ("id")
        ON DELETE SET NULL,

    CONSTRAINT "checkSimulationStatus"
        CHECK (
            "status" IN (
                'pending',
                'running',
                'completed',
                'failed'
            )
        )
);


-- ============================================================
-- 13. SIMULATION METRICS
-- ============================================================
-- Hasil evaluasi simulasi SUMO.
--
-- Metrics yang memang dibutuhkan SmartTwin:
--
-- delay
-- queue
-- throughput
-- waiting time
-- emission
--
-- Bisa disimpan per approach atau sebagai total intersection.
-- ============================================================

CREATE TABLE "simulationMetrics" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    "simulationRunId" BIGINT NOT NULL,

    "approachId" BIGINT,

    "timestamp" TIMESTAMPTZ,

    "delaySeconds" DOUBLE PRECISION,

    "queueLengthVeh" DOUBLE PRECISION,

    "throughputVeh" DOUBLE PRECISION,

    "waitingTimeSeconds" DOUBLE PRECISION,

    "emission" DOUBLE PRECISION,

    CONSTRAINT "fkSimulationMetricRun"
        FOREIGN KEY ("simulationRunId")
        REFERENCES "simulations" ("id")
        ON DELETE CASCADE,

    CONSTRAINT "fkSimulationMetricApproach"
        FOREIGN KEY ("approachId")
        REFERENCES "approaches" ("id")
        ON DELETE SET NULL,

    CONSTRAINT "checkDelay"
        CHECK (
            "delaySeconds" IS NULL
            OR "delaySeconds" >= 0
        ),

    CONSTRAINT "checkSimulationQueue"
        CHECK (
            "queueLengthVeh" IS NULL
            OR "queueLengthVeh" >= 0
        ),

    CONSTRAINT "checkThroughput"
        CHECK (
            "throughputVeh" IS NULL
            OR "throughputVeh" >= 0
        ),

    CONSTRAINT "checkWaitingTime"
        CHECK (
            "waitingTimeSeconds" IS NULL
            OR "waitingTimeSeconds" >= 0
        ),

    CONSTRAINT "checkEmission"
        CHECK (
            "emission" IS NULL
            OR "emission" >= 0
        )
);


-- ============================================================
-- INDEXES
-- ============================================================

-- ------------------------------------------------------------
-- Intersection
-- ------------------------------------------------------------

CREATE INDEX "idxApproachesIntersection"
ON "approaches" ("intersectionId");

CREATE INDEX "idxLanesApproach"
ON "lanes" ("approachId");

CREATE INDEX "idxCamerasIntersection"
ON "cameras" ("intersectionId");

CREATE INDEX "idxVideoUploadsIntersection"
ON "cameraVideos" ("intersectionId");

CREATE INDEX "idxVideoUploadsCamera"
ON "cameraVideos" ("cameraId");

CREATE INDEX "idxVideoUploadsStatus"
ON "cameraVideos" ("status");


-- ------------------------------------------------------------
-- Traffic
-- ------------------------------------------------------------

CREATE INDEX "idxTrafficStatesIntersectionTime"
ON "trafficStates" (
    "intersectionId",
    "windowStart" DESC
);

CREATE INDEX "idxApproachStatesTrafficState"
ON "trafficApproachStates" ("trafficStateId");

CREATE INDEX "idxApproachStatesApproach"
ON "trafficApproachStates" ("approachId");


-- ------------------------------------------------------------
-- Signal
-- ------------------------------------------------------------

CREATE INDEX "idxSignalStatusesIntersectionTime"
ON "signalStatuses" (
    "intersectionId",
    "timestamp" DESC
);


-- ------------------------------------------------------------
-- Forecast
-- ------------------------------------------------------------

CREATE INDEX "idxForecastsIntersectionTime"
ON "forecasts" (
    "intersectionId",
    "createdAt" DESC
);

CREATE INDEX "idxForecastPredictionsForecastTime"
ON "forecastPredictions" (
    "forecastId",
    "timestamp"
);


-- ------------------------------------------------------------
-- Recommendation
-- ------------------------------------------------------------

CREATE INDEX "idxRecommendationsIntersectionTime"
ON "recommendations" (
    "intersectionId",
    "timestamp" DESC
);


-- ------------------------------------------------------------
-- Simulation
-- ------------------------------------------------------------

CREATE INDEX "idxSimulationRunsIntersectionTime"
ON "simulations" (
    "intersectionId",
    "createdAt" DESC
);

CREATE INDEX "idxSimulationMetricsRun"
ON "simulationMetrics" ("simulationRunId");


-- ============================================================
-- END OF SCHEMA
-- ============================================================
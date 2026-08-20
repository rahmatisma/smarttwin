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
* system logs

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
 │    ├── TrafficApproachState
 │    └── TrafficLaneMetric
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
                    └──────┬───────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Intersection  │
                  └───────┬────────┘
                          │
          ┌───────────────┼─────────────────────┐
          │               │                     │
          ▼               ▼                     ▼
   ┌────────────┐   ┌────────────┐      ┌──────────────┐
   │  Approach  │   │   Camera   │      │ TrafficState │
   └─────┬──────┘   └──────┬─────┘      └──────┬───────┘
         │                 │                   │
         ▼                 ▼                   ├── TrafficApproachState
      ┌──────┐       ┌────────────┐            │
      │ Lane │       │CameraVideo │            └── TrafficLaneMetric
      └──────┘       └──────┬─────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │CvProcessingJob  │
                    └─────────────────┘


Intersection
 │
 ├── SignalPhase
 │       │
 │       ▼
 │   SignalStatus
 │
 ├── Forecast
 │       │
 │       ▼
 │   ForecastPrediction
 │
 ├── Recommendation
 │
 └── Simulation
         │
         ▼
   SimulationMetric
```

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

## 2.2 `userSettings`

Menyimpan pengaturan dashboard masing-masing user.

| Column                  | Type          | Constraint              | Description      |
| ----------------------- | ------------- | ----------------------- | ---------------- |
| `id`                    | `bigserial`   | PK                      | ID setting       |
| `userId`                | `bigint`      | FK → `users.id`         | Pemilik setting  |
| `defaultIntersectionId` | `bigint`      | FK → `intersections.id` | Simpang default  |
| `theme`                 | `varchar(20)` | NOT NULL                | Tema dashboard   |
| `createdAt`             | `timestamptz` | NOT NULL                | Waktu dibuat     |
| `updatedAt`             | `timestamptz` | NOT NULL                | Waktu diperbarui |

Constraint:

```text
UNIQUE(userId)
```

Relasi:

```text
users 1 ─────── 1 userSettings
```

---

## 2.3 `intersections`

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

## 2.4 `approaches`

Menyimpan empat lengan persimpangan.

| Column           | Type           | Constraint              | Description           |
| ---------------- | -------------- | ----------------------- | --------------------- |
| `id`             | `bigserial`    | PK                      | ID approach           |
| `intersectionId` | `bigint`       | FK → `intersections.id` | Simpang               |
| `approach`       | `varchar(10)`  | NOT NULL                | north/south/east/west |
| `name`           | `varchar(100)` | NULL                    | Nama approach         |
| `createdAt`      | `timestamptz`  | NOT NULL                | Waktu dibuat          |

Nilai `approach`:

```text
north
south
east
west
```

Constraint:

```text
UNIQUE(intersectionId, approach)
```

Relasi:

```text
intersections 1 ─────── N approaches
```

---

## 2.5 `lanes`

Menyimpan lane pada masing-masing approach.

| Column       | Type          | Constraint           | Description     |
| ------------ | ------------- | -------------------- | --------------- |
| `id`         | `bigserial`   | PK                   | ID lane         |
| `approachId` | `bigint`      | FK → `approaches.id` | Approach        |
| `laneId`     | `varchar(50)` | NOT NULL             | ID lane         |
| `laneNumber` | `integer`     | NULL                 | Nomor lane      |
| `direction`  | `varchar(30)` | NULL                 | Arah pergerakan |
| `createdAt`  | `timestamptz` | NOT NULL             | Waktu dibuat    |

Constraint:

```text
UNIQUE(approachId, laneId)
```

Contoh:

```text
north
 ├── lane_1
 ├── lane_2
 └── lane_3
```

**Catatan:** walaupun data CSV sekarang menggunakan `lane_1`, `lane_2`, dst., database tetap memakai `laneId` sebagai nama field camelCase.

---

## 2.6 `cameras`

Menyimpan informasi CCTV.

| Column           | Type           | Constraint              | Description      |
| ---------------- | -------------- | ----------------------- | ---------------- |
| `id`             | `bigserial`    | PK                      | ID kamera        |
| `intersectionId` | `bigint`       | FK → `intersections.id` | Simpang          |
| `cameraId`       | `varchar(100)` | UNIQUE, NOT NULL        | ID kamera        |
| `name`           | `varchar(150)` | NOT NULL                | Nama kamera      |
| `approachId`     | `bigint`       | FK → `approaches.id`    | Approach kamera  |
| `sourceType`     | `varchar(30)`  | NOT NULL                | Sumber kamera    |
| `sourceUrl`      | `text`         | NULL                    | URL stream       |
| `status`         | `varchar(30)`  | NOT NULL                | Status kamera    |
| `createdAt`      | `timestamptz`  | NOT NULL                | Waktu dibuat     |
| `updatedAt`      | `timestamptz`  | NOT NULL                | Waktu diperbarui |

`sourceType`:

```text
live
uploaded
dataset
```

Relasi:

```text
intersections 1 ─────── N cameras
approaches    1 ─────── N cameras
```

---

## 2.7 `cameraVideos`

Ini **penting untuk halaman CCTV**.

Video disimpan di Hugging Face, bukan PostgreSQL.

| Column            | Type           | Constraint        | Description      |
| ----------------- | -------------- | ----------------- | ---------------- |
| `id`              | `bigserial`    | PK                | ID video         |
| `cameraId`        | `bigint`       | FK → `cameras.id` | Kamera           |
| `videoName`       | `varchar(255)` | NOT NULL          | Nama video       |
| `videoFormat`     | `varchar(20)`  | NOT NULL          | Format video     |
| `storageProvider` | `varchar(30)`  | NOT NULL          | Penyimpanan      |
| `repositoryId`    | `varchar(255)` | NULL              | ID repository HF |
| `filePath`        | `text`         | NULL              | Path file di HF  |
| `fileUrl`         | `text`         | NULL              | URL video        |
| `durationSeconds` | `integer`      | NULL              | Durasi           |
| `fileSizeBytes`   | `bigint`       | NULL              | Ukuran file      |
| `recordedAt`      | `timestamptz`  | NULL              | Waktu rekaman    |
| `uploadedAt`      | `timestamptz`  | NOT NULL          | Waktu upload     |
| `status`          | `varchar(30)`  | NOT NULL          | Status video     |

**Perubahan penting:**

Field `intersectionName` dihapus karena redundant.

Relasi:

```text
Camera
   │
   └── CameraVideo
```

Informasi persimpangan video dapat diperoleh melalui:

```text
cameraVideos.cameraId
        ↓
cameras.id
        ↓
cameras.intersectionId
        ↓
intersections.id
```

Contoh:

```text
storageProvider = huggingface
repositoryId = username/smarttwin-cctv
filePath = videos/simpang4-pingit/video01.mp4
videoFormat = mp4
```

---

## 2.8 `cvProcessingJobs`

Mencatat proses YOLO + ByteTrack terhadap video.

| Column         | Type           | Constraint             | Description      |
| -------------- | -------------- | ---------------------- | ---------------- |
| `id`           | `bigserial`    | PK                     | ID job           |
| `videoId`      | `bigint`       | FK → `cameraVideos.id` | Video input      |
| `modelName`    | `varchar(100)` | NULL                   | Model CV         |
| `modelVersion` | `varchar(50)`  | NULL                   | Versi model      |
| `startedAt`    | `timestamptz`  | NULL                   | Waktu mulai      |
| `completedAt`  | `timestamptz`  | NULL                   | Waktu selesai    |
| `status`       | `varchar(30)`  | NOT NULL               | Status proses    |
| `outputPath`   | `text`         | NULL                   | Lokasi output    |
| `errorMessage` | `text`         | NULL                   | Error jika gagal |
| `createdAt`    | `timestamptz`  | NOT NULL               | Waktu dibuat     |

Status:

```text
queued
processing
completed
failed
```

Relasi:

```text
CameraVideo 1 ─────── N CvProcessingJob
```

---

## 2.9 `trafficStates`

Ini merupakan **parent entity dari TrafficState contract**.

| Column            | Type          | Constraint                 | Description  |
| ----------------- | ------------- | -------------------------- | ------------ |
| `id`              | `bigserial`   | PK                         | ID internal  |
| `intersectionId`  | `bigint`      | FK → `intersections.id`    | Simpang      |
| `windowStart`     | `timestamptz` | NOT NULL                   | Awal window  |
| `windowEnd`       | `timestamptz` | NOT NULL                   | Akhir window |
| `source`          | `varchar(30)` | NOT NULL                   | Sumber data  |
| `processingJobId` | `bigint`      | FK → `cvProcessingJobs.id` | CV job       |
| `createdAt`       | `timestamptz` | NOT NULL                   | Waktu dibuat |

Contoh:

```text
windowStart = 2026-08-15T16:30:10
windowEnd   = 2026-08-15T16:30:15
```

Relasi:

```text
Intersection 1 ─────── N TrafficState

CvProcessingJob 1 ─── N TrafficState
```

---

## 2.10 `trafficApproachStates`

Ini bagian **paling penting** untuk menyimpan `ApproachState`.

| Column            | Type               | Constraint              | Description              |
| ----------------- | ------------------ | ----------------------- | ------------------------ |
| `id`              | `bigserial`        | PK                      | ID                       |
| `trafficStateId`  | `bigint`           | FK → `trafficStates.id` | Traffic state            |
| `approachId`      | `bigint`           | FK → `approaches.id`    | Approach                 |
| `approach`        | `varchar(10)`      | NOT NULL                | north/south/east/west    |
| `volume`          | `integer`          | NOT NULL                | Total kendaraan          |
| `carCount`        | `integer`          | NOT NULL                | Jumlah mobil             |
| `motorcycleCount` | `integer`          | NOT NULL                | Jumlah motor             |
| `busCount`        | `integer`          | NOT NULL                | Jumlah bus               |
| `truckCount`      | `integer`          | NOT NULL                | Jumlah truk              |
| `queueLengthVeh`  | `integer`          | NOT NULL                | Jumlah kendaraan antre   |
| `queueLengthMEst` | `double precision` | NOT NULL                | Estimasi panjang antrean |
| `densityIndex`    | `double precision` | NOT NULL                | Proxy kepadatan          |
| `avgSpeedKmh`     | `double precision` | NULL                    | Kecepatan rata-rata      |

Constraint:

```text
UNIQUE(trafficStateId, approachId)
```

### Kenapa `approachId` dan `approach` sama-sama ada?

`approachId` digunakan untuk **relasi database**.

`approach` digunakan untuk **data contract/API**.

Jadi:

```text
approachId
    ↓
approaches
    ↓
approach = north
```

Backend dapat mengembalikan:

```json
{
  "approach": "north"
}
```

tanpa mengubah contract frontend.

### Sangat penting

Field contract harus persis:

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

## 2.11 `trafficLaneMetrics`

Direkomendasikan untuk SmartTwin karena data CV awal masih berbentuk:

```text
timestamp + approach + lane
```

| Column            | Type               | Constraint              | Description        |
| ----------------- | ------------------ | ----------------------- | ------------------ |
| `id`              | `bigserial`        | PK                      | ID                 |
| `trafficStateId`  | `bigint`           | FK → `trafficStates.id` | Traffic state      |
| `laneId`          | `bigint`           | FK → `lanes.id`         | Lane               |
| `timestamp`       | `timestamptz`      | NOT NULL                | Timestamp CV       |
| `vehicleCount`    | `integer`          | NOT NULL                | Kendaraan crossing |
| `carCount`        | `integer`          | NOT NULL                | Mobil              |
| `motorcycleCount` | `integer`          | NOT NULL                | Motor              |
| `busCount`        | `integer`          | NOT NULL                | Bus                |
| `truckCount`      | `integer`          | NOT NULL                | Truk               |
| `queueLengthVeh`  | `integer`          | NOT NULL                | Antrean lane       |
| `queueLengthMEst` | `double precision` | NOT NULL                | Panjang antrean    |
| `densityIndex`    | `double precision` | NOT NULL                | Density proxy      |

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

Relasi:

```text
TrafficState 1 ─────── N TrafficLaneMetric

Lane 1 ─────────────── N TrafficLaneMetric
```

Ini sangat membantu jika nanti perlu melakukan audit mengapa suatu `TrafficState` menghasilkan angka tertentu.

---

## 2.12 `signalPhases`

Menyimpan konfigurasi fase lampu.

| Column             | Type           | Constraint              | Description    |
| ------------------ | -------------- | ----------------------- | -------------- |
| `id`               | `bigserial`    | PK                      | ID fase        |
| `intersectionId`   | `bigint`       | FK → `intersections.id` | Simpang        |
| `phaseId`          | `varchar(50)`  | NOT NULL                | ID fase        |
| `phaseName`        | `varchar(100)` | NOT NULL                | Nama fase      |
| `sequenceOrder`    | `integer`      | NOT NULL                | Urutan         |
| `greenSeconds`     | `integer`      | NOT NULL                | Green          |
| `yellowSeconds`    | `integer`      | NOT NULL                | Yellow         |
| `redSeconds`       | `integer`      | NOT NULL                | Red            |
| `activeApproaches` | `jsonb`        | NOT NULL                | Approach aktif |
| `isActive`         | `boolean`      | NOT NULL                | Status         |

Constraint:

```text
UNIQUE(intersectionId, phaseId)
```

Contoh:

```json
["north", "south"]
```

`activeApproaches` tetap menggunakan JSON karena satu phase dapat mengaktifkan beberapa approach.

---

## 2.13 `signalStatuses`

Menyimpan kondisi lampu pada waktu tertentu.

| Column             | Type           | Constraint              | Description  |
| ------------------ | -------------- | ----------------------- | ------------ |
| `id`               | `bigserial`    | PK                      | ID           |
| `intersectionId`   | `bigint`       | FK → `intersections.id` | Simpang      |
| `timestamp`        | `timestamptz`  | NOT NULL                | Waktu        |
| `currentPhase`     | `varchar(50)`  | NOT NULL                | Fase aktif   |
| `phaseName`        | `varchar(100)` | NOT NULL                | Nama fase    |
| `remainingSeconds` | `integer`      | NOT NULL                | Sisa waktu   |
| `cycleTimeSeconds` | `integer`      | NOT NULL                | Waktu siklus |
| `source`           | `varchar(30)`  | NOT NULL                | Sumber       |

Field API tetap:

```text
currentPhase
phaseName
remainingSeconds
cycleTimeSeconds
source
```

Relasi:

```text
Intersection 1 ─────── N SignalStatus
```

---

## 2.14 `forecasts`

Menyimpan metadata satu proses forecasting.

| Column           | Type           | Constraint              | Description      |
| ---------------- | -------------- | ----------------------- | ---------------- |
| `id`             | `bigserial`    | PK                      | ID               |
| `intersectionId` | `bigint`       | FK → `intersections.id` | Simpang          |
| `horizonMinutes` | `integer`      | NOT NULL                | Horizon prediksi |
| `model`          | `varchar(100)` | NOT NULL                | Model            |
| `createdAt`      | `timestamptz`  | NOT NULL                | Waktu prediksi   |

Contoh:

```text
horizonMinutes = 15
model = LSTM
```

---

## 2.15 `forecastPredictions`

Menyimpan setiap titik prediksi.

| Column                     | Type               | Constraint          | Description              |
| -------------------------- | ------------------ | ------------------- | ------------------------ |
| `id`                       | `bigserial`        | PK                  | ID                       |
| `forecastId`               | `bigint`           | FK → `forecasts.id` | Forecast                 |
| `timestamp`                | `timestamptz`      | NOT NULL            | Waktu prediksi           |
| `predictedVehicleCount`    | `double precision` | NOT NULL            | Prediksi kendaraan       |
| `predictedQueueLengthVeh`  | `double precision` | NOT NULL            | Prediksi antrean         |
| `predictedQueueLengthMEst` | `double precision` | NOT NULL            | Prediksi panjang antrean |
| `predictedDensityIndex`    | `double precision` | NOT NULL            | Prediksi density         |
| `predictedSpeedKmh`        | `double precision` | NULL                | Prediksi speed           |

Relasi:

```text
Forecast 1 ─────── N ForecastPrediction
```

---

## 2.16 `recommendations`

Untuk halaman **Signal Recommendation**.

| Column                          | Type               | Constraint              | Description                |
| ------------------------------- | ------------------ | ----------------------- | -------------------------- |
| `id`                            | `bigserial`        | PK                      | ID                         |
| `intersectionId`                | `bigint`           | FK → `intersections.id` | Simpang                    |
| `timestamp`                     | `timestamptz`      | NOT NULL                | Waktu                      |
| `recommendedPhase`              | `varchar(50)`      | NOT NULL                | Fase rekomendasi           |
| `recommendedGreenSeconds`       | `integer`          | NOT NULL                | Green rekomendasi          |
| `currentGreenSeconds`           | `integer`          | NOT NULL                | Green saat ini             |
| `expectedDelayReductionPercent` | `double precision` | NOT NULL                | Estimasi pengurangan delay |
| `confidence`                    | `double precision` | NOT NULL                | Confidence                 |
| `reason`                        | `text`             | NOT NULL                | Alasan                     |
| `source`                        | `varchar(30)`      | NOT NULL                | Sumber                     |
| `createdAt`                     | `timestamptz`      | NOT NULL                | Waktu dibuat               |

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

## 2.17 `simulations`

Menyimpan setiap eksperimen Digital Twin / SUMO.

| Column             | Type           | Constraint                | Description       |
| ------------------ | -------------- | ------------------------- | ----------------- |
| `id`               | `bigserial`    | PK                        | ID simulation     |
| `intersectionId`   | `bigint`       | FK → `intersections.id`   | Simpang           |
| `trafficStateId`   | `bigint`       | FK → `trafficStates.id`   | State input       |
| `recommendationId` | `bigint`       | FK → `recommendations.id` | Recommendation    |
| `simulationName`   | `varchar(150)` | NOT NULL                  | Nama simulasi     |
| `simulationType`   | `varchar(50)`  | NOT NULL                  | Jenis simulasi    |
| `engine`           | `varchar(50)`  | NOT NULL                  | Simulation engine |
| `status`           | `varchar(30)`  | NOT NULL                  | Status            |
| `startedAt`        | `timestamptz`  | NULL                      | Mulai             |
| `completedAt`      | `timestamptz`  | NULL                      | Selesai           |
| `createdAt`        | `timestamptz`  | NOT NULL                  | Dibuat            |

Contoh:

```text
simulationType = baseline
simulationType = recommended

engine = SUMO
```

Relasi:

```text
TrafficState 1 ─────── N Simulation

Recommendation 1 ──── N Simulation
```

`recommendationId` dapat bernilai `NULL` untuk simulation baseline.

---

## 2.18 `simulationMetrics`

Menyimpan hasil evaluasi SUMO.

Ini yang nantinya dipakai untuk membandingkan:

```text
Before
vs
After recommendation
```

| Column         | Type               | Constraint            | Description |
| -------------- | ------------------ | --------------------- | ----------- |
| `id`           | `bigserial`        | PK                    | ID          |
| `simulationId` | `bigint`           | FK → `simulations.id` | Simulasi    |
| `metricName`   | `varchar(50)`      | NOT NULL              | Nama metric |
| `metricValue`  | `double precision` | NOT NULL              | Nilai       |
| `unit`         | `varchar(30)`      | NULL                  | Satuan      |
| `createdAt`    | `timestamptz`      | NOT NULL              | Waktu       |

Metric:

```text
averageDelaySeconds
averageQueueLength
throughputVehicles
averageWaitingTimeSeconds
emissionGrams
```

Relasi:

```text
Simulation 1 ─────── N SimulationMetric
```

---

## 2.19 `cctvHistory`

Untuk halaman **History CCTV**.

Data history sebenarnya berasal dari `cvProcessingJobs`. Karena itu tabel ini **tidak menyimpan ulang detail proses**, tetapi hanya menjadi referensi history terhadap video dan processing job.

| Column            | Type          | Constraint                 | Description   |
| ----------------- | ------------- | -------------------------- | ------------- |
| `id`              | `bigserial`   | PK                         | ID            |
| `processingJobId` | `bigint`      | FK → `cvProcessingJobs.id` | CV job        |
| `createdAt`       | `timestamptz` | NOT NULL                   | Waktu history |

Relasi:

```text
CameraVideo
     │
     ▼
CvProcessingJob
     │
     ▼
CctvHistory
```

Informasi kamera dan video tidak perlu diduplikasi di `cctvHistory`, karena dapat diperoleh melalui:

```text
cctvHistory.processingJobId
        ↓
cvProcessingJobs.videoId
        ↓
cameraVideos.cameraId
        ↓
cameras
```

Dengan demikian tidak ada data `cameraId`, `videoId`, dan `processingJobId` yang redundant di history.

---

## 2.20 `systemLogs`

Menyimpan log aktivitas sistem.

| Column           | Type           | Constraint                    | Description     |
| ---------------- | -------------- | ----------------------------- | --------------- |
| `id`             | `bigserial`    | PK                            | ID log          |
| `userId`         | `bigint`       | FK → `users.id`, NULL         | User terkait    |
| `intersectionId` | `bigint`       | FK → `intersections.id`, NULL | Simpang terkait |
| `level`          | `varchar(20)`  | NOT NULL                      | Level log       |
| `action`         | `varchar(100)` | NOT NULL                      | Aktivitas       |
| `message`        | `text`         | NOT NULL                      | Pesan log       |
| `createdAt`      | `timestamptz`  | NOT NULL                      | Waktu log       |

Level:

```text
info
warning
error
```

Relasi:

```text
User 1 ─────── N SystemLog

Intersection 1 ─────── N SystemLog
```

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
       └── TrafficLaneMetric
```

Cardinality:

```text
TrafficState 1 ─── N TrafficApproachState

TrafficState 1 ─── N TrafficLaneMetric

Lane 1 ─── N TrafficLaneMetric

Approach 1 ─── N TrafficApproachState
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

# 7. CCTV History Relationship

History CCTV tidak membuat relasi baru yang redundant.

```text
Camera
  │
  ▼
CameraVideo
  │
  ▼
CvProcessingJob
  │
  ▼
CctvHistory
```

Sehingga halaman CCTV dapat mengambil:

```text
camera
video
processing status
processing time
output
```

tanpa menyimpan ulang data tersebut di beberapa tabel.

---

# 8. Full Entity Relationship

```text
User
 │
 ├── UserSetting
 │       │
 │       └── Intersection
 │
 └── SystemLog

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
 │                     │
 │                     └── CctvHistory
 │
 ├── TrafficState
 │     ├── TrafficApproachState
 │     └── TrafficLaneMetric
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
 ├── Simulation
 │     │
 │     └── SimulationMetric
 │
 └── SystemLog
```

---

# 9. Dashboard → Database Mapping

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
| CCTV History          | `cvProcessingJobs` + `cctvHistory`                           |
| Simulation History    | `simulations` + `simulationMetrics`                          |

---

# 10. Data Contract Mapping

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

# 11. Entity Naming Consistency

Database menggunakan nama tabel plural, sedangkan entity/API menggunakan nama singular atau contract tertentu.

Pemetaan yang digunakan:

| Database Table          | Entity / API Concept |
| ----------------------- | -------------------- |
| `users`                 | `User`               |
| `userSettings`          | `UserSetting`        |
| `intersections`         | `Intersection`       |
| `approaches`            | `Approach`           |
| `lanes`                 | `Lane`               |
| `cameras`               | `Camera`             |
| `cameraVideos`          | `CameraVideo`        |
| `cvProcessingJobs`      | `CvProcessingJob`    |
| `trafficStates`         | `TrafficState`       |
| `trafficApproachStates` | `ApproachState`      |
| `trafficLaneMetrics`    | `LaneMetric`         |
| `signalPhases`          | `SignalPhase`        |
| `signalStatuses`        | `SignalStatus`       |
| `forecasts`             | `Forecast`           |
| `forecastPredictions`   | `ForecastPrediction` |
| `recommendations`       | `Recommendation`     |
| `simulations`           | `Simulation`         |
| `simulationMetrics`     | `SimulationMetric`   |
| `cctvHistory`           | `CctvHistory`        |
| `systemLogs`            | `SystemLog`          |

Perbedaan seperti:

```text
trafficApproachStates
        ↓
ApproachState
```

adalah normal karena database table menggunakan bentuk plural, sedangkan entity API menggunakan bentuk singular.

Yang harus dijaga adalah **field contract**, terutama:

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

---

# 12. Contoh TrafficState di Database

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

# 13. Video Storage Architecture

Video **jangan dimasukkan ke PostgreSQL**.

Gunakan:

```text
                ┌──────────────────────┐
                │      Frontend        │
                │      CCTV Page      │
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
videoFormat
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

# 14. Recommended PostgreSQL Index

Karena SmartTwin akan sering mengambil data berdasarkan simpang + waktu, index berikut penting.

```text
trafficStates
    INDEX (intersectionId, windowStart)

trafficApproachStates
    INDEX (trafficStateId, approachId)

trafficLaneMetrics
    INDEX (trafficStateId, laneId, timestamp)

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

cctvHistory
    INDEX (processingJobId, createdAt)

systemLogs
    INDEX (createdAt)
```

---

# 15. Tables yang Benar-benar Wajib untuk MVP

Kalau deadline kalian mepet, **jangan langsung implementasi semua 20 tabel**.

### Phase 1 — sekarang

```text
intersections

approaches

lanes

cameras

cameraVideos

cvProcessingJobs

trafficLaneMetrics

trafficStates

trafficApproachStates
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

# 16. Final Table List

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

---

# 17. Yang Paling Penting untuk Kondisi Kalian Sekarang

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

Dan **Traffic State Builder yang sudah kalian selesaikan tetap menjadi layer yang mengubah `trafficLaneMetrics`/CSV CV → `trafficStates` + `trafficApproachStates`**.

Database ini menjadi persistence layer di antara pipeline/backend dan dashboard.

---

# 18. Important Consistency Rules

Agar implementasi PostgreSQL, FastAPI, dan frontend tidak kembali berbeda-beda, gunakan aturan berikut:

### Entity relationship

```text
Intersection
    ↓
Approach
    ↓
Lane
```

```text
Intersection
    ↓
Camera
    ↓
CameraVideo
    ↓
CvProcessingJob
```

```text
TrafficState
    ↓
TrafficApproachState
```

```text
TrafficState
    ↓
TrafficLaneMetric
```

### Foreign key

Gunakan ID relasional sebagai sumber kebenaran:

```text
intersectionId
approachId
laneId
cameraId
videoId
processingJobId
trafficStateId
forecastId
recommendationId
simulationId
```

### API contract

Jangan ubah field berikut:

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

### Jangan duplikasi data yang bisa ditelusuri melalui FK

Contoh **jangan**:

```text
cameraVideos
 ├── cameraId
 └── intersectionName   ❌
```

Cukup:

```text
cameraVideos
 └── cameraId
       ↓
    cameras
       ↓
 intersectionId
       ↓
 intersections
```

Begitu juga untuk CCTV history:

```text
cctvHistory
 └── processingJobId
       ↓
 cvProcessingJobs
       ↓
 cameraVideos
       ↓
 cameras
       ↓
 intersections
```

Dengan struktur ini, **satu entity hanya punya satu sumber data utama**, sementara backend bebas membentuk response sesuai data contract frontend.

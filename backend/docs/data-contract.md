# SmartTwin Data Contract

Contract ini menjadi **source of truth** untuk data antara:

```text
Computer Vision
      ↓
Backend
      ↓
Forecast
      ↓
Frontend
```

**Nama field di contract harus digunakan apa adanya.**

⚠️ NAMING CONVENTION

Seluruh nama variabel, field API, request, response, schema, dan data contract menggunakan camelCase.

Tidak boleh menggunakan:
- spasi
- snake_case
- kebab-case
- nama field dengan underscore (_)

Contoh:

✅ intersectionId
✅ windowStart
✅ queueLengthVeh
✅ avgSpeedKmh
✅ horizonMinutes


❌ intersection_id
❌ window_start
❌ queue_length_veh
❌ avg_speed_kmh

Nama field harus konsisten dari CV → Backend → Forecast → Frontend.
---

# 1. Traffic State

## 1. Traffic State

| Field            | Type              | Keterangan                   |
| ---------------- | ----------------- | ---------------------------- |
| `intersectionId` | `string`          | ID persimpangan              |
| `windowStart`    | `datetime`        | Awal window observasi        |
| `windowEnd`      | `datetime`        | Akhir window observasi       |
| `approaches`     | `ApproachState[]` | Data traffic tiap pendekatan |

## 2. Approach State

| Field             | Type                             | CV | Forecast | Frontend | Keterangan                           |
| ----------------- | -------------------------------- | -: | -------: | -------: | ------------------------------------ |
| `approach`        | `north \| south \| east \| west` |  ✅ |        ✅ |        ✅ | Arah pendekatan                      |
| `volume`          | `int`                            |  ✅ |        ✅ |        ✅ | Total kendaraan dari `vehicle_count` |
| `carCount`        | `int`                            |  ✅ |        ✅ |        ✅ | Jumlah mobil                         |
| `motorcycleCount` | `int`                            |  ✅ |        ✅ |        ✅ | Jumlah motor                         |
| `busCount`        | `int`                            |  ✅ |        ✅ |        ✅ | Jumlah bus                           |
| `truckCount`      | `int`                            |  ✅ |        ✅ |        ✅ | Jumlah truk                          |
| `queueLengthVeh`  | `int`                            |  ✅ |        ✅ |        ✅ | Jumlah kendaraan dalam antrean       |
| `queueLengthMEst` | `float`                          |  ✅ |        ✅ |        ✅ | Estimasi panjang antrean dalam meter |
| `densityIndex`    | `float`                          |  ✅ |        ✅ |        ✅ | Proxy lane occupancy/kepadatan       |
| `avgSpeedKmh`     | `float \| null`                  | ⚠️ |       ⚠️ |        ✅ | Belum tersedia dari CSV CV           |


> **⚠️ `avgSpeedKmh` boleh `null`.**



---

# 2. Traffic Metric Rules

### `queueLengthVeh`

Jumlah kendaraan yang terdeteksi sebagai antrean.

```text
queueLengthVeh = jumlah kendaraan dalam antrean
```

### `queueLengthMEst`

Estimasi panjang antrean berdasarkan panjang kendaraan.

```text
queueLengthMEst = estimasi panjang antrean dalam meter
```

### `densityIndex`

Index/proxy kepadatan berdasarkan data visual.

**Bukan:**

```text
vehicles/km
```

### `avgSpeedKmh`

Kecepatan rata-rata kendaraan jika tersedia.

```json
{
  "avgSpeedKmh": null
}
```

berarti data speed belum tersedia.

**Jangan:**

```json
{
  "avgSpeedKmh": 0
}
```

karena `0` berarti kendaraan terukur tidak bergerak.

---

# 3. Forecast

## Request

```http
POST /api/forecast
```

```json
{
  "intersectionId": "intersection_01",
  "horizonMinutes": 15
}
```

## Response

| Field             | Type     | Keterangan           |
| ----------------- | -------- | -------------------- |
| `intersectionId` | `string` | ID persimpangan      |
| `horizonMinutes` | `int`    | Durasi prediksi      |
| `model`           | `string` | Model yang digunakan |
| `predictions`     | `array`  | Hasil prediksi       |

Prediction:

| Field                      | Type            | Keterangan                        |
| -------------------------- | --------------- | --------------------------------- |
| `timestamp`                | `datetime`      | Waktu prediksi                    |
| `predictedVehicleCount`    | `float`         | Prediksi jumlah kendaraan         |
| `predictedQueueLengthVeh`  | `float`         | Prediksi jumlah kendaraan antre   |
| `predictedQueueLengthMEst` | `float`         | Prediksi estimasi panjang antrean |
| `predictedDensityIndex`    | `float`         | Prediksi density index            |
| `predictedSpeedKmh`        | `float \| null` | Prediksi speed jika tersedia      |

---

# 4. Signal & Recommendation

## Signal Status

```http
GET /api/signal/status
POST /api/signal/status
```

| Field                | Type       | Keterangan      |
| -------------------- | ---------- | --------------- |
| `intersectionId`    | `string`   | ID persimpangan |
| `timestamp`          | `datetime` | Waktu           |
| `currentPhase`      | `string`   | Fase aktif      |
| `phaseName`         | `string`   | Nama fase       |
| `remainingSeconds`  | `int`      | Sisa waktu      |
| `cycleTimeSeconds` | `int`      | Waktu siklus    |
| `source`             | `string`   | Sumber data     |

## Recommendation

```http
POST /api/recommendation
```

| Field                              | Type       | Keterangan                 |
| ---------------------------------- | ---------- | -------------------------- |
| `intersectionId`                  | `string`   | ID persimpangan            |
| `timestamp`                        | `datetime` | Waktu                      |
| `recommendedPhase`                | `string`   | Fase rekomendasi           |
| `recommendedGreenSeconds`        | `int`      | Green time rekomendasi     |
| `currentGreenSeconds`            | `int`      | Green time saat ini        |
| `expectedDelayReductionPercent` | `float`    | Estimasi pengurangan delay |
| `confidence`                       | `float`    | Confidence 0–1             |
| `reason`                           | `string`   | Alasan rekomendasi         |
| `source`                           | `string`   | Sumber recommendation      |

---

# 5. Frontend Mapping

**Frontend tidak membuat nama variabel baru.**

| Backend/API       | Frontend gunakan  |
| ----------------- | ----------------- |
| `volume`          | `volume`          |
| `carCount`        | `carCount`        |
| `motorcycleCount` | `motorcycleCount` |
| `busCount`        | `busCount`        |
| `truckCount`      | `truckCount`      |
| `queueLengthVeh`  | `queueLengthVeh`  |
| `queueLengthMEst` | `queueLengthMEst` |
| `densityIndex`    | `densityIndex`    |
| `avgSpeedKmh`     | `avgSpeedKmh`     |


### Handling `null`

```ts
avgSpeedKmh === null
  ? "N/A"
  : `${avgSpeedKmh.toFixed(1)} km/h`
```

**Tidak boleh:**

```ts
avgSpeedKmh || 0
```

---

# 6. Core Rule

```text
CV
 ↓
Backend
 ↓
Forecast
 ↓
Frontend

gunakan nama field yang sama.
```

Jika data belum tersedia:

```text
null
```

Jika data dummy:

```text
source: "mock"
```

Jangan mengarang nilai production.

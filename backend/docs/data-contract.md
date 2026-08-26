# SmartTwin Data Contract

> **Diperbarui 27 Agustus 2026** — sempat dihapus keliru dengan alasan "duplikat/kontradiktif dengan `docs/data-contract.md`", lalu dikembalikan setelah dicek: dua dokumen ini beda fungsi, bukan duplikat.
> - `docs/data-contract.md` (root) = kontrak SEMANTIK lintas modul — field apa saja yang ada, artinya apa, ditulis gaya Pydantic/Python idiomatik (snake_case). Itu tetap sumber kebenaran untuk "field apa yang ada dan kenapa".
> - **Dokumen INI** = konvensi PENAMAAN yang benar-benar dipakai kode (camelCase, dikonfirmasi langsung ke `backend/app/schemas/traffic.py` — atributnya literally `queueLengthVeh`, bukan `queue_length_veh` dengan alias) plus bentuk request/response endpoint yang sebenarnya. Bagian endpoint di bawah sempat ketinggalan (path masih pakai `/api/...` yang sudah tidak dipakai, field baru dari item 1.7 belum ada) — sudah disegarkan cocok kode per 27 Agustus.
>
> Kalau dua dokumen ini kelihatan beda soal ejaan field (`queue_length_veh` vs `queueLengthVeh`), itu bukan konflik — root itu spek konseptual, dokumen ini itu ejaan literal yang dipakai di kode.

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

**Diperbarui 27 Agustus 2026 — bentuk sebelumnya (`intersectionId`+`horizonMinutes`, response `predictions[]` dengan prefix `predicted*`) sudah tidak dipakai kode. Dua endpoint aktif sekarang, dua-duanya butuh 12 timestep histori (bukan `horizonMinutes`):**

## 3.1 Forecast agregat (satu simpang, bukan per-lengan)

```http
POST /api/forecast
```

Request — minimal 12 baris (`backend/app/api/routes/forecast.py::ForecastRequest`):

```json
{
  "records": [
    {
      "timestamp": "2026-08-15T17:19:15",
      "vehicleCount": 10,
      "queueLengthVeh": 0,
      "queueLengthMEst": 0,
      "densityIndex": 0.171212
    }
  ]
}
```

Response (`ForecastService.predict_dataframe()`):

| Field      | Type     | Keterangan                                             |
| ---------- | -------- | -------------------------------------------------------- |
| `model`    | `object` | `{type, inputTimesteps, outputTimesteps, ...}`           |
| `input`    | `object` | Ringkasan input yang dipakai                             |
| `forecast` | `array`  | 12 langkah, tiap elemen: `timestamp`, `vehicleCount`, `queueLengthVeh`, `queueLengthMEst`, `densityIndex`, `secondsAhead` |

## 3.2 Forecast per-approach (4 lengan sekaligus — dipakai Decision Engine)

```http
POST /api/forecast/approaches
```

Request — minimal 12 `TrafficState` lengkap berinterval 5 detik, tiap elemen punya `timestamp` + `approaches[]` (4 lengan, tiap lengan: `approach`, `vehicleCount`, `queueLengthVeh`, `queueLengthMEst`, `densityIndex`).

Response (`PerApproachForecastService.predict_records()`, fallback ke alokasi model agregat kalau model per-approach gagal — lihat `forecastSource`/`fallbackUsed`):

| Field                | Type      | Keterangan                                                        |
| --------------------- | --------- | -------------------------------------------------------------------- |
| `model`                | `object`  | `{name, mode, inputSteps, outputSteps, intervalSeconds}`           |
| `input`                | `object`  | Ringkasan histori yang dipakai                                     |
| `approachForecasts`    | `array`   | 12 horizon (langkah 5 detik), tiap horizon punya `secondsAhead` + `approaches[]` (4 lengan: `approach`, `vehicleCount`, `queueLengthVeh`, `queueLengthMEst`, `densityIndex`) |
| `forecastSource`       | `string`  | `"lstm-per-approach"` atau `"aggregate-recent-share-fallback"`     |
| `fallbackUsed`         | `boolean` | `true` kalau jatuh ke model agregat                                 |

---

# 4. Signal & Recommendation

**Diperbarui 27 Agustus 2026 — path sebelumnya (`/api/signal/status`, `/api/recommendation`) sudah tidak dipakai (dua-duanya TANPA prefix `/api`), dan skema di bawah belum punya field yang ditambah item 1.7 (siklus 4-lengan live). Sudah disegarkan cocok `backend/app/schemas/signal.py` & `backend/app/schemas/recommendation.py`.**

## Signal Status

```http
GET /signal/status
POST /signal/status
```

| Field                | Type       | Keterangan      |
| -------------------- | ---------- | --------------- |
| `intersectionId`    | `string`   | ID persimpangan |
| `timestamp`          | `datetime` | Waktu           |
| `currentPhase`      | `string`   | Lengan yang aktif hijau sekarang (`west`/`south`/`east`/`north`) |
| `phaseName`         | `string`   | Nama fase       |
| `remainingSeconds`  | `int`      | Sisa waktu fase aktif (hijau + kuning digabung) |
| `cycleTimeSeconds` | `int`      | Waktu siklus    |
| `phases`             | `object`   | **[BARU item 1.7]** map `approach -> SignalPhase` (`phaseId`, `state`, `durationSeconds`, `remainingSeconds`) |
| `nextPhase`          | `string`   | **[BARU item 1.7]** lengan berikutnya dalam rotasi |
| `nextPhaseName`      | `string`   | **[BARU item 1.7]** nama fase berikutnya |
| `source`             | `string`   | Sumber data     |

## Recommendation

```http
POST /recommendation
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
| `source`                           | `string`   | `"rule-based"` / `"rule-based+forecast"` (item 2.4) / `"scenario-generator"` (batch, item 1.5) |
| `cyclePlan`                         | `object \| null` | **[BARU item 1.7]** `{phases: [{approach, greenSeconds, demandScore}, ...4 lengan], cycleLengthSeconds, currentPhase, source}` — durasi hijau ke-4 lengan sekaligus, sumber sama dengan yang dipakai `/signal/status` |

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

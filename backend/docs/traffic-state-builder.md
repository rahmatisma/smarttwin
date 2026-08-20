# Traffic State Builder

Traffic State Builder adalah pipeline yang mengubah data traffic hasil Computer Vision (YOLO + ByteTrack) menjadi **TrafficState** yang dapat digunakan oleh Backend, SUMO, dan Dashboard SmartTwin.

## 1. Alur

```text
YOLO + ByteTrack
       ↓
CV Traffic Data
       ↓
Traffic State Builder
       ↓
TrafficState
       ↓
Backend API
       ↓
Frontend / SUMO
```

## 2. Input

Input utama:

```text
cv/output/smarttwin_traffic_data.csv
```

Format data saat ini adalah **per timestamp + approach + lane**.

Kolom utama:

| Kolom                | Fungsi                                |
| -------------------- | ------------------------------------- |
| `timestamp`          | Waktu pengamatan                      |
| `intersection_id`    | Identitas simpang                     |
| `approach`           | Lengan simpang: north/south/east/west |
| `lane_id`            | Identitas lajur                       |
| `vehicle_count`      | Kendaraan yang memotong counting line |
| `car_count`          | Jumlah mobil                          |
| `motorcycle_count`   | Jumlah motor                          |
| `bus_count`          | Jumlah bus                            |
| `truck_count`        | Jumlah truk                           |
| `queue_length_veh`   | Jumlah kendaraan dalam antrean        |
| `queue_length_m_est` | Estimasi panjang antrean              |
| `density_index`      | Proxy kepadatan/occupancy lajur       |

## 3. Tugas Traffic State Builder

Builder melakukan:

1. Membaca data traffic dari CSV.
2. Mengelompokkan data berdasarkan **time window**.
3. Mengelompokkan data berdasarkan **approach**.
4. Menggabungkan data dari beberapa lane dalam satu approach.
5. Menghasilkan `volume`.
6. Menghasilkan `queue_length_veh`.
7. Menghasilkan `queue_length_m_est`.
8. Menghasilkan `density_index`.
9. Mengisi `avg_speed_kmh` sebagai `None` karena speed belum tersedia.
10. Menghasilkan object `TrafficState` sesuai data contract.

## 4. Output

Output mengikuti contract:

```text
TrafficState
├── intersectionId
├── windowStart
├── windowEnd
└── approaches
    ├── north
    ├── south
    ├── east
    └── west
```

Setiap `ApproachState` memiliki:

```text
approach
volume
queueLengthVeh
queueLengthMEst
densityIndex
avgSpeedKmh
```

Contoh konsep:

```json
{
  "intersectionId": "simpang4-pingit",
  "windowStart": "2026-08-15T16:30:12",
  "windowEnd": "2026-08-15T16:30:17",
  "approaches": [
    {
      "approach": "south",
      "volume": 10,
      "queueLengthVeh": 5,
      "queueLengthMEst": 12.5,
      "densityIndex": 24.3,
      "avgSpeedKmh": null
    }
  ]
}
```

## 5. Tahapan Implementasi

### Tahap 1 — Load Data

Membaca CSV dan melakukan parsing:

```text
CSV
 ↓
timestamp
intersection_id
approach
lane_id
metrics
```

### Tahap 2 — Time Window

Traffic State Builder menggunakan window observasi sebesar **5 detik**.

Contoh:

```text
16:30:12 ── 16:30:17
      ↓
TrafficState #1

16:30:17 ── 16:30:22
      ↓
TrafficState #2
```

Durasi window harus ditentukan sebagai konfigurasi, bukan hardcoded di banyak tempat.

### Tahap 3 — Aggregate Lane → Approach

Contoh:

```text
south
├── lane_1
├── lane_2
└── lane_3
```

menjadi:

```text
south
└── ApproachState
```

### Tahap 4 — Hitung Metrik Approach

Metrik per-lane digabungkan menjadi metrik per-approach.

* `volume` → total kendaraan yang tercatat crossing.
* `queue_length_veh` → nilai antrean sesuai hasil CV.
* `queue_length_m_est` → estimasi panjang antrean.
* `density_index` → agregasi proxy occupancy/density.
* `avg_speed_kmh` → `None` sampai sumber speed tersedia.

### Tahap 5 — Build TrafficState

Hasil agregasi dimasukkan ke schema:

```text
TrafficState
        ↓
ApproachState[]
```

### Tahap 6 — Validasi

Validasi minimal:

* Semua approach menggunakan nilai yang valid.
* Tidak ada volume negatif.
* Queue tidak negatif.
* `density_index` tidak negatif.
* Timestamp terurut.
* Tidak terjadi double counting antar-lane.
* `avg_speed_kmh` tetap `None` jika speed belum tersedia.

### Tahap 7 — Integrasi Backend

```text
TrafficStateBuilder
        ↓
TrafficService
        ↓
GET /api/traffic/latest
        ↓
Frontend
```

## 6. Catatan Penting

### Volume ≠ kendaraan yang terlihat

`volume` hanya merepresentasikan kendaraan yang **memotong counting line**, bukan seluruh kendaraan yang terlihat pada frame.

### Queue ≠ Volume

`queue_length_veh` merupakan jumlah kendaraan yang sedang mengantre dan tidak boleh disamakan dengan volume.

### Density bukan kendaraan/km

`density_index` saat ini merupakan **proxy lane occupancy** dan belum merupakan kepadatan fisik dalam kendaraan/km.

### Speed belum tersedia

Jika belum ada data kecepatan:

```json
"avgSpeedKmh": null
```

Jangan menggunakan `0.0` sebagai placeholder.

## 7. File Utama

```text
smarttwin/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │   └── routes/
│   │   │       └── traffic.py
│   │   │
│   │   ├── schemas/
│   │   │   └── traffic.py
│   │   │
│   │   ├── services/
│   │   │   └── traffic_service.py
│   │   │
│   │   ├── pipeline/
│   │   │   └── traffic_state_builder.py      ← 1
│   │   │
│   │   └── simulation/
│   │       └── sumo/
│   │           ├── traffic_state_adapter.py  ← 2
│   │           └── sumo_controller.py        ← 3
│   │
│   └── tests/
│       ├── test_traffic_state_builder.py      ← 4
│       └── test_sumo_adapter.py               ← 5
│
├── cv/
│   ├── vehicle_counter.py
│   └── output/
│       └── smarttwin_traffic_data.csv
│
└── simulation/
    └── sumo/
        ├── network/
        ├── routes/
        ├── configs/
        └── outputs/
```

## 8. Target Akhir

Traffic State Builder dianggap selesai apabila pipeline berikut berjalan:

```text
CV CSV
  ↓
Time Window
  ↓
Lane Aggregation
  ↓
Approach Aggregation
  ↓
TrafficState
  ↓
Backend API
  ↓
Dashboard / SUMO
```

**Prinsip utama:** Traffic State Builder hanya bertanggung jawab mengubah data CV menjadi state lalu lintas sesuai contract. Logika API, frontend, SUMO, forecasting, dan recommendation tetap berada di layer masing-masing.

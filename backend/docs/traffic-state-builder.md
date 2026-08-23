
# Traffic State Builder

Traffic State Builder mengubah data traffic dari Computer Vision (YOLO + ByteTrack) menjadi `TrafficState` yang digunakan oleh Backend, SUMO, dan Dashboard SmartTwin.

## 1. Alur

```text
CV Traffic Data
      ↓
Traffic State Builder
      ↓
BuiltTrafficState
      ↓
TrafficState
      ↓
Backend API
   ↓       ↓
Frontend   SUMO
````

## 2. Input

Sumber data utama:

```text
cv/output/smarttwin_traffic_data.csv
```

Data berada pada level:

```text
timestamp + intersection + approach + lane
```

Kolom utama:

| Kolom                | Keterangan                            |
| -------------------- | ------------------------------------- |
| `timestamp`          | Waktu pengamatan                      |
| `intersection_id`    | ID simpang                            |
| `approach`           | `north`, `south`, `east`, `west`      |
| `lane_id`            | ID lajur                              |
| `vehicle_count`      | Kendaraan yang melewati counting line |
| `car_count`          | Jumlah mobil                          |
| `motorcycle_count`   | Jumlah motor                          |
| `bus_count`          | Jumlah bus                            |
| `truck_count`        | Jumlah truk                           |
| `queue_length_veh`   | Jumlah kendaraan dalam antrean        |
| `queue_length_m_est` | Estimasi panjang antrean              |
| `density_index`      | Proxy kepadatan/occupancy             |

## 3. Tugas Builder

Traffic State Builder bertugas:

1. Membaca data traffic.
2. Parsing dan mengurutkan timestamp.
3. Membentuk time window **5 detik**.
4. Menggabungkan data beberapa lane menjadi satu approach.
5. Menghitung `volume`.
6. Mengagregasikan `queueLengthVeh`.
7. Mengagregasikan `queueLengthMEst`.
8. Mengagregasikan `densityIndex`.
9. Menghitung `carCount`, `motorcycleCount`, `busCount`, dan `truckCount`.
10. Menghasilkan `BuiltTrafficState` sesuai contract backend.

## 4. Aggregation

```text
Lane
 │
 ├── lane_1
 ├── lane_2
 └── lane_3
       ↓
   Approach
       ↓
 ApproachState
```

Aturan utama:

| Metric            | Aggregation                      |
| ----------------- | -------------------------------- |
| `volume`          | SUM `vehicle_count`              |
| `carCount`        | SUM `car_count`                  |
| `motorcycleCount` | SUM `motorcycle_count`           |
| `busCount`        | SUM `bus_count`                  |
| `truckCount`      | SUM `truck_count`                |
| `queueLengthVeh`  | SUM antar-lane                   |
| `queueLengthMEst` | SUM antar-lane                   |
| `densityIndex`    | Rata-rata antar-lane             |
| `avgSpeedKmh`     | `None` jika speed belum tersedia |

## 5. Time Window

Window default:

```text
5 detik
```

Contoh:

```text
16:30:12 ───── 16:30:17
       ↓
 TrafficState #1

16:30:17 ───── 16:30:22
       ↓
 TrafficState #2
```

Window harus dikonfigurasi melalui builder dan tidak di-hardcode di banyak tempat.

## 6. Output

Struktur utama:

```text
BuiltTrafficState
├── trafficStateId
├── intersectionId
├── windowStart
├── windowEnd
└── approaches
    ├── north
    ├── south
    ├── east
    └── west
```

Setiap approach memiliki metric:

```text
approach
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

Contoh:

```json
{
  "intersectionId": "simpang4-pingit",
  "windowStart": "2026-08-15T16:30:12",
  "windowEnd": "2026-08-15T16:30:17",
  "approaches": [
    {
      "approach": "south",
      "volume": 10,
      "carCount": 3,
      "motorcycleCount": 6,
      "busCount": 1,
      "truckCount": 0,
      "queueLengthVeh": 5,
      "queueLengthMEst": 12.5,
      "densityIndex": 24.3,
      "avgSpeedKmh": null
    }
  ]
}
```

## 7. Integrasi

```text
CV
 ↓
TrafficStateBuilder
 ↓
BuiltTrafficState
 ├──→ Traffic Service
 │       ↓
 │    Backend API
 │       ↓
 │    Frontend
 │
 └──→ SumoTrafficStateAdapter
         ↓
       SUMO
```

`TrafficStateBuilder` hanya bertanggung jawab terhadap pembentukan traffic state.

Logic SUMO, API, frontend, forecasting, dan recommendation berada di layer masing-masing.

## 8. Validasi

Builder memastikan:

* Approach valid: `north`, `south`, `east`, `west`
* Tidak ada nilai metric negatif.
* Timestamp terurut.
* Tidak terjadi double counting antar-lane.
* `queueLengthVeh` merupakan agregasi queue per-lane.
* `queueLengthMEst` merupakan agregasi queue length per-lane.
* `densityIndex` merupakan rata-rata antar-lane.
* `avgSpeedKmh = None` jika data speed belum tersedia.

## 9. File Utama

```text
backend/
└── app/
    ├── pipeline/
    │   └── traffic_state_builder.py
    │
    ├── schemas/
    │   └── traffic.py
    │
    ├── services/
    │   └── traffic_service.py
    │
    └── simulation/
        └── sumo/
            ├── traffic_state_adapter.py
            └── sumo_controller.py
```

Input CV:

```text
cv/
└── output/
    └── smarttwin_traffic_data.csv
```

SUMO network:

```text
simulation/
└── network/
    └── simpang4_pingit.sumocfg
```

## 10. Testing

Test khusus Traffic State Builder:

```bash
python -m pytest tests/test_traffic_state_builder.py -q
```

Test Traffic Service:

```bash
python -m pytest tests/test_traffic_service.py -q
```

Test SUMO Adapter:

```bash
python -m pytest tests/test_sumo_adapter.py -q
```

Seluruh backend:

```bash
python -m pytest -q
```

## Prinsip Utama

```text
CV Data
   ↓
Time Window
   ↓
Lane Aggregation
   ↓
Approach Aggregation
   ↓
BuiltTrafficState
   ↓
Backend / SUMO / Frontend
```

Traffic State Builder **tidak mengatur simulasi SUMO atau tampilan frontend**. Builder hanya menghasilkan traffic state yang menjadi sumber data bagi layer berikutnya.

```

## Note — Waktu dan Data

- Data CV memiliki timestamp berdasarkan waktu pengamatan video/CCTV.
- Traffic State Builder menggunakan **time window 5 detik** untuk mengagregasikan data CV.
- Satu `TrafficState` merepresentasikan kondisi lalu lintas pada **satu window 5 detik**, bukan kondisi satu frame.
- `windowStart` dan `windowEnd` menunjukkan periode data yang digunakan untuk membentuk state.
- Data yang masuk ke builder harus memiliki timestamp yang valid dan terurut.
- Jika tidak ada data pada suatu window, builder tidak boleh menganggapnya sebagai `0` tanpa aturan preprocessing yang jelas.
- `volume` merupakan jumlah kendaraan yang tercatat oleh CV pada window tersebut, bukan jumlah kendaraan yang sedang berada di jalan.
- `queueLengthVeh` merepresentasikan kendaraan yang sedang mengantre pada window tersebut.
- Data CV merupakan **observasi**, sedangkan SUMO merupakan **representasi/simulasi** dari kondisi tersebut.
- Untuk mode realtime, setiap `TrafficState` baru dapat digunakan sebagai input/update kondisi SUMO tanpa harus menunggu simulasi selesai selama beberapa menit.
- `durationSeconds` pada endpoint SUMO menentukan berapa lama proses simulasi berjalan, **bukan durasi data CV**.

**Catatan penting:** aku sengaja menghapus checklist `24 passed` dari README. Angka jumlah test itu gampang berubah ketika kalian nambah test, jadi lebih aman README menjelaskan **command testing**, bukan mengunci jumlah test saat ini.
```

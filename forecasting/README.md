# SmartTwin — Traffic Forecasting

Modul forecasting untuk project **SmartTwin**.

Modul ini bertujuan membangun model **Long Short-Term Memory (LSTM)** untuk memprediksi kondisi lalu lintas berdasarkan data time-series.

Hasil forecasting nantinya digunakan sebagai salah satu input untuk:

```text
Traffic Forecast
      ↓
Scenario Generator
      ↓
SUMO
      ↓
Performance Analysis
      ↓
PPO
      ↓
Signal Timing Recommendation
```

Prinsip utama modul:

```text
DATA → PREDICTION → SIMULATION → DECISION
```

LSTM bukan pengambil keputusan lampu lalu lintas.

```text
LSTM = Forecasting
PPO  = Decision Making
SUMO = Traffic Simulation
YOLO = Traffic State Extraction
```

---

# 1. Tujuan Modul

Tujuan modul forecasting bukan hanya mendapatkan nilai error sekecil mungkin.

Model harus:

1. mempelajari hubungan temporal lalu lintas;
2. mampu memprediksi kondisi lalu lintas beberapa timestep ke depan;
3. menghasilkan traffic forecast yang masuk akal;
4. dapat diterjemahkan menjadi traffic state;
5. dapat digunakan untuk scenario generation;
6. dapat digunakan sebagai input simulasi SUMO;
7. pada tahap akhir dapat dikombinasikan dengan traffic state dari YOLO.

Pipeline target:

```text
YOLO / Traffic Dataset
        ↓
Traffic State
        ↓
      LSTM
        ↓
Traffic Forecast
        ↓
Scenario Generator
        ↓
      SUMO
        ↓
Performance Analysis
        ↓
       PPO
        ↓
Signal Timing Recommendation
```

---

# 2. Status Pengembangan

## Dataset dan Pipeline

* [x] Repository SmartTwin tersedia
* [x] Folder forecasting ditentukan
* [x] Dataset TMU dipelajari
* [x] Dataset PEMS04 dipelajari
* [x] Dataset Brisbane traffic intersection dipelajari
* [x] PEMS04 preprocessing
* [x] PEMS04 sequence generation
* [x] PEMS04 LSTM training
* [x] PEMS04 evaluation
* [x] PEMS04 prediction
* [x] Brisbane real-time collector
* [x] Brisbane data disimpan ke MariaDB
* [ ] Brisbane dataset preprocessing
* [ ] Brisbane LSTM training
* [ ] Brisbane evaluation
* [ ] Brisbane prediction
* [ ] Eksperimen PEMS04 sensor 1–20
* [ ] Perbandingan PEMS04 sensor 1–10 vs 1–20
* [ ] Eksperimen tambahan sensor jika diperlukan

## Integrasi SmartTwin

* [ ] Feature mapping antar dataset
* [ ] Penyesuaian forecast dengan traffic state YOLO
* [ ] Integrasi Traffic State Builder
* [ ] Integrasi scenario generator
* [ ] Integrasi SUMO
* [ ] Integrasi forecast dengan demand/scenario simulation
* [ ] Integrasi PPO
* [ ] Signal timing recommendation

---

# 3. Dataset yang Digunakan

Forecasting SmartTwin menggunakan **tiga jenis dataset** dengan tujuan yang berbeda.

```text
                 SMARTTWIN FORECASTING
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
         TMU           PEMS04        Brisbane
      Baseline       Multi-sensor    Intersection
          │              │              │
          ↓              ↓              ↓
       Single/       307 sensors      Traffic
       aggregated     × 3 feature     controller
       traffic                          data
          │              │              │
          └──────────────┼──────────────┘
                         ↓
                    LSTM Forecast
```

Ketiga dataset **tidak langsung digabung menjadi satu dataset**.

Masing-masing digunakan untuk menjawab pertanyaan eksperimen yang berbeda.

---

# 4. Dataset 1 — TMU

## Fungsi

TMU digunakan sebagai **baseline awal** untuk memastikan pipeline forecasting bekerja dengan baik pada data time-series lalu lintas.

Dataset:

```text
TMU Site 9329/1 on A174 eastbound
between A19 and A1044
```

Interval data:

```text
15 menit
```

Kolom penting antara lain:

```text
Local Date
Local Time
Day Type ID
Total Carriageway Flow
Total Flow vehicles less than 5.2m
Total Flow vehicles 5.21m - 6.6m
Total Flow vehicles 6.61m - 11.6m
Total Flow vehicles above 11.6m
Speed Value
Quality Index
Network Link Id
NTIS Model Version
```

### Karakteristik TMU

TMU memiliki karakteristik:

* data time-series;
* interval 15 menit;
* flow lalu lintas;
* speed;
* klasifikasi kendaraan berdasarkan ukuran;
* lebih sederhana dibandingkan data sensor intersection.

TMU cocok untuk menjawab:

> Apakah pola temporal lalu lintas dapat dipelajari oleh LSTM?

TMU **bukan representasi final traffic state SmartTwin**.

---

# 5. Dataset 2 — PEMS04

PEMS04 digunakan sebagai dataset **multi-sensor traffic forecasting**.

Dataset memiliki struktur:

```text
(time, sensor, feature)
```

Hasil inspeksi dataset:

```text
Shape:
(16992, 307, 3)
```

Artinya:

```text
16992 timestep
307 sensor
3 feature
```

Feature:

```text
1. Flow
2. Occupancy
3. Speed
```

Dengan demikian dataset menyediakan traffic information dari banyak sensor sekaligus.

---

# 6. Mengapa PEMS04 Digunakan

PEMS04 digunakan karena lebih sesuai untuk eksperimen forecasting berbasis banyak sensor.

Berbeda dengan TMU yang lebih sederhana, PEMS04 memungkinkan eksperimen:

```text
Jumlah sensor
      ↓
10 sensor
      ↓
20 sensor
      ↓
30 sensor
      ↓
...
```

Tujuan eksperimen:

> Apakah penambahan informasi dari lebih banyak sensor meningkatkan kemampuan LSTM dalam memprediksi kondisi lalu lintas?

Karena itu PEMS04 digunakan untuk **eksperimen multi-sensor**.

---

# 7. Konfigurasi PEMS04 Saat Ini

Eksperimen pertama menggunakan:

```text
Sensor       : 1–10
Jumlah sensor: 10

Feature:
- Flow
- Occupancy
- Speed

Jumlah feature:
3
```

Input LSTM:

```text
10 sensor × 3 feature
= 30 nilai per timestep
```

Sequence:

```text
15 timestep
```

Forecast horizon:

```text
1 timestep
```

Data memiliki struktur:

```text
X:
(samples, 15, 10, 3)

y:
(samples, 10, 3)
```

---

# 8. Mengapa Occupancy dan Speed Tetap Digunakan

Walaupun pada sistem final YOLO juga diharapkan menghasilkan informasi seperti speed dan occupancy, kedua feature tersebut tetap digunakan dalam model.

Alasannya:

1. memungkinkan model memanfaatkan hubungan antar-variabel;
2. memberikan informasi tambahan selain flow;
3. memungkinkan evaluasi performa model terhadap beberapa traffic indicator;
4. model tidak perlu dilatih ulang jika nantinya speed atau occupancy diperlukan dalam forecasting;
5. memungkinkan perbandingan kontribusi masing-masing feature.

Dengan demikian input utama PEMS04:

```text
Flow
Occupancy
Speed
```

Bukan hanya:

```text
Flow
```

---

# 9. Sequence Length PEMS04

Konfigurasi saat ini:

```text
sequence_length = 15
```

Artinya model melihat:

```text
15 timestep sebelumnya
```

sebelum menghasilkan prediksi timestep berikutnya.

Jika interval dataset adalah 5 menit, maka:

```text
15 × 5 menit
= 75 menit history
```

Catatan:

**Makna waktu sebenarnya bergantung pada interval asli dataset.**

Karena itu sequence length tidak boleh diterjemahkan menjadi durasi tertentu tanpa mengetahui interval dataset.

Yang kita samakan untuk eksperimen adalah:

```text
15 timestep
```

bukan selalu:

```text
15 menit
```

---

# 10. Eksperimen Sensor PEMS04

Eksperimen pertama:

```text
Sensor 1–10
```

Setelah baseline selesai, eksperimen berikutnya:

```text
Sensor 1–20
```

Model 1–20 **dilatih ulang dari awal**.

Bukan:

```text
Model 1–10
      ↓
tambahkan sensor 11–20
```

Tetapi:

```text
PEMS04
   ↓
ambil sensor 1–20
   ↓
preprocessing baru
   ↓
training model baru
```

Perubahan input:

```text
10 sensor × 3 feature = 30 input
```

menjadi:

```text
20 sensor × 3 feature = 60 input
```

Tujuan:

```text
Bandingkan

Sensor 1–10
      VS
Sensor 1–20
```

berdasarkan:

```text
MAE
RMSE
MAPE
R²
```

Jika performa meningkat, penambahan sensor memberikan manfaat.

Jika performa tidak meningkat, maka lebih banyak sensor tidak otomatis berarti model lebih baik.

---

# 11. Mengapa Tidak Langsung Menggunakan Semua 307 Sensor

PEMS04 memiliki:

```text
307 sensor
```

Namun tidak langsung digunakan seluruhnya.

Alasannya:

### 1. Kompleksitas model meningkat

Semakin banyak sensor:

```text
input dimension ↑
parameter ↑
memory usage ↑
training complexity ↑
```

### 2. Tidak semua sensor harus memberikan informasi tambahan

Sensor yang terlalu banyak dapat membawa informasi yang:

* redundant;
* sangat berkorelasi;
* kurang relevan terhadap target;
* bahkan dapat menambah noise.

### 3. Eksperimen harus dapat dijelaskan

Lebih mudah menjelaskan:

```text
10 sensor → 20 sensor → 30 sensor
```

daripada langsung:

```text
307 sensor
```

tanpa mengetahui apakah penambahan tersebut benar-benar memberikan manfaat.

### 4. Sesuai kebutuhan SmartTwin

SmartTwin pada akhirnya tidak harus menggunakan seluruh sensor publik.

Tujuan penelitian adalah menemukan konfigurasi yang cukup informatif tetapi tetap efisien.

---

# 12. Dataset 3 — Brisbane Traffic Intersection

Dataset Brisbane digunakan untuk mendekatkan forecasting terhadap kondisi **traffic intersection**.

Dataset:

```text
traffic-data-at-intersection
```

Data berasal dari traffic controller/intersection.

Salah satu intersection yang digunakan:

```text
TSC = 470
```

Data memiliki informasi terkait:

```text
lane
ds1
ds2
ds3
ds4
ct
link_plan
```

Data tersebut kemudian diproses menjadi traffic observation.

---

# 13. Brisbane Real-Time Collector

Data Brisbane dikumpulkan secara berkala menggunakan collector Python.

Konfigurasi:

```text
TSC:
470

Interval:
60 detik

Database:
MariaDB

Database name:
smarttwin_traffic

Table:
brisbane_traffic
```

Collector berjalan sebagai proses 24/7 pada server.

Data disimpan ke:

```text
brisbane_traffic
```

dengan feature seperti:

```text
recorded
tsc
lane_count
vehicle_count
reconstituted_flow
density_proxy
queue_proxy
cycle_time
link_plan
```

---

# 14. Catatan Penting tentang Brisbane

Brisbane tidak boleh dianggap memiliki physical traffic density hanya karena terdapat nilai:

```text
density_proxy
```

Feature tersebut merupakan **proxy**, bukan physical density aktual.

Demikian pula:

```text
queue_proxy
```

merupakan hasil pendekatan dari data yang tersedia.

Dokumentasi harus selalu mempertahankan istilah:

```text
density_proxy
queue_proxy
```

dan tidak mengklaimnya sebagai pengukuran fisik jika data pendukung tidak tersedia.

---

# 15. Mengapa Brisbane Dikumpulkan Secara Real-Time

PEMS04 dan TMU merupakan dataset historis.

Brisbane memberikan kesempatan untuk mendapatkan data yang terus bertambah.

Pipeline:

```text
Brisbane API
     ↓
Python Collector
     ↓
MariaDB
     ↓
Historical Traffic Dataset
     ↓
Preprocessing
     ↓
LSTM
```

Dengan collector berjalan di server:

```text
Laptop tidak perlu menyala 24/7.
```

Data dapat terus dikumpulkan selama server aktif.

Hal ini juga memungkinkan:

* mencari data tambahan;
* mengumpulkan data beberapa hari/minggu;
* melakukan analisis temporal;
* membangun dataset intersection sendiri;
* melakukan training setelah data mencukupi.

---

# 16. Perbedaan Ketiga Dataset

| Dataset  | Fungsi                  | Karakteristik                                   |
| -------- | ----------------------- | ----------------------------------------------- |
| TMU      | Baseline                | Time-series sederhana, interval 15 menit        |
| PEMS04   | Multi-sensor experiment | 307 sensor, Flow + Occupancy + Speed            |
| Brisbane | Intersection-oriented   | Traffic controller/intersection, data real-time |

Ketiga dataset **tidak harus memiliki feature yang sama**.

Yang penting adalah fungsi eksperimennya jelas.

---

# 17. Jangan Menggabungkan Ketiga Dataset Secara Langsung

Dataset:

```text
TMU
PEMS04
Brisbane
```

tidak langsung digabung.

Perbedaan yang harus diperiksa:

```text
timestamp
interval
unit
geographic meaning
sensor meaning
vehicle classification
measurement method
traffic definition
```

Contoh:

```text
TMU
Flow + Speed
```

tidak otomatis sama secara semantik dengan:

```text
Brisbane
vehicle_count + reconstituted_flow
```

Begitu juga:

```text
PEMS04 occupancy
```

tidak boleh dianggap identik dengan:

```text
YOLO occupancy
```

tanpa definisi dan mapping yang jelas.

---

# 18. Target Forecasting

Target disesuaikan dengan dataset.

## TMU

Target baseline:

```text
Future vehicle flow
Future average speed
```

Horizon:

```text
t + 15 menit
t + 30 menit
t + 45 menit
```

Karena TMU memiliki interval 15 menit.

---

## PEMS04

Eksperimen saat ini:

```text
Input:
Flow
Occupancy
Speed

Target:
Flow
Occupancy
Speed

Horizon:
1 timestep
```

Model memprediksi kondisi traffic untuk timestep berikutnya pada sensor yang digunakan.

---

## Brisbane

Target akan ditentukan setelah preprocessing dan analisis data selesai.

Kandidat target:

```text
vehicle_count
reconstituted_flow
density_proxy
queue_proxy
speed-related feature
```

Target akhir tidak boleh dipilih sebelum struktur dan distribusi data Brisbane diperiksa.

---

# 19. Data Split

Untuk seluruh eksperimen time-series:

```text
Chronological split
```

Bukan random split.

Konfigurasi umum:

```text
70% → Training
15% → Validation
15% → Testing
```

Urutan:

```text
PAST --------------------------------------> FUTURE

|------------- TRAIN -------------|
                                |---- VALIDATION ----|
                                                   |------ TEST ------|
```

Tujuan:

menghindari informasi masa depan masuk ke training.

---

# 20. Data Leakage

Scaler hanya boleh di-fit menggunakan training data.

Benar:

```text
TRAIN
  ↓
fit scaler

VALIDATION
  ↓
transform

TEST
  ↓
transform
```

Salah:

```text
TRAIN + VALIDATION + TEST
          ↓
      fit scaler
```

Data masa depan tidak boleh digunakan untuk membentuk input prediksi masa lalu.

---

# 21. Model LSTM

Model baseline menggunakan LSTM berbasis PyTorch.

Konfigurasi PEMS04 saat ini:

```text
Hidden size : 64
LSTM layers : 2
Dropout     : 0.2

Learning rate : 0.001
Batch size    : 64

Maximum epochs       : 100
Early stopping       : 10 epochs
```

Struktur:

```text
Input
  ↓
Flatten sensor × feature
  ↓
LSTM
  ↓
LSTM
  ↓
Dropout
  ↓
Output Layer
  ↓
Forecast
```

Untuk PEMS04 sensor 1–10:

```text
10 × 3 = 30
```

input per timestep.

Untuk sensor 1–20:

```text
20 × 3 = 60
```

input per timestep.

---

# 22. Early Stopping

Training menggunakan early stopping.

Tujuan:

menghentikan training ketika validation loss tidak lagi membaik.

Contoh:

```text
Patience = 10
```

Model terbaik ditentukan berdasarkan:

```text
Validation Loss terendah
```

Model tersebut disimpan sebagai:

```text
best_model.pth
```

Model terbaik **tidak boleh ditimpa oleh model eksperimen lain** tanpa identifikasi yang jelas.

---

# 23. Hasil Training PEMS04 Saat Ini

Eksperimen pertama:

```text
Dataset     : PEMS04
Sensor      : 1–10
Feature     : Flow + Occupancy + Speed
Sequence    : 15 timestep
Horizon     : 1 timestep
```

Hasil training:

```text
Best epoch:
28

Best validation loss:
0.111231
```

Model:

```text
59,806 parameters
```

Model telah berhasil disimpan dan dapat digunakan untuk evaluation dan prediction.

---

# 24. Evaluasi PEMS04 Saat Ini

Hasil test:

```text
MAE  : 0.197478
MSE  : 0.134427
RMSE : 0.366643
R²   : 0.878620
```

Per-feature:

```text
Feature       MAE       RMSE       R²

Flow          0.174370  0.262502   0.933240
Occupancy     0.182695  0.373828   0.869451
Speed         0.235368  0.441166   0.839173
```

Catatan:

MAPE menghasilkan nilai tinggi:

```text
142.5780%
```

MAPE perlu ditafsirkan dengan hati-hati karena nilai aktual yang mendekati nol dapat membuat MAPE menjadi sangat besar.

Karena itu evaluasi tidak boleh hanya menggunakan MAPE.

Metric utama yang perlu diperhatikan:

```text
MAE
RMSE
R²
```

---

# 25. Evaluasi Per Sensor

Evaluasi juga dilakukan per sensor.

Hal ini penting karena performa model tidak selalu sama pada setiap sensor.

Contoh hasil:

```text
Sensor 1  → R² 0.935
Sensor 6  → R² 0.956
Sensor 7  → R² 0.587
Sensor 10 → R² 0.930
```

Sensor 7 menunjukkan performa yang jauh lebih rendah dibandingkan beberapa sensor lain.

Hal tersebut menjadi bahan analisis sebelum langsung mengubah arsitektur model.

---

# 26. Prediction

Prediction pipeline menggunakan:

```text
best_model.pth
```

dan menghasilkan:

```text
prediction.npz
prediction.csv
prediction_summary.json
```

Prediction summary menyimpan informasi:

```text
dataset
sequence_length
forecast_horizon
sensor configuration
features
model architecture
inference time
prediction files
```

Output prediction nantinya harus dapat diterjemahkan menjadi:

```text
Traffic Forecast
```

yang digunakan oleh tahap berikutnya.

---

# 27. Feature Traffic State SmartTwin

Traffic state final yang diharapkan dari YOLO dapat memiliki struktur seperti:

```text
timestamp
intersection_id
lane_id

vehicle_count
car_count
motorcycle_count
bus_count
truck_count

average_speed
queue_length
density
occupancy
```

LSTM tidak harus langsung menggunakan seluruh feature tersebut.

Feature yang digunakan harus berdasarkan:

```text
ketersediaan data
kualitas data
konsistensi definisi
kebutuhan forecasting
```

---

# 28. Hubungan PEMS04 dengan YOLO

PEMS04:

```text
Flow
Occupancy
Speed
```

YOLO nantinya dapat menghasilkan:

```text
Vehicle Count
Vehicle Class
Speed
Queue
Density
Occupancy
```

Keduanya memiliki konsep traffic yang beririsan, tetapi **tidak otomatis memiliki definisi yang sama**.

Sebelum integrasi harus dilakukan:

```text
Feature Mapping
       ↓
Unit Mapping
       ↓
Temporal Alignment
       ↓
Semantic Validation
```

Baru kemudian model dapat disesuaikan dengan traffic state YOLO.

---

# 29. Hubungan Brisbane dengan YOLO

Brisbane lebih dekat dengan konsep:

```text
Intersection Traffic
```

dibandingkan TMU.

Karena itu Brisbane dapat digunakan untuk menjembatani:

```text
Public Traffic Dataset
        ↓
Intersection Dataset
        ↓
YOLO Traffic State
```

Namun data Brisbane tetap harus dipetakan terlebih dahulu.

Contoh:

```text
Brisbane vehicle_count
        ↓
?
YOLO vehicle_count
```

Kesamaan nama tidak otomatis berarti kesamaan definisi.

---

# 30. Hubungan Forecasting dengan SUMO

Forecast LSTM digunakan untuk membantu membentuk kondisi traffic masa depan.

Konsep:

```text
Current Traffic State
        +
Future Traffic Forecast
        ↓
Scenario Generator
        ↓
SUMO
```

Scenario generator dapat menggunakan forecast untuk membentuk skenario:

```text
Normal traffic
High traffic
Low traffic
Increasing traffic
Congested traffic
```

Skenario tersebut kemudian diuji di SUMO.

SUMO dapat menghasilkan:

```text
waiting time
queue length
delay
throughput
emission
```

---

# 31. Hubungan Forecasting dengan PPO

LSTM tidak menentukan lampu lalu lintas.

PPO menerima:

```text
Current Traffic State
        +
Forecast Traffic State
        +
Simulation State
```

kemudian menentukan:

```text
Signal Timing Action
```

Contoh action:

```text
green duration
phase selection
phase extension
phase switching
```

Konsep:

```text
Traffic State
     +
LSTM Forecast
     ↓
    PPO
     ↓
Signal Action
     ↓
   SUMO
     ↓
Performance
     ↓
Reward
     ↓
   PPO
```

---

# 32. Struktur Folder Saat Ini

Struktur yang digunakan untuk eksperimen PEMS04:

```text
forecasting/
│
├── data/
│   ├── TMU.csv
│   ├── Brisbane.csv
│   └── PEMS04.npz
│
├── scripts/
│   └── pems04/
│       ├── 01_inspect_pems04.py
│       ├── 02_preprocess_pems04.py
│       ├── 03_train_pems04.py
│       ├── 04_evaluate_pems04.py
│       └── 05_predict_pems04.py
│
├── outputs/
│   └── pems04/
│       ├── processed/
│       │   ├── X_train.npy
│       │   ├── y_train.npy
│       │   ├── X_val.npy
│       │   ├── y_val.npy
│       │   ├── X_test.npy
│       │   ├── y_test.npy
│       │   ├── scaler_X.pkl
│       │   └── pems04_config.json
│       │
│       ├── best_model.pth
│       ├── training_history.csv
│       ├── training_summary.json
│       │
│       ├── plots/
│       │   └── training_loss.png
│       │
│       └── evaluation/
│           ├── test_predictions.npz
│           ├── overall_metrics.json
│           ├── feature_metrics.csv
│           ├── sensor_metrics.csv
│           ├── evaluation_summary.json
│           └── plots/
│
└── ...
```

---

# 33. Eksperimen PEMS04 Selanjutnya

Eksperimen berikutnya adalah:

```text
PEMS04
Sensor 1–20
Flow + Occupancy + Speed
Sequence 15 timestep
Horizon 1 timestep
```

Pipeline:

```text
PEMS04.npz
     ↓
02_preprocess
     ↓
Sensor 1–20
     ↓
15 timestep sequence
     ↓
03_train
     ↓
best_model
     ↓
04_evaluate
     ↓
05_predict
```

Kemudian dibandingkan dengan eksperimen:

```text
Sensor 1–10
```

Perbandingan:

```text
                Sensor 1–10    Sensor 1–20

MAE                 ?              ?
RMSE                ?              ?
MAPE                ?              ?
R²                  ?              ?
Training time       ?              ?
Parameters          ?              ?
Inference time      ?              ?
```

---

# 34. Eksperimen Sensor Berikutnya

Tidak langsung menggunakan seluruh 307 sensor.

Jika sensor 1–20 memberikan peningkatan yang jelas, eksperimen dapat dilanjutkan:

```text
1–10
   ↓
1–20
   ↓
1–30
   ↓
...
```

Jika penambahan sensor tidak lagi memberikan peningkatan yang berarti, eksperimen dapat dihentikan.

Prinsip:

> Cari jumlah sensor yang memberikan trade-off terbaik antara performa dan kompleksitas.

---

# 35. Brisbane Training

Setelah data Brisbane cukup terkumpul:

```text
Brisbane API
     ↓
MariaDB
     ↓
brisbane_traffic
     ↓
Export / preprocessing
     ↓
Feature selection
     ↓
Sequence generation
     ↓
LSTM
```

Sebelum training harus diperiksa:

```text
timestamp
missing timestep
duplicate
interval
distribusi feature
outlier
jumlah data
```

Tidak boleh langsung training hanya karena data sudah masuk database.

---

# 36. Mengapa Brisbane Tidak Langsung Ditraining Sekarang

Brisbane collector baru bertugas mengumpulkan data.

Model membutuhkan data historis yang cukup untuk mempelajari:

```text
jam sibuk
jam normal
perubahan traffic
hari berbeda
pola temporal
```

Semakin pendek periode data:

```text
pola temporal ↓
```

Semakin sulit memastikan model benar-benar belajar pola traffic.

Karena itu selama Brisbane mengumpulkan data, pekerjaan lain dapat dilakukan paralel:

```text
Brisbane collector
        +
PEMS04 experiments
        +
TMU analysis
        +
SUMO preparation
        +
YOLO integration
```

---

# 37. Strategi Pengembangan Dataset

Tidak semua dataset harus berakhir menjadi satu model.

Strategi:

```text
TMU
 ↓
Baseline forecasting
```

```text
PEMS04
 ↓
Multi-sensor forecasting
 ↓
Sensor experiment
```

```text
Brisbane
 ↓
Intersection forecasting
 ↓
Real-time/historical adaptation
```

Kemudian:

```text
TMU
PEMS04
Brisbane
   ↓
Knowledge / feature / architecture comparison
   ↓
SmartTwin Forecasting Design
```

Bukan:

```text
TMU + PEMS04 + Brisbane
          ↓
     langsung merge
```

---

# 38. Data Leakage Checklist

Sebelum setiap training:

```text
[ ] Chronological split
[ ] Scaler fit hanya pada training
[ ] Validation tidak masuk training
[ ] Test tidak masuk training
[ ] Tidak menggunakan future information
[ ] Sequence dibuat setelah split yang benar
```

---

# 39. Dataset Quality Checklist

Sebelum training:

```text
[ ] Timestamp valid
[ ] Timestamp terurut
[ ] Interval diketahui
[ ] Missing timestep diperiksa
[ ] Duplicate diperiksa
[ ] Missing value diperiksa
[ ] Outlier diperiksa
[ ] Unit feature diketahui
[ ] Feature definition diketahui
```

---

# 40. Model Evaluation Checklist

Model tidak dianggap berhasil hanya karena training selesai.

Periksa:

```text
[ ] Training loss turun
[ ] Validation loss masuk akal
[ ] Tidak overfitting parah
[ ] Test prediction mengikuti actual
[ ] MAE dihitung
[ ] RMSE dihitung
[ ] MAPE dihitung dengan hati-hati
[ ] R² dihitung
[ ] Per-feature metrics diperiksa
[ ] Per-sensor metrics diperiksa
```

---

# 41. Jika Model Jelek

Jangan langsung:

```text
Tambah layer
Tambah neuron
Tambah epoch
Ganti LSTM
Ganti dataset
```

Urutan pemeriksaan:

```text
1. Dataset
2. Timestamp
3. Missing value
4. Duplicate
5. Interval
6. Feature
7. Target
8. Sequence
9. Scaling
10. Data split
11. Leakage
12. Model
13. Hyperparameter
```

---

# 42. Jika MAPE Sangat Besar

MAPE tidak boleh langsung digunakan sebagai satu-satunya indikator.

Jika actual mendekati nol:

```text
actual ≈ 0
```

maka:

```text
percentage error
```

dapat menjadi sangat besar.

Contoh PEMS04:

```text
Overall MAPE = 142.578%
```

Nilai tersebut perlu dianalisis bersama:

```text
MAE
RMSE
R²
```

dan distribusi target.

---

# 43. Aturan Penting

## RULE 1 — Jangan mengejar dataset tanpa batas

Dataset tambahan hanya digunakan jika memberikan manfaat nyata.

Deadline lebih penting daripada jumlah dataset.

---

## RULE 2 — Jangan menggabungkan dataset secara sembarangan

Periksa:

```text
timestamp
unit
interval
geographic meaning
sensor meaning
measurement method
```

---

## RULE 3 — Jangan mengklaim feature yang tidak tersedia

Jika hanya memiliki:

```text
density_proxy
```

jangan menyebutnya:

```text
actual traffic density
```

---

## RULE 4 — Jangan random split time-series

Gunakan chronological split.

---

## RULE 5 — Jangan fit scaler menggunakan test data

Scaler harus berasal dari training data.

---

## RULE 6 — Jangan menghapus model eksperimen

Setiap eksperimen harus memiliki output terpisah atau identitas eksperimen yang jelas.

---

## RULE 7 — Jangan mengubah target hanya karena metric jelek

Periksa terlebih dahulu:

```text
dataset
preprocessing
sequence
scaling
target
leakage
```

---

## RULE 8 — Jangan membuat LSTM terlalu kompleks tanpa alasan

Kompleksitas harus memiliki alasan eksperimental.

---

## RULE 9 — LSTM bukan PPO

```text
LSTM = Forecasting
PPO  = Decision Making
```

---

## RULE 10 — Output harus dapat digunakan tahap berikutnya

Forecast harus dapat diterjemahkan menjadi traffic state dan digunakan dalam:

```text
Scenario Generator
SUMO
PPO
```

---

# 44. Roadmap Saat Ini

Roadmap pengembangan forecasting:

```text
                    ┌──────────────┐
                    │     TMU      │
                    │   Baseline   │
                    └──────┬───────┘
                           ↓
                     LSTM Baseline
                           │
                           ↓
                      Evaluation
                           │
                           │
                    ┌──────┴───────┐
                    ↓              ↓
                PEMS04         Brisbane
             Multi-sensor      Intersection
                    │              │
                    ↓              ↓
                1–10 sensor     Data Collection
                    │              │
                    ↓              │
                1–20 sensor        │
                    │              │
                    ↓              ↓
              Sensor Analysis   Preprocessing
                    │              │
                    └──────┬───────┘
                           ↓
                    Feature Mapping
                           ↓
                    Traffic State
                           ↓
                         YOLO
                           ↓
                    LSTM Forecast
                           ↓
                  Scenario Generator
                           ↓
                         SUMO
                           ↓
                  Performance Analysis
                           ↓
                          PPO
                           ↓
              Signal Timing Recommendation
```

---

# 45. Langkah Berikutnya

Prioritas pengembangan saat ini:

### Step 1 — PEMS04 Sensor 1–20

```text
02_preprocess
      ↓
03_train
      ↓
04_evaluate
      ↓
05_predict
```

Kemudian bandingkan:

```text
PEMS04 1–10
vs
PEMS04 1–20
```

---

### Step 2 — Lanjutkan pengumpulan Brisbane

Collector tetap berjalan:

```text
API
 ↓
MariaDB
 ↓
brisbane_traffic
```

Sambil menunggu data bertambah, tidak perlu menghentikan eksperimen PEMS04.

---

### Step 3 — Analisis Brisbane

Setelah data cukup:

```text
timestamp analysis
missing data
duplicate
interval
distribution
correlation
feature selection
```

---

### Step 4 — Brisbane preprocessing

Tentukan feature dan target berdasarkan data nyata.

---

### Step 5 — Brisbane LSTM

Bangun model dengan pipeline yang konsisten:

```text
preprocess
→ sequence
→ train
→ evaluate
→ predict
```

---

### Step 6 — Bandingkan Dataset

Bandingkan karakteristik:

```text
TMU
PEMS04
Brisbane
```

bukan hanya berdasarkan metric, tetapi juga:

```text
data structure
temporal resolution
feature availability
sensor coverage
intersection relevance
forecast capability
```

---

### Step 7 — Feature Mapping

Setelah model dan dataset dipahami:

```text
PEMS04
      +
Brisbane
      +
YOLO Traffic State
```

dipetakan ke konsep traffic state SmartTwin.

---

### Step 8 — Integrasi SmartTwin

Final pipeline:

```text
YOLO
 ↓
Traffic State Builder
 ↓
Current Traffic State
       +
LSTM Forecast
 ↓
Scenario Generator
 ↓
SUMO
 ↓
Performance Analysis
 ↓
PPO
 ↓
Signal Timing Recommendation
```

---

# 46. Prinsip Akhir Project

Tujuan akhir bukan:

```text
DATA
 ↓
LSTM
 ↓
selesai
```

Tetapi:

```text
DATA
 ↓
TRAFFIC STATE
 ↓
PREDICTION
 ↓
SCENARIO
 ↓
SIMULATION
 ↓
DECISION
```

atau secara sederhana:

```text
DATA → PREDICTION → SIMULATION → DECISION
```

TMU membantu membangun **baseline**.

PEMS04 membantu menguji **multi-sensor traffic forecasting**.

Brisbane membantu mendekatkan sistem ke **traffic intersection dan data yang dikumpulkan secara real-time**.

YOLO nantinya menyediakan **traffic state aktual dari kamera**.

SUMO digunakan untuk **menguji skenario traffic**.

PPO digunakan untuk **mengambil keputusan pengaturan lampu lalu lintas**.

Dengan demikian LSTM tetap berada pada fungsi yang jelas:

```text
LSTM
=
Future Traffic Forecast
```

dan bukan mengambil alih fungsi simulator maupun reinforcement learning.

---

# 47. Current Decision

Konfigurasi eksperimen aktif:

```text
Dataset:
PEMS04

Sensor:
1–10

Feature:
Flow
Occupancy
Speed

Sequence:
15 timestep

Forecast horizon:
1 timestep

Model:
2-layer LSTM

Hidden size:
64

Dropout:
0.2

Batch size:
64

Learning rate:
0.001

Early stopping:
10 epochs

Split:
70 / 15 / 15 chronological

Evaluation:
MAE
RMSE
MAPE
R²
```

Eksperimen berikutnya:

```text
PEMS04
Sensor 1–20
Flow + Occupancy + Speed
15 timestep
1 timestep forecast
```

Sementara:

```text
Brisbane collector
        ↓
MariaDB
        ↓
terus mengumpulkan data
```

Setelah eksperimen PEMS04 selesai:

```text
Brisbane preprocessing
        ↓
Brisbane LSTM
        ↓
Evaluation
        ↓
Prediction
```

Kemudian:

```text
PEMS04
+
Brisbane
+
YOLO Traffic State
        ↓
Feature Mapping
        ↓
SmartTwin Forecasting
        ↓
Scenario Generator
        ↓
SUMO
        ↓
PPO
```


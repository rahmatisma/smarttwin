# SmartTwin Forecasting

Modul forecasting pada SmartTwin digunakan untuk memprediksi kondisi lalu lintas berdasarkan data time-series historis.

Model utama yang digunakan adalah **Long Short-Term Memory (LSTM)** karena data lalu lintas memiliki ketergantungan temporal, sehingga kondisi pada timestep sebelumnya dapat digunakan untuk memprediksi kondisi pada timestep berikutnya.

Repository forecasting ini menggunakan beberapa dataset dengan **tujuan eksperimen yang berbeda**. Dataset tidak digabung secara langsung menjadi satu dataset karena masing-masing memiliki struktur, sensor, interval waktu, unit, dan karakteristik lalu lintas yang berbeda. Pendekatan ini dipertahankan agar setiap eksperimen dapat dievaluasi secara independen.

---

# 1. Struktur Forecasting

Secara umum pipeline forecasting terdiri dari:

```text
Dataset
   ↓
Inspection
   ↓
Preprocessing
   ↓
Chronological Split
   ↓
Scaling
   ↓
Sequence Generation
   ↓
LSTM Training
   ↓
Validation
   ↓
Best Model
   ↓
Test Evaluation
   ↓
Prediction
```

Pipeline tersebut diterapkan secara terpisah untuk masing-masing dataset.

Struktur utama:

```text
forecasting/
│
├── data/
│   ├── TMU/
│   ├── PEMS04/
│   ├── Brisbane/
│   └── YOLO/
│
├── scripts/
│   ├── tmu/
│   ├── pems04/
│   ├── brisbane/
│   └── yolo/
│
├── outputs/
│   ├── tmu/
│   ├── pems04/
│   ├── brisbane/
│   └── yolo/
│
└── README.md
```

Setiap dataset mempunyai folder output sendiri sehingga model, scaler, metric, prediction, dan hasil eksperimen tidak tercampur.

---

# 2. Dataset yang Digunakan

Saat ini terdapat empat dataset yang digunakan atau dikaji dalam pengembangan forecasting:

| Dataset        | Status                | Tujuan                                                 |
| -------------- | --------------------- | ------------------------------------------------------ |
| TMU            | Training + Evaluation | Baseline forecasting                                   |
| PEMS04         | Training + Evaluation | Eksperimen multi-sensor                                |
| Brisbane       | Belum training        | Eksperimen data intersection                           |
| YOLO SmartTwin | Training + Evaluation | Forecasting berdasarkan traffic state aktual SmartTwin |

Penting:

```text
TMU
PEMS04
Brisbane
YOLO
```

tidak digabung menjadi satu dataset training.

Masing-masing dataset diproses menggunakan pipeline sendiri.

---

# 3. Dataset TMU

## 3.1 Tujuan

TMU digunakan sebagai **baseline forecasting**.

Tujuan eksperimen TMU adalah memastikan bahwa pipeline forecasting berbasis LSTM dapat mempelajari pola time-series lalu lintas sebelum digunakan pada eksperimen dengan struktur data yang lebih kompleks.

Dataset TMU merupakan data traffic sensor dengan interval waktu yang relatif lebih panjang dibandingkan dataset YOLO SmartTwin.

---

## 3.2 Karakteristik

Eksperimen TMU menggunakan beberapa variabel lalu lintas seperti:

```text
vehicle_count
speed_value
density_proxy
queue_proxy
```

Sequence digunakan untuk mempelajari hubungan temporal antar timestep.

Konfigurasi eksperimen TMU menggunakan:

```text
Sequence length : 16
Forecast horizon: 1 timestep
```

---

## 3.3 Status

TMU telah melewati:

```text
[x] Data inspection
[x] Preprocessing
[x] Sequence generation
[x] Training
[x] Validation
[x] Test evaluation
[x] Prediction
```

Eksperimen TMU menghasilkan baseline untuk dibandingkan dengan dataset lainnya.

Salah satu hasil evaluasi menunjukkan prediksi `speed_value` memperoleh MAPE sekitar 2,09%.

Namun, MAPE pada feature yang memiliki nilai aktual mendekati nol harus diinterpretasikan dengan hati-hati karena dapat menghasilkan nilai yang sangat besar.

---

# 4. Dataset PEMS04

## 4.1 Tujuan

PEMS04 digunakan untuk eksperimen **multi-sensor traffic forecasting**.

Dataset ini digunakan untuk melihat kemampuan LSTM dalam mempelajari kondisi lalu lintas dari banyak sensor secara bersamaan.

Berbeda dengan TMU yang lebih sederhana, PEMS04 memiliki banyak sensor dan beberapa feature lalu lintas.

---

## 4.2 Struktur Data

Eksperimen PEMS04 menggunakan feature:

```text
flow
occupancy
speed
```

Dengan konfigurasi eksperimen yang digunakan pada pipeline:

```text
Jumlah sensor : 20
Feature/sensor: 3
```

Sehingga:

```text
20 × 3 = 60 feature/timestep
```

Sequence:

```text
Sequence length : 15
Forecast horizon: 1
```

---

## 4.3 Model

Arsitektur LSTM:

```text
Input
  ↓
LSTM Layer 1
  ↓
LSTM Layer 2
  ↓
Dropout
  ↓
Linear Output
```

Konfigurasi:

```text
Hidden size : 64
LSTM layers : 2
Dropout     : 0.2
```

Arsitektur ini dipertahankan sebagai salah satu konfigurasi dasar LSTM dalam eksperimen forecasting SmartTwin.

---

## 4.4 Status

PEMS04 telah melewati:

```text
[x] Data inspection
[x] Preprocessing
[x] Chronological split
[x] Scaling
[x] Sequence generation
[x] Training
[x] Validation
[x] Test evaluation
[x] Prediction
```

Eksperimen PEMS04 menunjukkan bahwa LSTM dapat mempelajari hubungan temporal antar sensor.

Hasil eksperimen sebelumnya menghasilkan R² sekitar:

```text
R² = 0.8786
```

untuk evaluasi keseluruhan eksperimen PEMS04.

Namun metric MAE/RMSE yang dihitung pada data ter-scaled tidak boleh langsung dianggap sebagai satuan fisik seperti kendaraan/jam.

---

# 5. Dataset Brisbane

## 5.1 Tujuan

Brisbane awalnya digunakan untuk mencari dataset yang lebih dekat dengan karakteristik **traffic intersection**.

Hal ini penting karena target SmartTwin adalah persimpangan bersinyal, bukan hanya ruas jalan atau jalan tol.

Pipeline Brisbane menggunakan sumber data traffic controller/API dan collector real-time.

Arsitektur pengumpulan datanya:

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

---

## 5.2 Feature

Data Brisbane memiliki feature yang berbeda dari PEMS04 dan TMU.

Beberapa feature yang digunakan dalam eksperimen awal antara lain:

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

`density_proxy` dan `queue_proxy` harus tetap disebut sebagai **proxy**, bukan pengukuran fisik langsung, apabila data pendukung untuk menghitung physical density atau queue sebenarnya tidak tersedia.

---

## 5.3 Mengapa Brisbane Belum Dilatih?

Brisbane **tidak gagal pada tahap model**.

Training memang belum dapat dilakukan karena data historis yang tersedia belum mencukupi.

Pada eksperimen sebelumnya:

```text
Raw rows        : 66
Rows lolos      : 5
Rentang waktu   : sekitar 5 menit
Sequence length : 16
```

Dengan sequence length 16, data yang tersedia bahkan belum mampu membentuk satu sequence training yang valid.

Artinya:

```text
Brisbane
   ↓
Data belum cukup
   ↓
Preprocessing terbatas
   ↓
Tidak ada training
   ↓
Tidak ada model Brisbane
```

Jadi Brisbane **tidak boleh dilaporkan sebagai model yang performanya buruk**.

Status yang benar:

```text
Brisbane = dataset intersection yang dikaji,
tetapi belum digunakan untuk training karena historical data belum mencukupi.
```

Collector real-time tetap berguna karena dapat terus mengumpulkan data sehingga dataset historis dapat bertambah.

---

# 6. Dataset YOLO SmartTwin

## 6.1 Tujuan

Dataset YOLO merupakan dataset yang berbeda dari tiga dataset sebelumnya.

Dataset ini berasal dari **traffic detection SmartTwin menggunakan YOLO**, sehingga feature yang digunakan merepresentasikan kondisi lalu lintas yang dihasilkan oleh sistem SmartTwin sendiri.

Dataset ini menjadi sangat penting karena tidak lagi hanya menggunakan dataset publik sebagai representasi traffic.

Pipeline:

```text
CCTV
 ↓
YOLO
 ↓
Traffic Detection
 ↓
Traffic Aggregation
 ↓
YOLO Traffic Dataset
 ↓
Preprocessing
 ↓
LSTM
 ↓
Traffic Forecast
```

Dengan demikian forecasting dapat menggunakan traffic state yang berasal dari sistem SmartTwin.

---

# 7. Struktur Dataset YOLO

Dataset YOLO yang digunakan memiliki:

```text
Intersection:
simpang4-pingit
```

Terdapat:

```text
4 approaches
12 lane sensors
```

Approach:

```text
north
east
south
west
```

Setiap approach memiliki lane:

```text
lane_1
lane_2
lane_3
```

Sehingga:

```text
4 approach × 3 lane
= 12 lane sensors
```

---

# 8. Feature Dataset YOLO

Berbeda dengan eksperimen PEMS04, jumlah feature pada dataset YOLO **tidak dipaksakan menjadi 3 feature**.

Semua feature yang tersedia dan relevan dari hasil YOLO digunakan.

Terdapat **8 feature per sensor**:

```text
vehicle_count
car_count
motorcycle_count
bus_count
truck_count
queue_length_veh
queue_length_m_est
density_index
```

Sehingga:

```text
12 sensor × 8 feature
= 96 feature/timestep
```

Dengan demikian input LSTM:

```text
96 feature/timestep
```

dan output:

```text
96 feature/timestep
```

Ini berbeda dengan PEMS04.

PEMS04:

```text
20 sensor × 3 feature
= 60 feature
```

YOLO:

```text
12 sensor × 8 feature
= 96 feature
```

Perbedaan jumlah feature tersebut memang disengaja karena mengikuti struktur asli masing-masing dataset.

---

# 9. Karakteristik Waktu Dataset YOLO

Dataset YOLO yang digunakan memiliki rentang:

```text
Start:
2026-08-15 16:30:12

End:
2026-08-15 17:19:16
```

Durasi:

```text
49 menit 04 detik
```

Dataset memiliki:

```text
Original timestamps : 2,616
Expected 1-second   : 2,945
Missing slots       : 329
```

Karena data berasal dari proses traffic detection, timestamp tidak seluruhnya membentuk grid waktu 1 detik yang sempurna.

Pipeline preprocessing kemudian membentuk timeline lengkap dengan:

```text
2,945 timestep
```

dan menghasilkan complete lane table dengan:

```text
12 sensor × 2,945 timestep
```

---

# 10. Feature Statistics YOLO

Hasil preprocessing:

| Feature            | Min |       Max |     Mean |
| ------------------ | --: | --------: | -------: |
| vehicle_count      |   0 |        15 | 3.089842 |
| car_count          |   0 |         7 | 1.284465 |
| motorcycle_count   |   0 |        12 | 1.616016 |
| bus_count          |   0 |         2 | 0.058376 |
| truck_count        |   0 |         3 | 0.130985 |
| queue_length_veh   |   0 |         5 | 0.073288 |
| queue_length_m_est |   0 |        15 | 0.173599 |
| density_index      |   0 | 45.454544 | 9.267092 |

Tidak ditemukan:

```text
NaN
Inf
negative feature values
duplicate sensor records
```

---

# 11. YOLO Preprocessing

Dataset YOLO menggunakan chronological split:

```text
Train      : 70%
Validation : 15%
Test       : 15%
```

Dari:

```text
2,945 timestep
```

dihasilkan:

```text
Train : 2,061 timestep
Val   :   442 timestep
Test  :   442 timestep
```

Scaler hanya di-fit menggunakan training data.

Sequence:

```text
Sequence length : 15 timestep
Forecast horizon: 1 timestep
```

Hasil sequence:

```text
X_train : (2046, 15, 96)
y_train : (2046, 96)

X_val   : (427, 15, 96)
y_val   : (427, 96)

X_test  : (427, 15, 96)
y_test  : (427, 96)
```

---

# 12. YOLO LSTM Model

Arsitektur YOLO forecasting menggunakan konfigurasi LSTM yang konsisten dengan eksperimen LSTM sebelumnya.

```text
Input
  ↓
LSTM Layer 1
  ↓
LSTM Layer 2
  ↓
Dropout
  ↓
Linear Layer
  ↓
96 outputs
```

Konfigurasi:

```text
Input size   : 96
Hidden size  : 64
LSTM layers  : 2
Dropout      : 0.2
Output size  : 96
```

Jumlah parameter:

```text
80,992
```

---

# 13. YOLO Training Result

Training menggunakan:

```text
Batch size       : 64
Learning rate    : 0.001
Maximum epochs   : 100
Early stopping   : 15 epochs
Loss             : MSELoss
Weight decay     : 1e-5
```

Training berhenti pada:

```text
Epoch : 32
```

karena early stopping.

Best model diperoleh pada:

```text
Best epoch     : 17
Best val loss  : 0.540659
```

Model disimpan sebagai:

```text
outputs/yolo/models/best_model.pth
```

---

# 14. YOLO Test Evaluation

Hasil evaluasi training menghasilkan:

```text
MAE  : 0.391496
MSE  : 0.494536
RMSE : 0.703232
MAPE : 110.5642%
R²   : 0.388572
```

Evaluasi terpisah kemudian dilakukan menggunakan pipeline evaluation.

Hasil evaluasi pada skala asli:

```text
MAE   : 0.851906
MSE   : 3.967761
RMSE  : 1.991924
sMAPE : 133.5164%
R²    : 0.767294
```

Perbedaan angka tersebut terjadi karena evaluasi dilakukan pada tahap dan representasi data yang berbeda.

Untuk interpretasi performa fisik, metric pada **skala asli** lebih relevan.

---

# 15. Catatan tentang MAPE

MAPE pada dataset traffic tidak selalu dapat digunakan sebagai indikator utama.

Beberapa feature memiliki banyak nilai:

```text
0
```

atau mendekati:

```text
0
```

Contohnya:

```text
bus_count
truck_count
queue_length_veh
```

Ketika nilai aktual mendekati nol:

```text
MAPE = |actual - prediction| / |actual|
```

dapat menghasilkan nilai yang sangat besar.

Karena itu:

```text
MAPE tinggi
```

tidak selalu berarti model sepenuhnya gagal.

Metric yang juga harus diperhatikan:

```text
MAE
RMSE
R²
sMAPE
```

serta evaluasi per-feature dan per-sensor.

---

# 16. Perbandingan Dataset

| Dataset  | Domain                  |             Sensor |                      Feature | Status         |
| -------- | ----------------------- | -----------------: | ---------------------------: | -------------- |
| TMU      | Road traffic            |           Terbatas |            Traffic variables | Trained        |
| PEMS04   | Highway traffic         |       Multi-sensor |       Flow, occupancy, speed | Trained        |
| Brisbane | Signalized intersection | Intersection lanes | Controller/traffic variables | Belum training |
| YOLO     | SmartTwin intersection  |    12 lane sensors |             8 feature/sensor | Trained        |

Perbedaan feature bukan masalah.

Yang penting adalah:

```text
dataset
   ↓
feature sesuai dataset
   ↓
preprocessing sesuai dataset
   ↓
model interface sesuai jumlah feature
```

Tidak ada alasan untuk memaksa semua dataset mempunyai jumlah feature yang sama.

---

# 17. Mengapa Dataset Tidak Digabung?

TMU, PEMS04, Brisbane, dan YOLO memiliki perbedaan:

```text
timestamp
interval waktu
unit
sensor
lokasi
jenis jalan
definisi traffic
metode pengukuran
vehicle classification
feature
```

Contohnya:

```text
PEMS04
flow + occupancy + speed
```

tidak secara otomatis memiliki arti yang sama dengan:

```text
YOLO
vehicle_count + car_count + motorcycle_count + ...
```

Karena itu dataset digunakan secara independen.

Tujuan eksperimen bukan membuat satu dataset campuran, tetapi membandingkan bagaimana forecasting bekerja pada karakteristik data yang berbeda.

---

# 18. Output Directory

Semua output dipisahkan berdasarkan dataset.

```text
outputs/
│
├── tmu/
│   ├── processed/
│   ├── models/
│   ├── metrics/
│   ├── predictions/
│   └── plots/
│
├── pems04/
│   ├── processed/
│   ├── models/
│   ├── metrics/
│   ├── prediction/
│   └── plots/
│
├── brisbane/
│   ├── processed/
│   └── test/
│
└── yolo/
    ├── processed/
    ├── models/
    ├── metrics/
    └── plots/
```

Brisbane tidak memiliki folder model karena training belum dilakukan.

YOLO memiliki:

```text
processed/
models/
metrics/
plots/
```

karena pipeline YOLO telah mencapai tahap training dan evaluation.

---

# 19. Script Pipeline

## TMU

```text
scripts/tmu/
```

Pipeline:

```text
01_inspect
02_preprocess
03_train
04_evaluate
05_predict
```

---

## PEMS04

```text
scripts/pems04/
```

Pipeline:

```text
01_inspect
02_preprocess
03_train
04_evaluate
05_predict
```

---

## Brisbane

```text
scripts/brisbane/
```

Pipeline saat ini berfokus pada:

```text
data collection
inspection
preprocessing
```

Training belum dilakukan karena historical data belum mencukupi.

---

## YOLO

```text
scripts/yolo/
```

Pipeline:

```text
01_inspect_yolo.py
02_preprocess_yolo.py
03_train_yolo.py
04_evaluate_yolo.py
05_predict_yolo.py
```

Status:

```text
[x] Inspection
[x] Preprocessing
[x] Training
[x] Evaluation
[ ] Prediction final
```

---

# 20. Data Leakage Prevention

Semua training time-series menggunakan chronological split.

Tidak digunakan random split untuk membagi masa lalu dan masa depan.

Prosedur:

```text
Past ------------------------------> Future

|--------- TRAIN --------|-- VAL --|-- TEST --|
```

Scaler juga hanya di-fit menggunakan training data.

```text
TRAIN
  ↓
fit scaler
  ↓
transform TRAIN
transform VAL
transform TEST
```

Validation dan test tidak digunakan untuk fitting scaler.

Hal ini dilakukan untuk mencegah informasi masa depan masuk ke proses training.

---

# 21. Forecasting SmartTwin

Dataset YOLO memberikan jalur yang lebih langsung menuju sistem SmartTwin:

```text
CCTV
  ↓
YOLO
  ↓
Vehicle Detection
  ↓
Traffic State
  ↓
12 Lane Sensors
  ↓
8 Features / Sensor
  ↓
96 Features / Timestep
  ↓
Sequence 15 Timestep
  ↓
LSTM
  ↓
Forecast 1 Timestep
  ↓
Traffic Forecast
```

Output forecasting kemudian dapat digunakan oleh komponen berikutnya dalam SmartTwin:

```text
Traffic Forecast
       ↓
Scenario Generator
       ↓
SUMO
       ↓
Traffic Simulation
       ↓
Performance Analysis
       ↓
Adaptive Decision
       ↓
Signal Timing Recommendation
```

---

# 22. Posisi Masing-Masing Dataset dalam Penelitian

Dataset tidak mempunyai posisi yang sama.

### TMU

```text
Baseline
```

Digunakan untuk memastikan pipeline forecasting dapat berjalan.

### PEMS04

```text
Multi-sensor experiment
```

Digunakan untuk menguji forecasting dengan banyak sensor dan beberapa feature traffic.

### Brisbane

```text
Intersection data exploration
```

Digunakan untuk mengeksplorasi sumber data intersection yang lebih dekat dengan kebutuhan SmartTwin.

Namun belum cukup untuk training.

### YOLO

```text
SmartTwin-specific traffic forecasting
```

Digunakan untuk menghubungkan traffic detection aktual SmartTwin dengan forecasting.

---

# 23. Kesimpulan

Eksperimen forecasting SmartTwin berkembang dari dataset publik menuju data yang dihasilkan langsung oleh sistem.

Tahap awal:

```text
TMU
 ↓
Baseline
```

Kemudian:

```text
PEMS04
 ↓
Multi-sensor forecasting
```

Selanjutnya:

```text
Brisbane
 ↓
Intersection data exploration
```

dan akhirnya:

```text
YOLO SmartTwin
 ↓
Actual traffic state
 ↓
Intersection forecasting
```

Dengan pendekatan tersebut, forecasting tidak hanya diuji menggunakan dataset publik, tetapi juga mulai diarahkan pada data lalu lintas yang benar-benar berasal dari lingkungan SmartTwin.

**Catatan penting:** dataset TMU dan PEMS04 digunakan sebagai eksperimen/baseline, Brisbane masih pada tahap pengumpulan/eksplorasi data, sedangkan dataset YOLO telah berhasil melewati preprocessing, training, dan evaluation.

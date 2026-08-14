# SmartTwin — Traffic Forecasting

Modul forecasting untuk project SmartTwin.

Modul ini bertujuan membangun model Long Short-Term Memory (LSTM)
untuk memprediksi kondisi lalu lintas berdasarkan data time-series.

Hasil forecasting nantinya digunakan sebagai salah satu input untuk
scenario generation dan adaptive traffic signal control berbasis PPO
di dalam sistem SmartTwin.

---

## 1. Tujuan Utama

Tujuan modul ini bukan hanya mendapatkan model dengan nilai error kecil.

Model harus menghasilkan forecast yang:

1. memiliki hubungan temporal dengan data lalu lintas sebelumnya;
2. dapat memprediksi kondisi lalu lintas beberapa timestep ke depan;
3. dapat diterjemahkan menjadi traffic state;
4. dapat digunakan oleh tahap berikutnya dalam SmartTwin;
5. dapat diintegrasikan dengan data hasil YOLO pada tahap berikutnya.

Pipeline utama:

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


---

# 2. Status Pengembangan

Status saat ini:

- [x] Repository SmartTwin tersedia
- [x] Folder forecasting ditentukan
- [x] Dataset TMU dipilih sebagai dataset baseline
- [ ] Preprocessing dataset TMU
- [ ] Exploratory Data Analysis
- [ ] Pembuatan sequence time-series
- [ ] Training LSTM baseline
- [ ] Evaluasi model
- [ ] Penyimpanan model dan scaler
- [ ] Forecasting menggunakan model
- [ ] Penyesuaian dengan traffic-data-at-intersection
- [ ] Integrasi dengan traffic state YOLO
- [ ] Integrasi dengan scenario generator
- [ ] Integrasi dengan SUMO
- [ ] Integrasi dengan PPO


---

# 3. Dataset Baseline

Dataset baseline yang digunakan:

    TMU Site 9329/1 on A174 eastbound between A19 and A1044

Dataset memiliki data dengan interval 15 menit.

Kolom utama:

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


---

# 4. Kenapa TMU Digunakan Sebagai Baseline

TMU digunakan sebagai dataset pertama karena menyediakan:

- timestamp;
- traffic flow;
- klasifikasi kendaraan berdasarkan ukuran;
- speed;
- data time-series dengan interval yang relatif konsisten.

Data tersebut cukup untuk menguji apakah pola temporal lalu lintas
dapat dipelajari oleh model LSTM.

TMU digunakan sebagai BASELINE.

TMU bukan representasi final dari data YOLO SmartTwin.


---

# 5. Dataset Traffic Intersection

Dataset:

    traffic-data-at-intersection

akan digunakan pada tahap berikutnya.

Tujuan dataset ini adalah mendekatkan model terhadap kondisi lalu lintas
pada intersection/lane.

Dataset ini tidak boleh langsung digabung dengan TMU sebagai data mentah
tanpa pemeriksaan struktur dan semantik terlebih dahulu.

Perbedaan dataset harus diperiksa sebelum:

- merging;
- transfer learning;
- fine-tuning;
- feature mapping.


---

# 6. Dataset DFT Raw Counts

Dataset:

    dft_traffic_counts_raw_counts

berukuran sangat besar dan tidak digunakan pada eksperimen baseline.

Dataset disimpan sebagai kandidat data tambahan.

Jangan memasukkan dataset ini ke pipeline utama sebelum:

1. struktur data dipahami;
2. definisi setiap kolom diketahui;
3. kebutuhan data terhadap SmartTwin dikonfirmasi;
4. waktu preprocessing sesuai dengan deadline.


---

# 7. Struktur Folder

Struktur modul forecasting:

forecasting/
│
├── .venv/
│
├── data/
│   ├── .gitkeep
│   ├── TMU.csv
│   └── Brisbane.csv                  ← DATASET BARU
│
├── models/
│   ├── .gitkeep
│   │
│   ├── lstm_model.pt                 ← MODEL TMU
│   ├── model_config.json
│   ├── scaler_X.pkl
│   ├── scaler_y.pkl
│   │
│   └── brisbane/                     ← MODEL BRISBANE
│       ├── lstm_model.pt
│       ├── model_config.json
│       ├── scaler_X.pkl
│       └── scaler_y.pkl
│
├── outputs/
│   │
│   ├── metrics/                      ← HASIL TMU
│   │   ├── metrics.json
│   │   ├── test_predictions.csv
│   │   ├── training_history.csv
│   │   └── training_summary.json
│   │
│   ├── plots/                        ← HASIL TMU
│   │   ├── density_proxy_forecast.png
│   │   ├── queue_proxy_forecast.png
│   │   ├── speed_value_forecast.png
│   │   └── vehicle_count_forecast.png
│   │
│   ├── predictions/
│   │   └── forecast.csv
│   │
│   ├── processed/                    ← HASIL TMU
│   │   ├── feature_config.json
│   │   ├── tmu_metadata.json
│   │   └── tmu_processed.csv
│   │
│   └── brisbane/                     ← SEMUA HASIL BRISBANE
│       ├── processed/
│       │   └── brisbane_processed.csv
│       │
│       ├── metrics/
│       │   ├── metrics.json
│       │   ├── test_predictions.csv
│       │   ├── training_history.csv
│       │   └── training_summary.json
│       │
│       ├── plots/
│       │   ├── vehicle_count_forecast.png
│       │   ├── density_proxy_forecast.png
│       │   └── queue_proxy_forecast.png
│       │
│       └── predictions/
│           └── forecast.csv
│
└── scripts/
    ├── 01_preprocess.py
    ├── 02_train_lstm.py
    ├── 03_evaluate.py
    ├── 04_predict.py
    │
    ├── 05_preprocess_brisbane.py
    ├── 06_train_brisbane.py
    ├── 07_evaluate_brisbane.py
    └── 08_predict_brisbane.py


---

# 8. Fungsi Setiap Script

## 01_prepare_tmu.py

Bertanggung jawab untuk:

- membaca dataset mentah;
- membersihkan nama kolom;
- menggabungkan tanggal dan waktu;
- mengurutkan timestamp;
- memeriksa missing value;
- memeriksa duplicate timestamp;
- memeriksa interval waktu;
- membuat fitur temporal;
- membuat fitur traffic;
- melakukan preprocessing;
- menyimpan dataset hasil preprocessing.

Output utama:

    tmu_processed.csv


---

## 02_train_lstm.py

Bertanggung jawab untuk:

- membaca dataset hasil preprocessing;
- menentukan feature;
- melakukan chronological train/validation/test split;
- melakukan scaling;
- membuat sequence;
- membangun model LSTM;
- melakukan training;
- menggunakan EarlyStopping;
- menyimpan model;
- menyimpan scaler;
- menyimpan konfigurasi model;
- menyimpan training history.

Output utama:

    lstm_model.keras
    scaler_X.pkl
    scaler_y.pkl
    model_config.json
    training_history.csv


---

## 03_evaluate.py

Bertanggung jawab untuk mengevaluasi model pada data test.

Metric minimum:

    MAE
    RMSE
    MAPE
    R²

Output:

    metrics/
    plots/


Grafik minimum:

1. Actual vs Predicted
2. Training Loss vs Validation Loss
3. Prediction Error


---

## 04_predict.py

Bertanggung jawab untuk:

- memuat model;
- memuat scaler;
- membaca data terbaru;
- membuat input sequence;
- menghasilkan forecast;
- mengembalikan hasil dalam format yang dapat digunakan pipeline
  berikutnya.

Output:

    predictions/


---

# 9. Feature yang Digunakan

Feature harus dipilih berdasarkan fungsi dan ketersediaan data.

Feature baseline yang dipertimbangkan:

    total_flow
    car_count
    medium_vehicle_count
    large_vehicle_count
    heavy_vehicle_count
    average_speed

Feature temporal:

    hour
    minute
    day_of_week
    is_weekend
    day_type


---

# 10. Feature Turunan

Feature turunan dapat digunakan apabila memang memberikan informasi
tambahan dan dapat dihitung secara valid.

Contoh:

    car_ratio
    medium_vehicle_ratio
    large_vehicle_ratio
    heavy_vehicle_ratio

Rasio dihitung terhadap total flow.

Contoh:

    car_ratio = car_count / total_flow

Feature perubahan:

    flow_change
    speed_change

Feature tersebut digunakan untuk menangkap perubahan traffic dari
timestep sebelumnya.


---

# 11. Traffic Density

Density harus diperlakukan dengan hati-hati.

TMU tidak secara langsung menyediakan physical traffic density.

Physical density membutuhkan informasi seperti panjang segmen jalan
atau pengukuran spasial yang sesuai.

Oleh karena itu:

    traffic_density

tidak boleh diklaim sebagai density aktual jika data yang dibutuhkan
tidak tersedia.

Jika diperlukan untuk eksperimen, gunakan:

    traffic_density_proxy

atau:

    congestion_index

dan dokumentasikan bahwa feature tersebut merupakan proxy.


---

# 12. Target LSTM

Target utama baseline:

    future_vehicle_count
    future_average_speed


Forecast horizon awal:

    t + 15 minutes
    t + 30 minutes
    t + 45 minutes

Karena data TMU memiliki interval 15 menit.

Horizon dapat diubah berdasarkan hasil eksperimen.

Target harus tetap konsisten dengan kebutuhan tahap berikutnya.


---

# 13. Sequence LSTM

Data time-series tidak boleh diacak sebelum sequence dibuat.

Contoh:

    timestep t-14
    timestep t-13
    ...
    timestep t-1
    timestep t
            ↓
        LSTM
            ↓
    t+1 ... t+n


Contoh konfigurasi baseline:

    lookback = 15 timestep

Dengan interval 15 menit:

    15 × 15 menit = 225 menit

Artinya model melihat sekitar 3 jam 45 menit history.


---

# 14. Train / Validation / Test Split

Data harus dibagi berdasarkan urutan waktu.

Tidak menggunakan random split untuk time-series forecasting.

Contoh:

    70% → training
    15% → validation
    15% → testing

Urutan:

    PAST ----------------------------> FUTURE

    |------ TRAIN ------|
                     |--- VALIDATION ---|
                                      |------ TEST ------|


Tujuan:

menghindari data masa depan masuk ke training.


---

# 15. Data Leakage

Data leakage harus dihindari.

Scaler hanya boleh di-fit menggunakan training data.

Benar:

    train → fit scaler
    validation → transform
    test → transform

Salah:

    seluruh dataset → fit scaler


Model juga tidak boleh menggunakan informasi masa depan ketika
memprediksi timestep tertentu.


---

# 16. Model LSTM

Model baseline harus cukup kuat tetapi tidak berlebihan.

Contoh struktur:

    Input
      ↓
    LSTM
      ↓
    Dropout
      ↓
    LSTM
      ↓
    Dense
      ↓
    Forecast


Model dapat dikembangkan berdasarkan hasil evaluasi.

Jangan menambah kompleksitas model hanya karena model dapat dibuat
lebih kompleks.


---

# 17. Output Training

Training harus menghasilkan minimal:

### Model

    lstm_model.keras

Model yang dapat dimuat kembali untuk inference.


### Input Scaler

    scaler_X.pkl

Scaler untuk feature input.


### Output Scaler

    scaler_y.pkl

Scaler untuk target.


### Configuration

    model_config.json

Berisi informasi seperti:

    feature_columns
    target_columns
    lookback
    forecast_horizon
    model architecture
    training configuration


### Training History

    training_history.csv

Berisi:

    epoch
    loss
    validation_loss


---

# 18. Output Evaluasi

Minimal:

    MAE
    RMSE
    MAPE
    R²


Interpretasi:

### MAE

Rata-rata besar kesalahan prediksi.

Semakin kecil semakin baik.


### RMSE

Memberikan penalti lebih besar terhadap error besar.

Semakin kecil semakin baik.


### MAPE

Kesalahan relatif dalam persen.

Harus digunakan dengan hati-hati ketika actual value mendekati nol.


### R²

Mengukur seberapa baik variasi target dapat dijelaskan model.

Semakin mendekati 1 biasanya semakin baik.


---

# 19. Output Forecast

Format output harus dapat digunakan oleh tahap berikutnya.

Contoh:

    timestamp
    forecast_horizon
    predicted_vehicle_count
    predicted_average_speed
    Predicted vehicle count	
    Predicted density	
    Predicted queue	
    Predicted speed	


Contoh:

    2026-03-01 10:00
    +15min
    580
    94.2

    2026-03-01 10:00
    +30min
    625
    91.8

    2026-03-01 10:00
    +45min
    670
    89.4


---

# 20. Hubungan dengan YOLO

Pada sistem final, YOLO diharapkan menghasilkan traffic state seperti:

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


Data tersebut merupakan representasi traffic state pada intersection.

LSTM nantinya digunakan untuk memprediksi traffic state masa depan.


---

# 21. Hubungan dengan PPO

LSTM bukan pengambil keputusan lampu lalu lintas.

LSTM:

    memprediksi kondisi traffic.


PPO:

    menentukan tindakan signal control.


Konsep:

    Current Traffic State
             +
    Forecast Traffic State
             ↓
           PPO
             ↓
    Signal Timing Action


Contoh action:

    green duration
    phase selection
    phase extension
    phase switching


Detail action akan mengikuti desain environment PPO.


---

# 22. Hubungan dengan SUMO

Forecast LSTM dapat digunakan untuk:

    scenario generation

dan/atau:

    traffic demand prediction


Kemudian scenario tersebut digunakan dalam:

    SUMO


SUMO menghasilkan:

    waiting time
    queue length
    delay
    throughput
    emissions


Metric tersebut dapat digunakan untuk mengevaluasi keputusan PPO.


---

# 23. Eksperimen Tahap 1

Eksperimen pertama:

    TMU
      ↓
    preprocessing
      ↓
    LSTM
      ↓
    evaluation


Tujuan:

Menjawab pertanyaan:

    "Apakah pola traffic dari TMU dapat dipelajari oleh LSTM
     dan menghasilkan forecast yang masuk akal?"


Tidak perlu langsung memasukkan PPO.


---

# 24. Eksperimen Tahap 2

Jika baseline berhasil:

    TMU LSTM
       ↓
    Traffic Intersection Data
       ↓
    feature mapping
       ↓
    fine-tuning / adaptation


Tujuan:

Mendekatkan model dari dataset publik menuju traffic state
yang lebih sesuai dengan SmartTwin.


---

# 25. Eksperimen Tahap 3

Setelah data YOLO tersedia:

    YOLO
      ↓
    Traffic State
      ↓
    LSTM
      ↓
    Forecast
      ↓
    Scenario Generator
      ↓
    SUMO


Model final harus menggunakan format data yang kompatibel dengan
Traffic State Builder.


---

# 26. Aturan Penting

## RULE 1 — Jangan mengejar dataset tanpa batas

Dataset tambahan hanya digunakan jika memberikan manfaat nyata
terhadap sistem.

Deadline lebih penting daripada mengumpulkan dataset sebanyak mungkin.


## RULE 2 — Jangan menggabungkan dataset secara sembarangan

Dataset berbeda harus diperiksa:

    timestamp
    unit
    interval
    geographic meaning
    vehicle classification
    measurement method


sebelum digabung.


## RULE 3 — Jangan mengklaim feature yang tidak benar-benar tersedia

Contoh:

Jika density tidak tersedia:

    jangan menyebutnya actual density.


Gunakan:

    density_proxy

jika memang diperlukan.


## RULE 4 — Jangan random split time-series

Gunakan chronological split.


## RULE 5 — Jangan fit scaler menggunakan test data

Scaler harus berasal dari training data.


## RULE 6 — Jangan menghapus model terbaik

Setiap eksperimen yang menghasilkan model lebih baik harus disimpan
dengan jelas.


## RULE 7 — Jangan mengubah target hanya karena metric jelek

Pertama periksa:

    dataset
    preprocessing
    sequence
    leakage
    target definition


baru kemudian ubah arsitektur.


## RULE 8 — Jangan membuat LSTM terlalu kompleks tanpa alasan

Model harus cukup untuk kebutuhan forecasting.


## RULE 9 — LSTM bukan PPO

LSTM = forecasting.

PPO = decision making.


## RULE 10 — Output harus dirancang untuk tahap berikutnya

Model tidak hanya dinilai berdasarkan MAE/RMSE.

Output harus dapat digunakan oleh:

    Traffic State
    Scenario Generator
    SUMO
    PPO


---

# 27. Kriteria Model Dianggap Berhasil

Model tidak dianggap berhasil hanya karena training selesai.

Minimal harus memenuhi:

- training berjalan tanpa error;
- validation loss masuk akal;
- test prediction mengikuti pola aktual;
- error tidak terlalu besar;
- tidak menunjukkan overfitting parah;
- prediction mengikuti perubahan traffic;
- forecast dapat digunakan dalam pipeline SmartTwin.


---

# 28. Checklist Sebelum Mengganti Model

Sebelum melakukan perubahan besar:

[ ] Apakah preprocessing benar?

[ ] Apakah timestamp benar?

[ ] Apakah interval data konsisten?

[ ] Apakah ada missing timestep?

[ ] Apakah ada duplicate?

[ ] Apakah ada data leakage?

[ ] Apakah scaler benar?

[ ] Apakah train/validation/test chronological?

[ ] Apakah target masuk akal?

[ ] Apakah prediction mengikuti actual?

[ ] Apakah metric sudah dihitung?

[ ] Apakah output model tersimpan?

[ ] Apakah output dapat digunakan tahap berikutnya?


---

# 29. Jika Model Jelek

Jangan langsung:

    tambah layer
    tambah neuron
    tambah epoch
    ganti LSTM
    ganti dataset


Urutan pemeriksaan:

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


---

# 30. Prinsip Utama Project

Tujuan akhir:

    DATA → PREDICTION → SIMULATION → DECISION


Bukan:

    DATA → LSTM → selesai


LSTM hanyalah salah satu komponen dari SmartTwin.

Model harus tetap sederhana, dapat dijelaskan, dapat dievaluasi,
dan dapat diintegrasikan dengan sistem berikutnya.


---

# 31. Current Decision

Untuk eksperimen pertama:

    Dataset:
    TMU Site 9329/1

    Model:
    LSTM

    Input:
    Historical traffic features

    Target:
    Future traffic flow dan speed

    Forecast horizon:
    15 / 30 / 45 menit

    Split:
    70 / 15 / 15 chronological

    Evaluation:
    MAE
    RMSE
    MAPE
    R²

    Output:
    model
    scaler
    configuration
    metrics
    predictions
    plots


Setelah baseline selesai:

    TMU
      ↓
    LSTM baseline
      ↓
    Evaluation
      ↓
    Traffic Intersection Dataset
      ↓
    Feature Mapping / Fine-tuning
      ↓
    YOLO-compatible Traffic State
      ↓
    Scenario Generator
      ↓
    SUMO
      ↓
    PPO


---

# 32. Jangan Mengubah Arah Tanpa Alasan

Jika terjadi kebingungan selama development, kembali ke prinsip:

    Apakah perubahan ini membuat forecasting lebih berguna
    untuk tahap SUMO dan PPO?

Jika tidak:

    jangan dilakukan dulu.

Jika iya:

    dokumentasikan alasannya sebelum mengubah pipeline.
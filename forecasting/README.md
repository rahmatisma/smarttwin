# SmartTwin Forecasting

Modul ini memprediksi kondisi lalu lintas 60 detik ke depan menggunakan LSTM
PyTorch dan data CV Simpang Pingit berinterval 5 detik. Tersedia dua model:

- model agregat untuk endpoint agregat dan fallback;
- shared LSTM per-approach sebagai model utama endpoint per-approach serta
  input prediktif Decision Engine live.

## Pipeline aktif

```text
crossing_simpang.csv + snapshot_zona.csv
                 ↓ preprocessing 5 detik
vehicleCount, queueLengthVeh, queueLengthMEst, densityIndex
                 ↓ histori 12 timestep / 60 detik
traffic_lstm.pt / traffic_lstm_per_approach.pt
                 ↓ prediksi 12 timestep / 60 detik
/api/forecast atau /api/forecast/approaches
                 ↓ 30% forecast + 70% kondisi live
RuleBasedEngine.recommend/recommend_cycle
                 ↓
SignalService → rekomendasi durasi hijau empat lengan
```

File utama:

- `scripts/lstm/train.py`: preprocessing, training, baseline, dan evaluasi;
- `scripts/lstm/predict.py`: prediksi offline;
- `outputs/lstm/traffic_lstm.pt`: model aktif;
- `outputs/lstm/scaler.json`: parameter normalisasi;
- `outputs/lstm/metadata.json`: konfigurasi dan metrik;
- `backend/app/services/forecast_service.py`: serving model.
- `backend/app/services/per_approach_forecast_service.py`: serving shared LSTM
  per-approach;
- `backend/app/services/signal_service.py`: integrasi forecast ke siklus lampu
  live dengan fallback ke TrafficState saat ini.

## Instalasi

Jalankan dari root repository:

```powershell
# Environment training/evaluasi forecasting
py -3.10 -m venv forecasting\.venv
.\forecasting\.venv\Scripts\python.exe -m pip install -r forecasting\requirements.txt

# Environment API dan serving model
py -3.10 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Backend hanya melakukan inferensi. `scikit-learn` dan `matplotlib` berada di
requirement forecasting karena hanya diperlukan saat preprocessing, training,
dan evaluasi.

## Data dan preprocessing

Model aktif menggunakan:

- `data/crossing_simpang.csv` untuk `vehicleCount`;
- `data/snapshot_zona.csv` untuk density dan estimasi antrean.

Ketentuan preprocessing:

- interval lima detik;
- chronological split 70% train, 15% validation, 15% test;
- scaler hanya di-fit pada train;
- sequence yang melintasi gap observasi dibuang;
- input 12 timestep dan output 12 timestep;
- empat fitur: `vehicleCount`, `queueLengthVeh`, `queueLengthMEst`, dan
  `densityIndex`.

### Pemilihan panjang histori

Panjang input 12 langkah sudah diuji, bukan sekadar diasumsikan. Eksperimen
27 Agustus membandingkan 6, 12, 18, 30, 60, dan 120 langkah dengan seed dan
split kronologis yang sama. Pemilihan menggunakan validation MAE satuan asli;
test tidak dipakai untuk memilih konfigurasi.

| Input | Histori | Train/val/test sequence | Validation MAE | Hasil |
|---:|---:|---:|---:|---|
| 6 | 30 detik | 1164/136/64 | 1,8841 | layak |
| **12** | **60 detik** | **1044/100/16** | **1,8046** | **terpilih** |
| 18–120 | 90–600 detik | tidak lengkap | — | tidak feasible karena gap |

Jalankan ulang dengan:

```powershell
$env:PYTHONUTF8='1'
.\forecasting\.venv\Scripts\python.exe `
    forecasting/scripts/lstm/per_approach/sequence_length_experiment.py
```

Artefak hasilnya berada di
`outputs/lstm/per_approach/sequence_length_experiment.json`.

Jalankan training:

```powershell
$env:PYTHONUTF8='1'
cd forecasting
.\.venv\Scripts\python.exe scripts\lstm\train.py
```

### Training shared LSTM per approach

Pipeline ini tidak menimpa model agregat. Seluruh artefaknya masuk ke
`outputs/lstm/per_approach/`.

```powershell
$env:PYTHONUTF8='1'
cd forecasting

# 1. Gabungkan crossing + snapshot menjadi empat deret approach
.\.venv\Scripts\python.exe scripts\lstm\per_approach\prepare_data.py

# 2. Latih satu shared LSTM dengan one-hot identity approach
.\.venv\Scripts\python.exe scripts\lstm\per_approach\train.py

# 3. Evaluasi ulang artefak model terhadap test dan naive baseline
.\.venv\Scripts\python.exe scripts\lstm\per_approach\evaluate.py

# 4. Prediksi 12 langkah untuk west/south/east/north
.\.venv\Scripts\python.exe scripts\lstm\per_approach\predict.py
```

Output utama:

- `data/processed/traffic_per_approach_5s.csv`;
- `outputs/lstm/per_approach/traffic_lstm_per_approach.pt`;
- `outputs/lstm/per_approach/metadata.json`;
- `outputs/lstm/per_approach/metrics_by_approach.json`;
- `outputs/lstm/per_approach/latest_forecast.json`.

Model menerima 12 timestep × 8 input: empat fitur traffic dan empat one-hot
identity approach. Outputnya 12 timestep × empat fitur traffic untuk approach
tersebut. Density dan antrean north masih memakai zona `simpang_tengah` sebagai
proxy, sesuai mapping Traffic State Builder.

## Hasil model agregat

Hasil retraining 26 Agustus 2026:

| Metrik | LSTM | Last-value baseline |
|---|---:|---:|
| MAE agregat | 2,6180 | 3,4159 |
| RMSE agregat | 3,8029 | 5,2989 |
| MAE vehicle count | 2,2192 | 4,0208 |
| MAE queue kendaraan | 3,0286 | 2,5201 |
| MAE panjang antrean | 5,1958 | 7,0951 |
| MAE density | 0,0286 | 0,0276 |

Secara agregat LSTM mengalahkan baseline, tetapi baseline masih sedikit lebih
baik untuk queue kendaraan dan density. Setelah sequence yang melintasi gap
dibuang, test efektif hanya empat sequence. Karena data berasal dari satu sesi
sekitar 49 menit, hasil ini harus disebut **proof of concept**, bukan model
produksi yang sudah mampu melakukan generalisasi lintas hari dan kondisi.

## Hasil shared LSTM per-approach

Training selesai pada 26 Agustus 2026 menggunakan satu model bersama dengan
one-hot identity approach. Model berhenti melalui early stopping pada epoch 56.

```text
Train rows/sequences      : 1.504 / 1.044
Validation rows/sequences :   320 /   100
Test rows/sequences       :   328 /    16
```

| Metrik | Shared LSTM | Last-value baseline |
|---|---:|---:|
| MAE keseluruhan | 1,6528 | 2,2973 |
| RMSE keseluruhan | 2,9826 | 4,8455 |
| MAE vehicle count | 1,1432 | 1,9635 |
| MAE queue kendaraan | 1,2119 | 1,5220 |
| MAE panjang antrean | 4,2236 | 5,6510 |
| MAE density | 0,0322 | 0,0525 |

| Approach | Shared LSTM MAE | Baseline MAE | Hasil |
|---|---:|---:|---|
| West | 3,0360 | 3,9841 | LSTM lebih baik |
| South | 1,3244 | 2,4007 | LSTM lebih baik |
| East | 0,9842 | 1,1900 | LSTM lebih baik |
| North | 1,2664 | 1,6143 | LSTM lebih baik |

Model mengalahkan baseline pada seluruh approach, tetapi test efektif hanya 16
sequence atau empat sequence per approach. Angka tersebut masih proof of
concept. West memiliki error tertinggi, sedangkan density/queue north memakai
zona `simpang_tengah` sebagai proxy, bukan pengukuran north murni.

### Uji robustness tanpa training ulang

Checkpoint yang sama juga diuji pada gabungan rentang validation dan test
setelah batas data training. Dari 196 sequence valid, LSTM mengalahkan baseline
last-value pada 114 sequence (58,16%). MAE keseluruhan turun dari 2,0563 menjadi
1,6715 dan RMSE turun dari 4,3054 menjadi 3,1337. LSTM lebih baik pada west,
south, dan north; pada east baseline masih sedikit lebih baik (MAE 1,1808 vs
1,2503).

Rentang ini disebut **post-training holdout/robustness check**, bukan independent
test, karena bagian validation pernah dipakai untuk early stopping. Bukti ini
memperluas jumlah sequence yang diperiksa tanpa melebih-lebihkan kemampuan
generalisasi lintas hari. Hasil lengkap tersimpan di
`outputs/lstm/per_approach/metrics_post_training_holdout.json`.

Uji dampak operasional pada 10 snapshot historis dengan horizon SUMO identik
256 langkah menunjukkan forecast memperbaiki delay 10/10, antrean 9/10, dan
throughput 10/10; ketiga metrik membaik bersamaan pada 9/10 snapshot. Rata-rata
perubahan adalah delay -3,925 detik, antrean -10,5 meter, dan throughput +3,2
kendaraan. Seluruh snapshot masih berasal dari satu sesi rekaman, sehingga ini
belum membuktikan generalisasi lintas hari. Lihat
`../docs/hasil-studi-forecast-multi-snapshot.md`.

## API

### Forecast agregat

```text
POST /api/forecast
```

Body harus memuat minimal 12 record berinterval lima detik:

```json
{
  "records": [
    {
      "timestamp": "2026-08-15T16:30:10",
      "vehicleCount": 8,
      "queueLengthVeh": 4,
      "queueLengthMEst": 18,
      "densityIndex": 0.4
    }
  ]
}
```

Contoh di atas menunjukkan bentuk satu record; ulangi sampai 12 record dengan
timestamp `16:30:10`, `16:30:15`, ..., `16:31:05`.

### Forecast per pendekat

```text
POST /api/forecast/approaches
```

Body juga wajib memiliki **12 record waktu**, bukan hanya satu record dengan
empat pendekat:

```json
{
  "records": [
    {
      "timestamp": "2026-08-15T16:30:10",
      "approaches": [
        {"approach":"west", "vehicleCount":8, "queueLengthVeh":4, "queueLengthMEst":18, "densityIndex":0.4},
        {"approach":"south", "vehicleCount":6, "queueLengthVeh":3, "queueLengthMEst":14, "densityIndex":0.3},
        {"approach":"east", "vehicleCount":4, "queueLengthVeh":2, "queueLengthMEst":9, "densityIndex":0.2},
        {"approach":"north", "vehicleCount":2, "queueLengthVeh":1, "queueLengthMEst":5, "densityIndex":0.1}
      ]
    }
  ]
}
```

Tambahkan 11 record berikutnya dengan interval lima detik. Respons berisi:

- `approachForecasts`: 12 horizon untuk setiap pendekat;
- `forecastSource`: `lstm-per-approach`;
- `fallbackUsed`: `false` ketika shared model berhasil digunakan;
- `model` dan `input`: identitas model serta rentang histori yang dipakai.

Endpoint memakai shared LSTM per-approach sebagai model utama. Jika artefak atau
input per-approach tidak dapat dipakai, endpoint jatuh ke model agregat dengan
`forecastSource=aggregate-recent-share-fallback` dan `fallbackUsed=true`.

Pada jalur live, `SignalService` mengambil histori TrafficState dari Supabase,
menjalankan shared LSTM, lalu mengirim hasilnya ke
`RuleBasedEngine.recommend_cycle()`. `RecommendationService` melakukan hal yang
sama untuk `RuleBasedEngine.recommend()`. Jika 12 TrafficState lengkap
berinterval lima detik belum tersedia atau inferensi gagal, Decision Engine
tetap berjalan menggunakan kondisi live tanpa forecast.

### Jalur simulasi dan dashboard

`simulation/forecast_client.py` meneruskan forecast ke `ScenarioEngine`.
`simulation/scenario_worker.py` menjalankan tiga kandidat SUMO di background,
menyimpan pemenang ke `liveScenarioCache`, dan backend memakai hasil cache yang
masih segar pada `/recommendation`. Cache basi/tidak tersedia selalu fallback
ke RuleBasedEngine. Integrasi ini sudah diverifikasi end-to-end dengan
`source="scenario-generator"`.

Forecast mengubah state keputusan dan timing, tetapi belum menginjeksi kendaraan
prediksi ke route SUMO. Model juga tidak menerima aksi/fase lampu sebagai input,
sehingga ia memprediksi tren demand—bukan dampak kausal dari durasi hijau tertentu.

## Menjalankan dan menguji

Semua command berikut dijalankan dari root repository.

### Jalankan backend

```powershell
$env:DEBUG='false'
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Buka dokumentasi API di `http://127.0.0.1:8000/docs`.

### Health check model agregat

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/forecast/health |
    ConvertTo-Json -Depth 10
```

### Tes forecasting dan Decision Engine tanpa Supabase

```powershell
$env:DEBUG='false'
.\backend\.venv\Scripts\python.exe -m pytest `
    backend/tests/test_forecast_decision_integration.py `
    backend/tests/test_signal_service.py `
    backend/tests/test_rule_based_engine_cycle.py -q
```

Tes ini memeriksa model per-approach sungguhan, output 60 detik untuk empat
lengan, penerusan forecast ke Decision Engine, rotasi sinyal, dan fallback.

### Tes seluruh backend

```powershell
$env:DEBUG='false'
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Sebagian tes penuh membutuhkan koneksi Supabase dan data ingest. Kegagalan
koneksi pada tes database/traffic tidak berarti inferensi LSTM gagal.


### Prediksi offline dan evaluasi ulang

```powershell
$env:PYTHONUTF8='1'
.\forecasting\.venv\Scripts\python.exe forecasting/scripts/lstm/predict.py
.\forecasting\.venv\Scripts\python.exe forecasting/scripts/lstm/per_approach/predict.py
.\forecasting\.venv\Scripts\python.exe forecasting/scripts/lstm/per_approach/evaluate.py
.\forecasting\.venv\Scripts\python.exe forecasting/scripts/lstm/per_approach/evaluate_holdout.py
```

Evaluasi dampak forecast ke Scenario Generator/SUMO (inference saja, tanpa
training) dijalankan dari root repo:

```powershell
$env:PYTHONPATH="$PWD;$PWD\backend;$PWD\simulation"
.\backend\.venv\Scripts\python.exe simulation/evaluate_forecast_batch.py `
    --snapshots 10 `
    --history-limit 100 `
    --pause-seconds 2
```

Perintah ini memerlukan backend environment, koneksi Supabase, dan SUMO. Semua
pasangan forecast OFF/ON memakai horizon 256 langkah yang sama agar throughput
dapat dibandingkan secara adil.

## Riwayat eksperimen dataset

Dataset berikut tetap digunakan secara independen karena interval, sensor,
fitur, lokasi, dan definisinya berbeda. Dataset tidak digabung langsung.

| Dataset | Peran | Fitur/struktur utama | Status |
|---|---|---|---|
| TMU | Baseline awal | vehicle count, speed, density/queue proxy | Training dan evaluasi selesai |
| PEMS04 | Eksperimen multi-sensor | 20 sensor × flow, occupancy, speed | Training dan evaluasi selesai; R² sekitar 0,8786 |
| Brisbane | Eksplorasi persimpangan | controller/API, lane count, flow, cycle | Belum training karena histori tidak cukup |
| YOLO SmartTwin | Forecast dari deteksi lokal | 12 lane sensor × 8 fitur | Training dan evaluasi eksperimen selesai |
| LSTM Pingit agregat | Serving dan fallback | agregat empat fitur CV asli | Training dan API agregat selesai |
| Shared LSTM per-approach | Forecast empat lengan | 4 fitur traffic + one-hot approach | Training, evaluasi, serving API, dan Decision Engine live selesai |

### TMU

Dipakai untuk memastikan pipeline time-series berjalan. Konfigurasi awal memakai
sequence 16 dan horizon satu timestep. Salah satu eksperimen menghasilkan MAPE
`speed_value` sekitar 2,09%; MAPE fitur mendekati nol harus ditafsirkan hati-hati.

### PEMS04

Eksperimen highway multi-sensor menggunakan 20 sensor × 3 fitur atau 60 fitur
per timestep. Model dua lapis LSTM, hidden size 64, dan dropout 0,2 menghasilkan
R² sekitar 0,8786. Metrik pada skala hasil normalisasi tidak boleh langsung
dianggap sebagai satuan fisik.

### Brisbane

Ditujukan untuk data persimpangan bersinyal. Data awal hanya 66 baris mentah,
lima baris valid, dan sekitar lima menit histori, sehingga tidak dapat membentuk
sequence 16. Statusnya adalah kekurangan histori, bukan kegagalan model.

### YOLO SmartTwin

Eksperimen lama menggunakan empat pendekat, 12 lane sensor, dan delapan fitur
per sensor atau 96 fitur per timestep. Konfigurasinya dua lapis LSTM, hidden size
64, dropout 0,2. Training berhenti di epoch 32 dengan best epoch 17. Evaluasi
skala asli mencatat MAE 0,8519, RMSE 1,9919, dan R² 0,7673. Nilai MAPE tinggi
dipengaruhi banyak target nol seperti bus, truk, dan queue.

## Status integrasi

- [x] model PyTorch dan scaler tersedia;
- [x] forecast empat fitur selama 60 detik;
- [x] sequence sadar gap timestamp;
- [x] perbandingan dengan naive baseline;
- [x] endpoint agregat dan per-pendekat;
- [x] forecast opsional pada RuleBasedEngine dan ScenarioEngine;
- [x] shared LSTM per-approach sudah dilatih dan mengalahkan baseline;
- [x] prediksi offline 12 langkah untuk empat approach;
- [x] backend memuat shared LSTM per-approach sebagai model utama endpoint;
- [x] forecast per-approach terhubung ke RecommendationService dan SignalService;
- [x] fallback ke kondisi live tersedia ketika forecast gagal;
- [x] panjang histori 12 langkah dipilih lewat eksperimen validation MAE;
- [x] forecast terhubung ke ScenarioEngine dan cache dashboard live;
- [ ] histori lintas hari/jam/cuaca belum tersedia;
- [ ] predicted demand belum diinjeksi ke SUMO;
- [ ] export ONNX membutuhkan dependency `onnxscript`.

Untuk serving utama, file `.pt` sudah cukup; kegagalan export ONNX tidak
mengganggu backend PyTorch.

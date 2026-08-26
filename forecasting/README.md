# SmartTwin Forecasting

Modul ini memprediksi kondisi lalu lintas 60 detik ke depan menggunakan LSTM
PyTorch dan data CV Simpang Pingit berinterval 5 detik. Tersedia dua model:

- model agregat untuk endpoint agregat dan fallback;
- shared LSTM per-approach sebagai model utama endpoint per-approach serta
  input prediktif Decision Engine live.

## Pipeline aktif

Training dan runtime adalah dua alur berbeda. CSV dipakai untuk melatih model;
serving tidak membaca CSV atau keluaran YOLO secara langsung.

```text
TRAINING
crossing_simpang.csv + snapshot_zona.csv
    → preprocessing per 5 detik
    → sequence 12 input / 12 output
    → traffic_lstm.pt + traffic_lstm_per_approach.pt

RUNTIME BACKEND
CV/YOLO + ByteTrack
    → metrik traffic per window 5 detik
    → TrafficState contract di Supabase
    → TrafficService mengambil 12 state lengkap terakhir
    → shared LSTM per-approach memprediksi 60 detik
    → RuleBasedEngine (70% state aktual + 30% forecast)
    → SignalService dan RecommendationService

RUNTIME SIMULATION
TrafficState API
    → simulation/forecast_client.py
    → Forecast API
    → ScenarioEngine
    → run_tls_simulation.py / SUMO
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
- `simulation/forecast_client.py`: client yang menyiapkan forecast dari histori
  TrafficState untuk jalur batch SUMO;
- `simulation/run_tls_simulation.py`: meneruskan forecast ke ScenarioEngine dan
  tetap memakai TrafficState aktual jika forecast tidak tersedia.

## Sumber TrafficState saat runtime

LSTM tidak menerima bounding box, track YOLO, maupun CSV mentah. Batas input
serving adalah kontrak `TrafficState` yang sudah berisi empat approach dan empat
fitur traffic. Karena itu, LSTM secara arsitektural berada **setelah** Traffic
State Builder, bukan menggantikannya.

Saat ini terdapat dua jalur produsen data:

1. Pipeline empat kamera terkalibrasi menghasilkan CSV CV, lalu
   `backend/app/pipeline/cv_csv_bridge.py` memasukkan lane metrics dan
   `TrafficStateBuilder` membentuk approach state di Supabase.
2. Pemrosesan satu video yang diunggah melalui halaman CCTV memakai
   `cv/process_uploaded_video.py`. Jalur ini menghitung window lima detik dan
   langsung melakukan upsert ke `trafficStates` serta
   `trafficApproachStates`. Implementasinya adalah builder sederhana khusus
   satu approach, bukan pemanggilan class `TrafficStateBuilder` utama.

Kedua jalur berakhir pada kontrak database yang sama. Forecast live membaca
kontrak tersebut melalui `TrafficService.get_latest_traffic()`. Client simulasi
membacanya melalui `GET /api/v1/traffic/{intersectionId}`. Dengan demikian tidak
ada jalur langsung `YOLO → LSTM` dan tidak ada duplikasi preprocessing di SUMO.

## Arti realtime pada implementasi sekarang

Sistem sudah event-driven pada level hasil deteksi: setiap window lima detik
yang selesai diproses disimpan ke Supabase, lalu
`cv/process_uploaded_video.py` memanggil `POST /api/v1/traffic/notify` dan
backend meneruskannya ke dashboard melalui WebSocket. Forecast dan rekomendasi
selalu mengambil histori terbaru yang sudah tersimpan.

Namun sumber gambarnya masih file video yang diunggah atau rekaman lokal, bukan
stream kamera RTSP yang terus-menerus. Jadi istilah yang tepat untuk kondisi
sekarang adalah **near-real-time processing dari rekaman/video upload**, bukan
live CCTV end-to-end. Supabase berperan sebagai penyimpanan state; push dashboard
menggunakan WebSocket backend karena Supabase Realtime tidak dipakai pada jalur
aktif ini.

Untuk menjadi realtime end-to-end, pekerjaan berikutnya berada di sisi producer
CV: menerima RTSP/live capture, memproses frame kontinu, menutup window setiap
lima detik, menyimpan TrafficState lengkap, dan mengirim notify. LSTM tidak perlu
dilatih ulang hanya karena sumber berubah, selama kontrak fitur dan intervalnya
tetap sama.

## Posisi Decision Engine dan PPO

Forecast saat ini dibaca oleh `RuleBasedEngine`, bukan PPO. `ScenarioEngine`
dan runner SUMO sudah menerima forecast melalui `simulation/forecast_client.py`.
Implementasi PPO belum tersedia. Alur target masa depan adalah:

```text
TrafficState → LSTM forecast → state/observation PPO → timing signal → SUMO
```

Jangan menyatakan PPO sudah membaca keluaran LSTM sebelum environment, model,
loader, dan evaluasi PPO benar-benar ditambahkan serta diuji.

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
    backend/tests/test_rule_based_engine_cycle.py `
    simulation/tests/test_forecast_client.py -q
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
```

### Jalankan SUMO dengan forecast

Backend harus hidup karena simulation forecast client memakai Traffic API dan
Forecast API. Jalankan runner pada terminal lain:

```powershell
$env:SMARTTWIN_BACKEND_URL='http://127.0.0.1:8000'
$env:FORECAST_ENABLED='true'
$env:FORECAST_WEIGHT='0.3'
.\simulation\.venv\Scripts\python.exe simulation\run_tls_simulation.py
```

Log yang membuktikan forecast diteruskan ke Decision Engine:

```text
Forecast berhasil dimuat.
Source                 : lstm-per-approach
Horizon                : 12 timestep / 60 detik
Decision weight        : 0.3
Source                 : rule-based+forecast
```

Jika histori/model/backend tidak tersedia, runner menampilkan fallback dan SUMO
tetap berjalan dari TrafficState aktual.

Setiap hasil juga menyimpan provenance numerik pada `simulationMetrics`:
`forecastApplied`, `forecastWeight`, `forecastFallbackUsed`, dan
`recommendedGreenSeconds`. Nama sumber forecast tetap dicetak di log karena
skema `simulationMetrics.metricValue` hanya menerima angka.

### A/B test SUMO

Tanpa forecast:

```powershell
$env:FORECAST_ENABLED='false'
$env:FORECAST_WEIGHT='0.0'
.\simulation\.venv\Scripts\python.exe simulation\run_tls_simulation.py
```

Dengan forecast:

```powershell
$env:FORECAST_ENABLED='true'
$env:FORECAST_WEIGHT='0.3'
.\simulation\.venv\Scripts\python.exe simulation\run_tls_simulation.py
```

Bandingkan `averageWaitingTimeSeconds`, `queueLengthVeh`, `throughputVeh`, dan
LOS dari dua hasil tersebut. Jangan menyimpulkan forecast memperbaiki sinyal
sebelum hasil A/B menunjukkan perbaikan pada data holdout/skenario yang sama.

Hasil A/B aktual 26 Agustus 2026 setelah normalisasi density dan fase kuning,
menggunakan TrafficState ID `13784` serta route file yang sama:

| Metrik | Tanpa forecast (simulation 12) | Forecast 30% (simulation 13) | Hasil |
|---|---:|---:|---|
| Green south | 38 detik | 22 detik | Berubah |
| Average waiting time | 31,56 detik | 32,83 detik | Forecast lebih buruk 1,27 detik |
| Peak queue | 13 kendaraan | 16 kendaraan | Forecast lebih buruk 3 kendaraan |
| Throughput | 59 kendaraan | 57 kendaraan | Forecast lebih buruk 2 kendaraan |

Kesimpulan yang sah dari satu pasangan run ini: integrasi LSTM memengaruhi
keputusan timing, tetapi belum terbukti meningkatkan performa. Perlu beberapa
TrafficState holdout dan pengulangan terkontrol sebelum menarik kesimpulan umum.

### Predicted demand

Forecast saat ini memengaruhi pemilihan approach dan timing, tetapi tidak
menambah kendaraan ke route SUMO. Injeksi otomatis sengaja belum diaktifkan:
route file belum memiliki mapping resmi `approach → origin edge/route`, sehingga
membagi kendaraan prediksi secara acak akan membuat evaluasi menyesatkan.
Prasyarat sebelum injeksi adalah mapping empat approach ke route masuk, mode
replace/scale demand statis (bukan menumpuk kendaraan ganda), dan seed yang sama
untuk A/B. Ini keputusan validasi, bukan kegagalan loader LSTM.

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
- [x] client forecast untuk jalur batch simulation tersedia dan diuji;
- [x] `run_tls_simulation.py` meneruskan forecast ke ScenarioEngine;
- [ ] histori lintas hari/jam/cuaca belum tersedia;
- [ ] PPO belum diimplementasikan dan belum membaca forecast;
- [ ] predicted demand belum diinjeksi ke SUMO;
- [ ] export ONNX membutuhkan dependency `onnxscript`.

Untuk serving utama, file `.pt` sudah cukup; kegagalan export ONNX tidak
mengganggu backend PyTorch.

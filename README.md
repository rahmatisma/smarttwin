| Tabel                       | Diisi oleh                      | Dibaca oleh                              | Fungsi utama                                     |
| --------------------------- | ------------------------------- | ---------------------------------------- | ------------------------------------------------ |
| `intersections`             | Backend/manual seed             | Hampir semua modul                       | Master data simpang                              |
| `approaches`                | Backend/manual seed             | TrafficStateBuilder, SUMO, PPO           | Master 4 arah: north/south/east/west             |
| `lanes`                     | Backend/manual seed             | TrafficStateBuilder, CV                  | Master setiap lane                               |
| `cameras`                   | Backend/manual seed             | CV / backend                             | Informasi kamera CCTV                            |
| `videoUploads`              | Frontend/CV                     | CV processing                            | Video yang di-upload                             |
| `cvProcessingJobs`          | Backend/CV                      | CV pipeline                              | Status/proses YOLO                               |
| **`trafficLaneMetrics`**    | **YOLO/CV**                     | **TrafficStateBuilder, LSTM, PPO, SUMO** | **Data mentah traffic per lane**                 |
| **`trafficStates`**         | Backend / Traffic State Builder | **LSTM, PPO, Dashboard, Simulation**     | **Snapshot kondisi traffic satu waktu**          |
| **`trafficApproachStates`** | **TrafficStateBuilder**         | **LSTM, PPO, Dashboard, SUMO**           | **Agregasi lane → approach**                     |
| `signalStatuses`            | SUMO / signal controller        | Dashboard, PPO                           | Kondisi lampu lalu lintas                        |
| `forecasts`                 | LSTM                            | PPO, Dashboard, Simulation               | Metadata hasil forecasting                       |
| `forecastPredictions`       | LSTM                            | PPO, Dashboard, Simulation               | Prediksi traffic masa depan                      |
| `recommendations`           | PPO / Decision Engine           | Dashboard, signal controller             | Rekomendasi timing lampu                         |
| `simulationRuns`            | SUMO                            | Dashboard, analysis                      | Riwayat simulasi                                 |
| `simulationMetrics`         | SUMO                            | Dashboard, PPO/analysis                  | Delay, queue, throughput, waiting time, emission |

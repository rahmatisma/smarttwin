# Studi Multi-Snapshot Forecast LSTM

Dihasilkan: 2026-08-29T17:48:27.165937+00:00

Tidak ada training pada studi ini. Checkpoint LSTM yang sudah ada dipakai untuk inferensi, lalu setiap TrafficState diuji forecast OFF/ON dengan Scenario Generator dan SUMO secara serial. Kedua kondisi memakai horizon identik 256 langkah agar throughput adil.

- Snapshot: 20
- Delay membaik: 20/20
- Antrean membaik: 17/20
- Throughput membaik: 19/20
- Ketiganya membaik bersamaan: 17/20

| Timestamp | Δ delay (s) | Δ antrean (m) | Δ throughput |
|---|---:|---:|---:|
| 2026-08-15T17:10:40+00:00 | -4.24 | -7.00 | +5 |
| 2026-08-15T17:10:55+00:00 | -5.65 | -14.00 | +2 |
| 2026-08-15T17:11:10+00:00 | -1.29 | +0.00 | +1 |
| 2026-08-15T17:11:25+00:00 | -2.81 | +0.00 | +0 |
| 2026-08-15T17:11:40+00:00 | -3.00 | -7.00 | +4 |
| 2026-08-15T17:11:50+00:00 | -3.30 | +0.00 | +3 |
| 2026-08-15T17:12:05+00:00 | -4.53 | -7.00 | +3 |
| 2026-08-15T17:12:20+00:00 | -3.85 | -7.00 | +2 |
| 2026-08-15T17:12:35+00:00 | -3.08 | -7.00 | +2 |
| 2026-08-15T17:12:50+00:00 | -2.17 | -7.00 | +2 |
| 2026-08-15T17:13:05+00:00 | -3.86 | -7.00 | +4 |
| 2026-08-15T17:13:20+00:00 | -2.71 | -7.00 | +4 |
| 2026-08-15T17:14:55+00:00 | -4.18 | -7.00 | +3 |
| 2026-08-15T17:16:30+00:00 | -4.51 | -7.00 | +3 |
| 2026-08-15T17:16:45+00:00 | -3.93 | -14.00 | +4 |
| 2026-08-15T17:18:20+00:00 | -6.65 | -21.00 | +1 |
| 2026-08-15T17:18:35+00:00 | -7.54 | -21.00 | +4 |
| 2026-08-15T17:18:50+00:00 | -7.45 | -28.00 | +3 |
| 2026-08-15T17:19:05+00:00 | -6.73 | -14.00 | +4 |
| 2026-08-15T17:19:20+00:00 | -4.91 | -14.00 | +3 |

Δ = dengan forecast − tanpa forecast. Nilai negatif lebih baik untuk delay/antrean; nilai positif lebih baik untuk throughput. Hasil ini berasal dari satu sesi rekaman dan bukan validasi lintas hari.

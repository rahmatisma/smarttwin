# Studi Multi-Snapshot Forecast LSTM

Dihasilkan: 2026-08-28T21:03:31.957763+00:00

Tidak ada training pada studi ini. Checkpoint LSTM yang sudah ada dipakai untuk inferensi, lalu setiap TrafficState diuji forecast OFF/ON dengan Scenario Generator dan SUMO secara serial. Kedua kondisi memakai horizon identik 256 langkah agar throughput adil.

- Snapshot: 10
- Delay membaik: 10/10
- Antrean membaik: 9/10
- Throughput membaik: 10/10
- Ketiganya membaik bersamaan: 9/10

| Timestamp | Δ delay (s) | Δ antrean (m) | Δ throughput |
|---|---:|---:|---:|
| 2026-08-15T17:10:40+00:00 | -4.24 | -7.00 | +5 |
| 2026-08-15T17:11:10+00:00 | -1.29 | +0.00 | +1 |
| 2026-08-15T17:11:40+00:00 | -3.00 | -7.00 | +4 |
| 2026-08-15T17:12:10+00:00 | -4.22 | -7.00 | +4 |
| 2026-08-15T17:12:40+00:00 | -3.61 | -7.00 | +4 |
| 2026-08-15T17:13:15+00:00 | -1.29 | -7.00 | +4 |
| 2026-08-15T17:16:25+00:00 | -2.59 | -7.00 | +3 |
| 2026-08-15T17:18:20+00:00 | -6.65 | -21.00 | +1 |
| 2026-08-15T17:18:50+00:00 | -7.45 | -28.00 | +3 |
| 2026-08-15T17:19:20+00:00 | -4.91 | -14.00 | +3 |

Δ = dengan forecast − tanpa forecast. Nilai negatif lebih baik untuk delay/antrean; nilai positif lebih baik untuk throughput. Hasil ini berasal dari satu sesi rekaman dan bukan validasi lintas hari.

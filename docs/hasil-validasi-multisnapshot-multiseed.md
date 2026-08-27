# Hasil Validasi Multi-Snapshot dan Multi-Seed

Dihasilkan: `2026-08-27T05:26:58.195526+00:00`

- Snapshot representatif: 3
- Seed SUMO: 42, 43, 44
- Run per kandidat: 9
- Forecast: tidak dipakai untuk mengisolasi pengaruh durasi kandidat

## Hasil agregat

| Kandidat | Run | Delay mean +/- SD (s) | Antrean mean +/- SD (m) | Throughput mean | Menang |
|---|---:|---:|---:|---:|---:|
| baseline | 9 | 14.34 +/- 0.85 | 39.67 +/- 6.06 | 7.22 | 2 |
| aggressive | 9 | 14.45 +/- 0.81 | 39.67 +/- 6.06 | 7.22 | 0 |
| balanced | 9 | 13.60 +/- 1.27 | 35.78 +/- 5.47 | 7.67 | 7 |

## Batasan

- Snapshot mengubah keputusan approach/durasi, tetapi route demand SUMO masih statis.
- Hasil belum merupakan kalibrasi model terhadap data lapangan.
- Forecast tidak dipakai agar pengaruh kandidat durasi diisolasi.

Hasil ini adalah validasi sensitivitas simulasi, bukan bukti optimum universal.

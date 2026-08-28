# Hasil Studi Forecast vs Tanpa Forecast

> **Catatan versi:** tabel eksperimen di bawah dijalankan ketika kandidat
> `aggressive` masih memakai rumus lama `baseline x 1,2`. Implementasi aktif
> sekarang memakai `baseline + 1 detik` setelah sweep 28–34 detik. Hasil
> kalibrasi aktif ada di `hasil-kalibrasi-kandidat-agresif.md`; tabel lama ini
> dipertahankan sebagai audit trail, bukan sebagai hasil kode terbaru.

**Dihasilkan:** 2026-08-27T03:07:10.387619+00:00

## Metode pengujian

Satu snapshot `TrafficState` yang sama (`simpang4-pingit`, window akhir 15 Agustus 2026 17:19:20 UTC) diuji dalam dua kondisi:

1. **Tanpa forecast:** `RuleBasedEngine` memakai 100% kondisi lalu lintas saat ini.
2. **Dengan forecast:** input keputusan merupakan campuran 70% kondisi saat ini dan 30% prediksi LSTM horizon +60 detik (`forecastWeight=0.3`).

Setiap kondisi memilih satu approach prioritas, kemudian menghasilkan tiga kandidat durasi hijau untuk approach yang sama. Setiap kandidat dijalankan dalam sesi SUMO terpisah selama 90 langkah:

- **Baseline:** durasi asli hasil `RuleBasedEngine`.
- **Aggressive:** `min(60, round(baseline × 1,2))` detik. Angka +20% adalah skenario pembanding demonstrasi, bukan hasil kalibrasi lalu lintas.
- **Balanced:** `round((baseline + 15) / 2)` detik, yaitu menarik durasi baseline ke arah batas minimum 15 detik.

Pemenang adalah kandidat dengan skor terendah:

```text
score = 0,5 × (delay / delay maksimum dalam kelompok)
      + 0,5 × (antrean / antrean maksimum dalam kelompok)
```

## Mengapa memakai baseline, aggressive, dan balanced?

Tiga nama ini **bukan keluaran LSTM**. LSTM hanya memprediksi kondisi traffic.
Ketiganya adalah desain eksperimen Scenario Generator:

1. **Baseline:** keputusan asli RuleBasedEngine sebagai kontrol.
2. **Aggressive:** menambah pelayanan lengan tersibuk. Kode aktif memakai
   `min(60, baseline + 1)`; +1 detik adalah alternatif lebih panjang dengan
   degradasi terkecil pada sweep awal.
3. **Balanced:** `round((baseline + 15) / 2)`, yaitu menguji durasi yang lebih
   dekat ke minimum green 15 detik.

Literatur mendukung **prinsip umumnya**, bukan tiga nama dan rumus persis ini.
Pedoman FHWA menjelaskan green interval melalui minimum/maximum green dan
perpanjangan berdasarkan demand. Studi adaptive signal control menilai perubahan
timing melalui delay, stops, waiting time, dan ukuran efisiensi. Karena itu,
mengeksplorasi beberapa durasi di sekitar baseline dan mengujinya di SUMO masuk
akal; tetapi rumus `+1`, balanced, dan bobot seleksi 50:50 tetap heuristik
SmartTwin yang perlu validasi lebih luas, bukan formula universal.

Rujukan:

- [FHWA Traffic Signal Timing Manual, Chapter 5](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm)
- [FHWA Traffic Signal Timing and Operations Strategies](https://ops.fhwa.dot.gov/arterial_mgmt/tst_ops.htm)
- [SUMO-RL reward documentation](https://lucasalegre.github.io/sumo-rl/mdp/reward/)
- [Deep Reinforcement Learning for Traffic Light Control](https://arxiv.org/abs/1803.11115)

## Hasil seluruh kandidat

| Kondisi | Kandidat | Hijau (s) | Delay (s) | Antrean (kend.) | Antrean (m) | Throughput | LOS |
|---|---|---:|---:|---:|---:|---:|---:|
| Tanpa forecast | baseline | 60 | 15.49 | 8 | 56.00 | 7 | B |
| Tanpa forecast | aggressive | 60 | 15.49 | 8 | 56.00 | 7 | B |
| Tanpa forecast | balanced | 38 | 15.57 | 6 | 42.00 | 6 | B |
| Dengan forecast | baseline | 28 | 13.85 | 5 | 35.00 | 8 | B |
| Dengan forecast | aggressive | 34 | 14.87 | 6 | 42.00 | 8 | B |
| Dengan forecast | balanced | 22 | 13.37 | 5 | 35.00 | 9 | B |

Tanpa forecast, `baseline` dan `aggressive` sama-sama 60 detik karena baseline sudah mencapai batas maksimum. Walaupun kandidat `balanced` mempunyai delay sedikit lebih tinggi, antreannya lebih rendah sehingga skor gabungannya menjadi yang terbaik. Dengan forecast, `balanced` mempunyai delay terendah, antrean setara nilai terendah, dan throughput tertinggi sehingga terpilih dengan lebih jelas.

## Asal dan perhitungan LOS

Nilai delay berasal dari rata-rata sampel `traci.vehicle.getAccumulatedWaitingTime(vehicleId)` untuk seluruh kendaraan aktif pada setiap langkah simulasi. Nilai tersebut dipetakan ke Level of Service HCM 2000 untuk simpang bersinyal:

| LOS | Rata-rata delay per kendaraan |
|---|---:|
| A | ≤ 10 detik |
| B | > 10 sampai ≤ 20 detik |
| C | > 20 sampai ≤ 35 detik |
| D | > 35 sampai ≤ 55 detik |
| E | > 55 sampai ≤ 80 detik |
| F | > 80 detik |

Karena delay pemenang tanpa forecast adalah 15,57 detik dan dengan forecast 13,37 detik, keduanya berada pada rentang LOS B. LOS tetap B bukan berarti tidak ada perbaikan; delay membaik tetapi belum melewati batas 10 detik untuk masuk LOS A.

Metrik lain dihitung sebagai berikut:

- Antrean kendaraan: jumlah maksimum kendaraan dengan kecepatan <0,1 m/s selama simulasi.
- Antrean meter: estimasi `antrean kendaraan × 7 meter`, bukan pengukuran geometri langsung.
- Throughput: jumlah kendaraan yang selesai perjalanan (`arrived`) selama 90 langkah.

## Perbandingan kandidat pemenang

| Kondisi | Kandidat | Delay (s) | Antrean (m) | Throughput | LOS |
|---|---:|---:|---:|---:|---:|
| Tanpa forecast | balanced | 15.57 | 42.00 | 6 | B |
| Dengan forecast | balanced | 13.37 | 35.00 | 9 | B |

## Selisih (dengan forecast - tanpa forecast)

- Delay: -2.20 detik
- Antrean: -7.00 meter
- Throughput: +3 kendaraan

Nilai negatif untuk delay/antrean berarti hasil dengan forecast lebih baik. Ini satu eksperimen pada satu snapshot, sehingga belum cukup untuk klaim signifikansi statistik.

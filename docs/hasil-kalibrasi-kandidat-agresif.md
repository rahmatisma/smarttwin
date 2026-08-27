# Hasil Analisis Sensitivitas Awal Kandidat Agresif

**Tanggal:** 27 Agustus 2026  
**Traffic state:** `trafficStateId=13784`, Simpang Pingit  
**Forecast:** LSTM per-approach, horizon 60 detik, bobot 0,3  
**Horizon simulasi:** 90 langkah per kandidat

> **Status bukti:** eksperimen eksploratif satu snapshot. Dokumen ini bukan
> validasi statistik, bukan penerapan Webster's formula, dan tidak membuktikan
> bahwa tambahan satu detik optimal untuk seluruh kondisi Simpang Pingit.

## Tujuan

Menguji apakah kandidat agresif lama `baseline x 1,2` mempunyai dukungan dari
hasil simulasi. Baseline Rule-Based Engine pada input ini adalah approach
selatan dengan hijau 28 detik. Semua durasi bilangan bulat dari 28 sampai 34
detik diuji menggunakan konfigurasi dan arus SUMO yang sama.

## Metode

Metode yang dipakai adalah **simulation-based discrete parameter sweep**, yaitu
analisis sensitivitas satu faktor (*one-factor-at-a-time*/OFAT):

1. Faktor yang diubah hanya durasi hijau approach selatan.
2. Durasi diuji dari 28 sampai 34 detik.
3. Forecast, traffic state, konfigurasi SUMO, dan horizon simulasi dibuat sama.
4. Setiap alternatif dibandingkan menggunakan delay, panjang antrean,
   throughput, dan LOS.

Selisih **satu detik adalah resolusi pencarian eksperimen**, bukan konstanta
teoretis atau rekomendasi baku dari suatu formula lalu lintas.

## Hasil sweep

| Hijau (s) | Delay rata-rata (s) | Antrean (m) | Throughput | LOS |
|---:|---:|---:|---:|:---:|
| 28 | 13,85 | 35 | 8 | B |
| 29 | 13,98 | 35 | 8 | B |
| 30 | 14,13 | 35 | 8 | B |
| 31 | 14,26 | 35 | 8 | B |
| 32 | 14,42 | 35 | 8 | B |
| 33 | 14,72 | 42 | 8 | B |
| 34 | 14,87 | 42 | 8 | B |

## Interpretasi hasil

Pada snapshot ini, data tidak mendukung ekstensi +20%: delay meningkat 1,02
detik dan antrean meningkat 7 meter dibanding baseline. Baseline 28 detik tetap
memberikan delay terendah di antara durasi 28-34 detik.

Di antara alternatif yang harus tetap lebih panjang daripada baseline, 29 detik
memberikan degradasi paling kecil (+0,13 detik) dan tidak meningkatkan antrean.
Karena itu, kandidat agresif dipertahankan sebagai **stress-test konservatif**
dengan tambahan satu detik. Kandidat ini bukan pengganti baseline dan bukan
durasi yang diklaim optimal; Scenario Generator tetap menentukan pemenang dari
hasil perbandingan seluruh kandidat.

## Keputusan implementasi

Rumus implementasi:

```text
aggressiveGreen = min(MAX_GREEN_SECONDS, baselineGreen + 1)
```

## Batasan dan validasi lanjutan

Eksperimen ini baru memakai satu traffic state dan satu run untuk setiap durasi.
Karena itu, hasilnya harus disebut **analisis sensitivitas awal** atau **pilot
simulation-based parameter sweep**, bukan kalibrasi ilmiah final.

Validasi yang lebih kuat memerlukan:

- beberapa snapshot yang mewakili kondisi sepi, sedang, dan padat;
- beberapa random seed dan pengulangan untuk setiap alternatif;
- pelaporan rata-rata, simpangan baku, dan interval kepercayaan;
- kalibrasi model SUMO terhadap volume, antrean, atau waktu tempuh lapangan; dan
- evaluasi terpisah untuk kondisi dengan forecast dan tanpa forecast.

## Kalimat yang aman untuk laporan/presentasi

> Kandidat agresif awalnya memakai kenaikan ilustratif 20%. Kami kemudian
> melakukan *simulation-based discrete parameter sweep* dengan resolusi satu
> detik pada snapshot pengujian yang sama. Kenaikan 20% memperburuk delay dan
> antrean, sehingga kandidat agresif dibatasi menjadi stress-test konservatif
> baseline +1 detik. Nilai tersebut merupakan hasil analisis sensitivitas awal,
> bukan durasi optimal universal.

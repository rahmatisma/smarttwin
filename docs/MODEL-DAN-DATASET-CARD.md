# Model dan Dataset Card SmartTwin

**Diperbarui:** 1 September 2026

Dokumen ini mencatat kemampuan dan batas model berdasarkan artefak yang ada di
repository. Angka tidak boleh diganti dengan klaim baru tanpa hasil evaluasi.

## Computer Vision

- Tugas: deteksi kelas kendaraan, tracking ByteTrack, crossing count, estimasi
  density, dan antrean.
- Sumber studi: rekaman empat CCTV Simpang Pingit.
- Hasil validasi manual: akurasi crossing rata-rata **48,7% pada 8 sampel**.
- Keterbatasan utama: kehilangan deteksi/tracking saat kondisi padat, potensi
  ID switch, serta `north` memakai area tengah simpang sebagai proxy.
- Output `dataQuality` runtime hanya mengukur kelengkapan metric row untuk empat
  lengan. Nilai tersebut bukan confidence deteksi atau akurasi YOLO.

Rujukan: [`hasil-validasi-akurasi-cv.md`](hasil-validasi-akurasi-cv.md).

## LSTM agregat

- Input: 12 timestep × 5 detik (60 detik histori).
- Output artefak saat ini: 12 timestep × 5 detik (60 detik forecast).
- Fitur: vehicle count, queue vehicles, queue meters, dan density index.
- Holdout MAE agregat: **2,6180**.
- Baseline persistence MAE: **3,4159**.
- Status pada metadata: mengalahkan baseline agregat.

Error band API menggunakan prediksi ± MAE per fitur. Ini indikator empirical
error, bukan confidence interval statistik.

## LSTM per approach

- Model: shared approach LSTM dengan one-hot approach.
- Holdout overall MAE: **1,6528**.
- Baseline persistence MAE: **2,2973**.
- Sampel test per approach pada metadata hanya 4; generalisasi harus dibaca
  hati-hati.
- Fallback model agregat mengalokasikan hasil memakai recent approach share dan
  memberi label sumber fallback pada respons.

## PPO

- Engine default: rule-based.
- PPO hanya aktif melalui `SMARTTWIN_DECISION_ENGINE=ppo`.
- Kontrak observation: 21 fitur.
- Kontrak action: `MultiDiscrete([10, 10, 10, 10])` untuk empat lengan.
- Checkpoint yang tidak kompatibel ditolak dan otomatis fallback ke rule-based.
- Evaluasi v5 repository: menang 7, seri 2, kalah 0 pada sembilan perbandingan
  metrik 3-seed, tetapi fairness/respons per lengan masih menjadi keterbatasan.

Rujukan: [`hasil-evaluasi-ppo-v5.md`](hasil-evaluasi-ppo-v5.md).

## Aturan pembaruan

Setiap model baru harus mencatat:

- hash/versi dataset dan rentang waktunya;
- split train, validation, dan test tanpa leakage;
- konfigurasi model dan random seed;
- baseline pembanding;
- metrik keseluruhan dan per lengan/kelas;
- keterbatasan serta kondisi gagal;
- path checkpoint dan kompatibilitas kontrak runtime.

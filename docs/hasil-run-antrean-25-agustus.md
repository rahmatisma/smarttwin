# Hasil Run CV Antrean + Kesiapan Data LSTM — 25 Agustus 2026

Laporan run penuh `cv/vehicle_counter_pingit.py` ke seluruh rekaman 43 menit, dijalankan malam 25 Agustus dengan CUDA. Menutup item **1.2** di `pembagian-tugas-tahap-akhir.md` (Fase 2 LSTM: logika antrean CV) dan menyiapkan Fase 2 untuk Yuli.

**Ringkas: berhasil. Keempat fitur LSTM sekarang berisi data asli — `queueLengthVeh`/`queueLengthMEst` tidak lagi konstan nol.**

---

## 1. Run CV

```
perintah : cv/vehicle_counter_pingit.py --durasi 2602 --tanpa-tampilan
python   : e:\KMIPN 2026\venv-cuda  (torch 2.13.0+cu130)
GPU      : GTX 1650 SUPER, ~1900/4096 MiB, util 21-31%
durasi   : ~2,4 jam        exit code 0, NOL error
hasil    : 538 jendela penuh untuk keempat kamera
```

Catatan performa: GPU cuma terpakai ~25%. Hambatannya CPU (decode video + encode 4 video anotasi 1920×1088), bukan CUDA. Run pertama dengan tampilan aktif berjalan 3,7 jam; setelah `--tanpa-tampilan` turun ke 2,4 jam (**1,54× lebih cepat**). Menaikkan `--imgsz` atau apa pun di sisi GPU tidak akan membantu.

### Statistik kepadatan zona

| kamera | lengan | jendela | rata2 | min | max |
|---|---|---|---|---|---|
| CCTV_1 | selatan | 538 | 8.44 | 0.00 | 16.81 |
| CCTV_2 | simpang_tengah | 538 | 2.06 | 0.00 | 5.43 |
| CCTV_3 | barat | 538 | 6.48 | 0.83 | 9.73 |
| CCTV_4 | timur | 538 | 2.00 | 0.00 | 6.00 |

---

## 2. Antrean — hasil utama

`snapshot_zona.csv`: **10.452 baris**, 2613 detik unik, 49,1 menit (16:30:12 – 17:19:16), 2613 baris per lengan (seimbang sempurna), 0 NaN.

| lengan | zona | q_veh mean | q_veh max | q_m mean | q_m max | rasio antre |
|---|---|---|---|---|---|---|
| selatan | 8.47 | 6.56 | 17 | 18.22 | 45.0 | **77%** |
| barat | 6.54 | 2.80 | 10 | 12.17 | 41.0 | **43%** |
| timur | 2.01 | 0.92 | 4 | 4.05 | 20.0 | **46%** |
| simpang_tengah | 2.07 | 0.70 | 6 | 2.77 | 27.0 | **34%** |

**71% baris punya queue > 0.**

Kolom "rasio antre" (queue ÷ kehadiran zona) adalah bukti terkuat bahwa logikanya benar secara fisik, bukan sekadar menghasilkan angka: badan simpang paling rendah (**34%** — kendaraan di situ memang *melintas*, bukan menunggu), lengan pendekat jauh lebih tinggi (43–77%). Kalau logikanya asal, keempatnya akan mirip.

Cek aritmetika terpisah pada run pendek: barat = 1 lajur, 6 kendaraan (1 motor + 5 mobil) → (1×2) + (5×5) = **27 m**, cocok persis dengan `queue_length_m_est`.

---

## 3. Dataset LSTM

`forecasting/outputs/lstm/data_gabungan.csv` — **538 baris**, keempat fitur berisi data nyata:

| fitur | mean | std | min | max | nilai unik |
|---|---|---|---|---|---|
| `vehicleCount` | 8.260 | 3.405 | 0.000 | 19.000 | 20 |
| `queueLengthVeh` | 10.903 | 3.898 | 2.000 | 21.667 | **94** |
| `queueLengthMEst` | 22.211 | 6.683 | 3.800 | 41.000 | **150** |
| `densityIndex` | 0.144 | 0.033 | 0.038 | 0.221 | 110 |

Tidak ada kolom konstan, tidak ada NaN. Bandingkan dengan sebelumnya: `queueLengthVeh` dan `queueLengthMEst` keduanya `[0.]` — satu nilai unik.

CSV sumber juga disalin ke `forecasting/data/` sebagai **snapshot beku**, supaya data training tidak berubah diam-diam kalau CV dijalankan ulang. (`train.py` tidak punya argparse — path-nya konstanta keras ke folder itu.)

---

## 4. Perubahan kode

`prepare_data.py` **dan** `train.py`, tiga lokasi identik di masing-masing:

| Lokasi | Sebelum | Sesudah |
|---|---|---|
| `load_snapshot*()` | `groupby.mean()` hanya `total_di_zona` | queue ikut: **sum** (veh), **max** (meter) |
| `resample_snapshot()` | seleksi `["densityIndex"]` saja | queue ikut, **mean** (lintas-waktu) |
| `merge_datasets()` | `= 0.0` hardcode | pakai data asli + fallback |

**`train.py` ternyata punya logika merge duplikat sendiri** — membaca CSV mentah langsung, tidak memakai output `prepare_data.py` (itu dipakai `predict.py`). Kalau cuma `prepare_data.py` yang diperbaiki, training tetap belajar dari antrean nol — kegagalan senyap. Sudah ditulis peringatan di komentar kedua file: **kalau satu diubah, ubah keduanya.**

### Bukti uji

| Uji | Hasil |
|---|---|
| `prepare_data.py` hasilkan queue asli | queueVeh mean 12.123 · queueM max 41.000 |
| `train.py` hasilkan queue asli | queueVeh mean 12.123 · queueM max 41.000 |
| Kedua pipeline setara | **True** (identik sampai 3 desimal) |
| `vehicleCount`/`densityIndex` tidak berubah | **True** (identik dengan baseline) |
| Fallback CSV lama (tanpa kolom queue) | semua nol, **tanpa crash**, jumlah baris sama |
| `py_compile` kedua file | OK |

### ⚠️ Dua keputusan yang butuh konfirmasi Yuli

1. **`queueLengthVeh` pakai SUM antar-lengan, bukan mean.** Alasan "jangan hitung kendaraan yang sama dua kali" yang dipakai `densityIndex` **tidak berlaku** untuk antrean — kendaraan antre di selatan bukan kendaraan yang sama dengan yang antre di barat.
2. **`queueLengthMEst` pakai MAX, bukan sum.** Menjumlahkan *meter* antar-lengan tidak bermakna — itu empat antrean terpisah, bukan satu antrean panjang.

Pola sum/max ini mengikuti preseden `realtime_forecast_service.py` saat ia meruntuhkan seluruh approach jadi satu deret. Kalau tidak setuju, tiap kolom cuma satu kata untuk diganti.

---

## 5. Temuan yang BELUM diperbaiki

### 5.1 [PENTING] 24% deret latih tercemar lompatan waktu palsu

```
segmen kontinu : 10
panjang        : 117, 106, 92, 71, 46, 38, 24, 17, 15, 12 jendela
lubang >5 detik: 9        terpanjang: 65 detik

sequence cara SEKARANG (buta lubang) : 524
sequence yang benar-benar sahih      : 400
TERCEMAR                             : 124  →  24%
```

Rekaman 43 menit punya **15 lubang** (total 6,9 menit), terdokumentasi di `gap_gabungan` milik `cv/output/sync_report.json` — 9 di antaranya lolos ke dataset gabungan. `create_sequences()` di `train.py` menerima array numpy tanpa timestamp dan menggeser jendela atas indeks berurutan, jadi setiap deret yang melintasi lubang menyodorkan **jeda 26–65 detik kepada model seolah langkah 5 detik biasa**.

Ini **tidak berhubungan dengan perbaikan queue** — sudah ada sejak awal.

**Kenapa tidak saya perbaiki:** ini keputusan metodologi latih, bukan tambal bug — apakah deret lintas-lubang dibuang atau dilatih per-segmen, dan bagaimana interaksinya dengan pembagian train/val/test yang saat ini kronologis 70/15/15. Wilayah Yuli (item 2.2).

**Bentuk perbaikannya:** pecah dataframe jadi segmen kontinu **sebelum** scaling, panggil `create_sequences` per segmen, gabungkan hasilnya. Yang perlu dipikirkan justru pembagian train/val/test-nya.

### 5.2 Pembagian lajur lengan TIMUR kolaps — terkonfirmasi empiris

Rasio `m_est / queue_veh` pada baris dengan queue ≥ 3:

| lengan | lajur | n | rasio mean | tafsir |
|---|---|---|---|---|
| barat | 1 | 1409 | **4.33** | acuan "semua di satu lajur" |
| selatan | 2 | 1924 | **2.90** | jauh di bawah acuan → split **bekerja** ✓ |
| timur | 2 | 103 | **4.18** | praktis sama acuan → split **kolaps** ✗ |
| simpang_tengah | 2 | 70 | 3.43 | sebagian |

Sesuai prediksi dari geometri poligon: PCA di `_sumbu_lateral_zona()` sudah benar memilih *arah* sumbu, tapi banding lebar seragam berupa garis lurus tidak bisa mengikuti garis lajur yang mengerucut kalau bentuk quad-nya miring. CCTV_1 (selatan) batasnya kebetulan jatuh di tengah pada kedua ujung → bekerja. CCTV_4 (timur) miring → seluruh lebar jalan jatuh ke satu bucket.

Akibatnya `queue_length_m_est` timur **over-estimate ~1,4×**. Dampak praktisnya kecil: timur lengan sepi (103 dari 2613 baris punya queue ≥ 3), dan agregasi LSTM pakai MAX antar-lengan yang didominasi selatan.

Perbaikan sebenarnya butuh homografi 4 titik — di luar scope H-6. Alternatif murah: kalibrasi ulang poligon CCTV_4 agar simetris terhadap sumbu jalan, atau set `LAJUR_PER_LENGAN["timur"] = 1` dan terima estimasi konservatif.

### 5.3 `densityIndex` beda definisi antara training dan serving

| | rumus | rentang |
|---|---|---|
| training (`prepare_data.py`/`train.py`) | `total_di_zona / 33`, clip 0–1 | 0.038–0.221 |
| live (`cv_csv_bridge.py:145`) | `mean(total_di_zona)` mentah | bisa ~13.4 |

Selisih skala **~33×**. Kalau `TrafficState` live disuapkan langsung ke model terlatih, `MinMaxScaler` akan melempar nilainya jauh di luar rentang latih. Jalur serving (`forecast_service.py`) menerima records dari pemanggil, jadi **pemanggilnya yang wajib membagi 33**. Ini keputusan kontrak lintas-modul (backend + Supabase + frontend), bukan yang boleh saya putuskan sendiri.

---

## 6. Blocker environment yang ditemukan

### 6.1 `prepare_data.py` crash di Windows

`UnicodeEncodeError` pada [prepare_data.py:270](../forecasting/scripts/lstm/prepare_data.py#L270) — karakter `→` tidak bisa di-encode ke cp1252. Skrip gagal sebelum sempat apa-apa.

**Solusi tanpa ubah kode:**
```powershell
$env:PYTHONIOENCODING = "utf-8"
```

Sengaja tidak saya ubah string-nya karena ini murni soal environment, bukan logika.

### 6.2 `train.py` belum bisa jalan di venv mana pun

`scikit-learn` tidak ada di ketiganya (venv-cuda, cv/.venv, simulation/.venv), padahal `MinMaxScaler` dipakai inti.

```powershell
& "e:\KMIPN 2026\venv-cuda\Scripts\python.exe" -m pip install "pandas<3" scikit-learn joblib
```

**Perhatikan pin `pandas<3`** — pip default menarik pandas 3.0.5, lompatan mayor dari 2.x yang dipakai proyek ini (`simulation/.venv` = 2.3.3). `onnx` tidak perlu: export-nya sudah dibungkus `try/except`.

Sengaja tidak saya instal supaya tidak mengubah environment tanpa persetujuan.

---

## 7. Catatan lain

- **Upload HuggingFace: 2 dari 4 gagal** — `500 Internal Server Error` dari sisi HuggingFace, bukan kesalahan kode. Gagal dengan aman sesuai desain. Keempat video anotasi (~250 MB) tetap ada di `cv/output/`. Ulangi kalau perlu.
- **Backup CSV lama** ada di `cv/output/*.BAK.csv`, tapi isinya cuma hasil test run pendek (3 detik), bukan data 43 menit — data panjang yang lama sudah tertimpa sebelum sesi ini dan CSV-nya gitignored.
- `forecasting/outputs/*` gitignored — perlu `git add -f` kalau `data_gabungan.csv` mau dikomit sebagai bukti laporan.

---

## 8. Langkah berikutnya

**Yuli (Fase 2):**
1. Instal dependensi (6.2), set `PYTHONIOENCODING=utf-8` (6.1)
2. Konfirmasi keputusan agregasi sum/max (bagian 4)
3. Latih ulang dengan 4 fitur penuh — data sudah siap di `forecasting/data/`
4. Putuskan penanganan lubang waktu (5.1) — ini yang paling memengaruhi kualitas model
5. Update tabel status fitur di `rencana-lstm-forecast.md` bagian 2: `queueLengthVeh`/`queueLengthMEst` dari "SELALU 0" → "Data asli"

**Rahmat:**
- Pertimbangkan 5.2 (poligon CCTV_4) kalau angka timur dipakai untuk klaim di laporan teknis
- Angkat 5.3 (definisi `densityIndex`) ke rapat tim — ini kontrak lintas-modul

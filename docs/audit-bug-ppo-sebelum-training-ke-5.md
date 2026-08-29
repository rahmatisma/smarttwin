# Audit Bug PPO — Sebelum Training ke-5

**30 Agustus 2026, Rahmat.** Ditulis atas permintaan eksplisit: *"kalau sekarang
saya training ulang berarti training yang ke-5 kalinya — cari bug-bug lagi yang
mungkin ada, biar nggak ngulang-ngulang."*

Empat training sebelumnya (Yuli ~100k, v2 200k, v3 300k, v4 100k) semuanya
berakhir tidak terpakai. Dokumen ini hasil audit sistematis **seluruh jalur
PPO** — bukan cuma bagian yang kelihatan mencurigakan — supaya training ke-5
tidak jadi yang kelima yang terbuang.

**Semua angka di bawah hasil pengukuran langsung, bukan pembacaan kode saja.**

---

## Ringkasan

| # | Bug | Dampak | Wajib diperbaiki sebelum training ulang? |
|---|---|---|---|
| **E** | Reward throughput tidak dinormalkan terhadap waktu | Agent diberi insentif memperpanjang siklus tanpa memperbaiki apa pun | ✅ **YA** |
| **F** | Evaluasi membandingkan durasi simulasi tidak setara | Kita tidak bisa tahu training berhasil atau tidak | ✅ **YA** (perbaiki duluan — tidak perlu training) |
| **G** | Skala fitur `volume` 14× kebesaran (di PPO **dan** rule-based) | Hasil pengukuran CV praktis tidak memengaruhi keputusan | ✅ **YA** |
| **H** | Cap probabilitas injeksi memotong 9,9% permintaan | Kondisi puncak — yang paling penting — tidak pernah dialami agent | ✅ **YA** |
| **I** | Profil permintaan dibekukan sepanjang episode | Sampel 5 detik direntangkan jadi 30–40 menit simulasi | ✅ **YA** |
| **J** | 4 dari 25 fitur observasi konstan (one-hot fase) | 16% masukan model tidak berisi informasi apa pun | 🟡 Sebaiknya |
| **K** | Lingkungan training jauh lebih macet daripada data nyata | Model belajar untuk kondisi yang jarang terjadi | 🟡 Kemungkinan besar ikut beres kalau I diperbaiki |
| **L** | Nama checkpoint di-hardcode, bentrok antar-run | Sudah pernah bikin salah identifikasi checkpoint | 🟡 Kebersihan |

**Dua hipotesis yang saya uji dan TERNYATA BUKAN MASALAH** — dicatat supaya
tidak ada yang mengaudit ulang hal yang sama (bagian 9).

---

## Bug E — reward throughput tidak dinormalkan terhadap waktu

Sudah didokumentasikan di `hasil-evaluasi-ppo-v4-80k.md`. Ringkasnya:
`arrived` diakumulasi sepanjang jendela rotasi yang panjangnya **dipilih agent
sendiri** (76–256 detik), sedangkan antrean/tunggu cuma snapshot di akhir.

| Pola aksi | Durasi | Throughput mentah | Throughput/detik | Reward |
|---|---:|---:|---:|---:|
| Semua 15 dtk | 76 s | 46,8 | 0,615 | −0,0556 |
| Semua 30 dtk | 136 s | 91,2 | 0,671 | −0,0367 |
| Semua 60 dtk | 256 s | 167,5 | 0,654 | **+0,0851** |

Korelasi durasi ↔ reward: **+0,978**. Efisiensi tidak berubah, reward naik 3,6×.

**Perbaikan:** `throughput_norm = (arrived / window_seconds) / LAJU_MAKS`, dengan
`LAJU_MAKS` diukur ulang (dari data di atas, laju wajar ±0,65 kend/detik —
beri kepala ruang, mis. 1,0).

---

## Bug F — evaluasi membandingkan durasi simulasi tidak setara

Juga di `hasil-evaluasi-ppo-v4-80k.md`. `evaluate_ppo.py` menjalankan jumlah
**langkah** tetap, bukan **durasi** tetap; rule-based memilih siklus lebih
panjang sehingga mensimulasikan 18–20% lebih banyak detik.

| Seed | Throughput mentah | Throughput per detik |
|---|---:|---:|
| 1000 | −14,8% | **+1,0%** |
| 2000 | −9,7% | **+0,0%** |
| 3000 | −11,7% | **+2,2%** |

**Kerjakan ini PALING DULU** — murni metodologi, tidak perlu training ulang,
dan tanpa ini kita tidak punya cara menilai apakah training ke-5 berhasil.

---

## Bug G — skala fitur `volume` 14× kebesaran (PPO **dan** rule-based)

Nilai `volume` sebenarnya di data produksi (`crossing_simpang.csv`, per jendela
5 detik):

```
n=2152 | min 0 | maks 9 | rata-rata 2,07 | p95 = 6
```

Tapi normalisasinya:

- `ppo_features.py`: `FEATURE_SCALES["volume"] = 60.0`
- `rule_based_engine.py`: `REFERENCE_VOLUME = 30.0`

Akibatnya **94,2% nilai produksi jatuh di bawah 0,1** — terjepit di 10% bawah
rentang fitur. Diukur pada observasi training sungguhan, slot volume keempat
lengan: maks **0,0333**, rata-rata 0,0167.

Dampaknya ke rule-based lebih parah lagi, karena
`demand_score = max(volume_score, queue_score, density_score)` — kalau
`volume_score` selalu ~0,03 sementara yang lain mendekati 1, **volume tidak
pernah menentukan apa pun**. Diukur pada state SUMO nyata:

| Lengan | volume | v_score | queue | q_score | density | d_score | demand | penentu |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| north | 1 | 0,033 | 14 | 0,700 | 14 | **1,000** | 1,000 | density |
| east | 1 | 0,033 | 13 | 0,650 | 13 | **1,000** | 1,000 | density |
| south | 0 | 0,000 | 0 | 0,000 | 0 | 0,000 | 0,000 | (semua nol) |
| west | 1 | 0,033 | 2 | 0,100 | 15 | **1,000** | 1,000 | density |

**Ini penting di luar PPO:** akurasi deteksi CV yang susah payah divalidasi
(48,7%, item S-4) praktis **tidak memengaruhi keputusan durasi hijau**, karena
satuan `volume` tidak cocok dengan konstanta pembanding yang dipakai.

Dugaan penyebab: `REFERENCE_VOLUME=30` dan `FEATURE_SCALES=60` sama-sama masuk
akal untuk satuan **kendaraan/menit** (data mencapai 108 kend/menit), tapi field
`volume` yang benar-benar diisi itu **kendaraan per 5 detik**. Selisih satuan 12×.

**Perbaikan:** samakan satuannya — entah ubah skala jadi ~10 (maks teramati 9),
atau konversi `volume` ke kendaraan/menit sebelum masuk fitur. **Pilih satu dan
terapkan di kedua tempat** (PPO dan rule-based), jangan cuma salah satu.

⚠️ **Perhatian:** memperbaiki `REFERENCE_VOLUME` mengubah perilaku rule-based
yang sekarang dipakai produksi & demo. Uji ulang `pytest` dan bandingkan
keluaran Scenario Generator sebelum/sesudah — jangan diubah mendadak menjelang
rekaman.

---

## Bug H — cap probabilitas injeksi memotong permintaan puncak

`ppo_env.py::_inject_one_second()`:

```python
if self.rng.random() >= min(0.8, self.profile[approach] / 60.0):
```

`min(0.8, ...)` membatasi laju injeksi maksimum ke 0,8 kendaraan/detik =
**48 kendaraan/menit**. Terukur pada seluruh dataset:

- Permintaan tertinggi di data: **108 kend/menit** (2,2× cap)
- Lengan-jendela yang kena cap: **250 dari 2.152 (11,6%)**
- Total permintaan yang hilang: **9,9%**

Yang hilang justru **momen-momen tersibuk** — persis kondisi yang paling
menentukan kualitas pengaturan lampu. Agent tidak pernah melihatnya.

**Perbaikan:** naikkan/hapus cap. Kalau cap dipertahankan sebagai pengaman
numerik, taruh di atas maksimum teramati (mis. 2,0/detik), bukan di bawahnya.

---

## Bug I — profil permintaan dibekukan sepanjang episode

`reset()` menetapkan `self.profile` **satu kali**, lalu tidak pernah berubah:

```python
self.profile = self.profiles[actual_seed % len(self.profiles)]
```

Terukur — profil awal dan akhir episode identik:

```
profil awal : {'north': 36.0, 'east': 60.0, 'south': 0.0, 'west': 12.0}
profil akhir: {'north': 36.0, 'east': 60.0, 'south': 0.0, 'west': 12.0}
-> STATIS sepanjang episode
```

Padahal satu profil berasal dari **jendela 5 detik** data CV, sementara satu
episode = 12 langkah × 76–256 detik = **15–50 menit waktu simulasi**.

Jadi cuplikan 5 detik direntangkan jadi kondisi tetap selama setengah jam.
Konsekuensi konkretnya:

- **`south` bernilai 0 di 202 dari 430 profil training (47%).** Ketika terpilih,
  artinya "tidak ada satu pun kendaraan dari selatan selama 30 menit" — bukan
  "kebetulan tidak ada yang lewat dalam 5 detik ini". Agent tetap wajib
  mengalokasikan 15–60 detik hijau ke lengan yang benar-benar kosong.
- Observasi antar-langkah dalam satu episode nyaris tidak berubah → keragaman
  data training jauh lebih kecil daripada yang terlihat dari jumlah langkah.

**Perbaikan:** majukan indeks profil tiap langkah (`profiles[(idx + step) % n]`)
supaya permintaan bergerak mengikuti rekaman aslinya. Ini juga membuat episode
merepresentasikan **urutan waktu nyata**, bukan satu titik beku.

---

## Bug J — 4 dari 25 fitur observasi konstan

Diukur pada seluruh observasi satu episode:

```
[20] onehot.north   min 1.00 maks 1.00   <-- KONSTAN
[21] onehot.east    min 0.00 maks 0.00   <-- KONSTAN
[22] onehot.south   min 0.00 maks 0.00   <-- KONSTAN
[23] onehot.west    min 0.00 maks 0.00   <-- KONSTAN
```

Ini konsekuensi langsung `_sync_active_phase()` yang sekarang
`self.current_phase = FIXED_CYCLE_ORDER[0]` tanpa syarat — jadi one-hot-nya
**selalu** `[1,0,0,0]`, secara konstruksi.

Sudah ditulis sebagai "keterbatasan yang diketahui" di docstring, tapi belum
pernah diukur dampaknya: **16% masukan model tidak membawa informasi apa pun**,
sementara saat inference keempat nilai itu bervariasi. Model tidak punya
kesempatan belajar meresponsnya.

**Perbaikan (pilih satu):** (a) buang saja 4 fitur itu dari observasi — jujur
dan sederhana, tapi mengubah `OBSERVATION_SIZE` jadi 21 sehingga checkpoint lama
tidak kompatibel; atau (b) ubah satu langkah training = satu **fase** (bukan
satu rotasi penuh) supaya fase benar-benar bervariasi — lebih setara dengan
produksi tapi perubahan desain besar.

---

## Bug K — lingkungan training jauh lebih macet daripada data nyata

Perbandingan nilai nyata:

| Besaran | Data produksi (CV) | Lingkungan training (SUMO) |
|---|---|---|
| `queueLengthVeh` | rata-rata **2,7**, maks 17 | **13–14** |
| `densityIndex` | rata-rata **4,8**, maks 19 | **12–18** |

Training berlangsung pada kepadatan ±3× dan antrean ±5× lipat dibanding simpang
sungguhannya. Model belajar menangani kemacetan yang di data aslinya jarang
terjadi.

**Catatan kejujuran:** kedua besaran ini tidak diukur dengan cara yang persis
sama (produksi = kendaraan dalam zona kamera; training = kendaraan di 2 ruas
SUMO), jadi angkanya tidak 100% setara. Tapi keduanya **dimasukkan ke slot
fitur yang sama dengan skala yang sama**, jadi ketidakcocokannya tetap nyata.

**Dugaan (belum dibuktikan):** ini kemungkinan besar **akibat Bug I** —
permintaan 36–60 kend/menit yang ditahan konstan selama 30 menit pada ruas yang
hanya sanggup melepas ~20–39 kend/menit pasti menumpuk tanpa batas. Kalau Bug I
diperbaiki, ukur ulang sebelum memperlakukan K sebagai bug terpisah.

---

## Bug L — nama checkpoint di-hardcode (kebersihan)

`train_ppo.py`: `CheckpointCallback(..., name_prefix="smarttwin_ppo")` — tetap,
**tidak peduli nilai `--output`**. Jadi checkpoint v3 dan v4 memakai nama file
yang sama persis (`smarttwin_ppo_80000_steps.zip`) di folder yang sama, saling
menimpa.

Ini sudah pernah menimbulkan masalah nyata: kesulitan memastikan checkpoint mana
milik run mana (harus dibuktikan lewat `action_space.nvec` dan `num_timesteps`,
bukan nama file).

**Perbaikan:** turunkan `name_prefix` dari `--output` (mis. basename-nya), atau
simpan checkpoint ke subfolder per-run.

---

## 9. Yang sudah dicek dan TERNYATA BUKAN MASALAH

Dicatat supaya tidak ada yang mengaudit ulang hal yang sama.

**1. Teleport SUMO merusak hitungan crossing — TIDAK TERBUKTI.**
Hipotesis: `_hitung_crossing()` menghitung kendaraan yang hilang dari
`EDGE_MASUK` sebagai "melintas", jadi kendaraan yang di-teleport SUMO karena
macet akan salah terhitung. Diukur: **0 teleport** selama 8 langkah pengujian.
Tidak jadi masalah pada tingkat kepadatan sekarang. (Kalau Bug H diperbaiki dan
kepadatan naik, **ukur ulang** — hipotesis ini bisa jadi relevan lagi.)

**2. Kendaraan gagal diinjeksi dan hilang diam-diam — SALAH UKUR, bukan bug.**
Pengukuran pertama saya menunjukkan "2.030 diminta, 0 masuk (100% hilang)".
Itu **keliru**: `getLoadedNumber()` dan `getDepartedNumber()` bersifat
**sesaat** (hanya langkah simulasi terakhir), bukan kumulatif — kesalahan yang
sama persis seperti `getArrivedNumber()` yang hampir bikin saya melaporkan bug
palsu di evaluasi 80k. Diverifikasi ulang: kendaraan memang masuk simulasi
dengan normal.

**3. Perbaikan Bug A/B/D (29 Agustus) — MASIH BERTAHAN.**
0/24 saturasi antrean, 0/24 saturasi throughput, ketiga komponen reward hidup
dengan gradien. Tidak perlu dikerjakan ulang.

---

## 10. Urutan kerja yang disarankan untuk training ke-5

**Jangan mulai training sebelum langkah 1–2 selesai.**

1. **Bug F dulu** — perbaiki metodologi evaluasi. Tidak perlu training; langsung
   evaluasi ulang checkpoint 80k/100k yang sudah ada. **Ini yang menentukan
   apakah kita bahkan bisa menilai hasil training ke-5.**
2. **Bug G** — samakan satuan `volume` di `ppo_features.py` **dan**
   `rule_based_engine.py`. Uji regresi rule-based dulu (lihat peringatan di Bug G).
3. **Bug I + H** — profil bergerak per langkah, dan naikkan cap injeksi.
   Setelah ini, **ukur ulang** antrean/kepadatan untuk cek Bug K.
4. **Bug E** — normalkan reward throughput terhadap waktu, lalu **ukur ulang
   ambang saturasi** seperti waktu Bug B (jangan menebak angkanya).
5. **Bug J** — putuskan (a) atau (b). Kalau memilih (a), catat bahwa checkpoint
   lama jadi tidak kompatibel.
6. **Bug L** — 5 menit, kerjakan kapan saja.
7. Baru training ulang. **Jangan naikkan timestep** — plateau di ~40k sudah
   terukur dua kali (v2 dan v4); 100k masih lebih dari cukup.
8. **Evaluasi checkpoint 10k dulu** sebelum menunggu selesai, seperti yang sudah
   dilakukan di v4 — pola itu berhasil menangkap masalah lebih awal.

**Aturan berhenti tetap berlaku:** kalau setelah semua ini PPO tetap tidak
unggul secara sahih, jangan dipaksakan aktif. Kotak 10 tetap fungsional dengan
Scenario Generator, dan temuan-temuan di dokumen ini sendiri sudah jadi bahan
laporan teknis yang kuat — menunjukkan tim menguji metodologinya sendiri, bukan
sekadar menerima angka apa adanya.

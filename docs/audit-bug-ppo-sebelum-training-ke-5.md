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
| **G** | Skala fitur `volume` 14× kebesaran | ⚠️ **Sisi PPO: diperbaiki.** Sisi rule-based: divalidasi lewat SUMO, ternyata memperbaikinya justru **memperburuk** delay +3,9% & antrean +6,5% — TIDAK diubah | ✅ PPO saja |
| **H** | Cap probabilitas injeksi memotong 9,9% permintaan | Kondisi puncak — yang paling penting — tidak pernah dialami agent | ✅ **YA** |
| **I** | Profil permintaan dibekukan sepanjang episode | 🔴 **PALING PENTING.** Terukur: **92,1% episode training di atas kapasitas simpang**, 71,9% di atas 2× kapasitas. Insentif reward tidak bisa divalidasi sampai ini beres | ✅ **YA — kerjakan duluan** |
| **J** | 4 dari 25 fitur observasi konstan (one-hot fase) | 16% masukan model tidak berisi informasi apa pun | 🟡 Sebaiknya |
| **K** | Lingkungan training jauh lebih macet daripada data nyata | Model belajar untuk kondisi yang jarang terjadi | 🟡 Kemungkinan besar ikut beres kalau I diperbaiki |
| **L** | Nama checkpoint di-hardcode, bentrok antar-run | Sudah pernah bikin salah identifikasi checkpoint | 🟡 Kebersihan |
| **N** | Permintaan data CV (1,66 kend/dtk) melampaui kapasitas jaringan SUMO (~1,00) | Lingkungan training selalu jenuh, padahal simpang asli tidak (antrean nyata cuma 2,7 kendaraan) | 🔴 **YA — butuh keputusan pemodelan** |

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

### ✅ DIPERBAIKI 30 Agustus — dan menyingkap masalah yang jauh lebih besar

`THROUGHPUT_SATURATION_VEH = 200,0` (jumlah mentah) diganti
`THROUGHPUT_SATURATION_RATE = 1,0` (kendaraan/detik). Ambangnya **diukur**, tidak
ditebak — 5 profil permintaan × 3 panjang rotasi × 2 ulangan:

```
laju: min 0,158 | p50 0,475 | p95 0,669 | maks 0,679 | rata-rata 0,424
korelasi durasi vs LAJU          : +0,050   <- bias panjang siklus hilang
korelasi durasi vs jumlah mentah : +0,675   <- inilah bias yang diperbaiki
```

Ambang 1,0 memberi 0% saturasi, rata-rata ternormalisasi 0,424, maksimum 0,679
— menyisakan ~32% kepala ruang. Diverifikasi dengan mengulang pengujian yang
dulu menemukan bug ini: **korelasi durasi ↔ reward +0,978 → −0,983.**

### ⚠️ Tapi insentifnya BELUM bisa divalidasi — dan itu karena Bug I

Setelah diperbaiki, saya uji apakah reward barunya masuk akal. Dua pengujian
lanjutan memberi hasil yang mengkhawatirkan:

**1. Optimum ada di ujung terpendek.** Diuji hijau seragam 15→60 detik: reward
tertinggi di 15 detik (siklus 76 detik), menurun monoton sampai 60 detik. Agent
tidak punya alasan memilih apa pun selain hijau minimum.

**2. Alokasi proporsional permintaan KALAH dari bagi rata.** Pada total hijau
yang sama (120 detik), seed dengan permintaan timpang (U60/T24/S24/B72):

| Alokasi | Laju | Antrean | Reward |
|---|---:|---:|---:|
| Bagi rata `[30,30,30,30]` | 0,647 | 66,3 | **−0,0187** ← menang |
| Proporsional `[40,15,15,50]` | 0,686 | 109,7 | −0,1503 |
| Kebalikan `[20,45,45,15]` | 0,664 | 119,0 | −0,1813 |

Alokasi proporsional memberi throughput **lebih tinggi** tapi antrean jauh lebih
panjang, sehingga kalah. Urutannya benar (proporsional > kebalikan), tapi bagi
rata tetap menang.

**Akar penyebabnya BUKAN fungsi reward — melainkan Bug I.** Diukur pada 430
profil training, dibandingkan kapasitas simpang yang benar-benar terukur
(0,68 kend/detik):

| Kondisi | Jumlah profil | Porsi |
|---|---:|---:|
| Di bawah kapasitas (sehat) | 34 | **7,9%** |
| 1–2× kapasitas (jenuh) | 87 | 20,2% |
| **>2× kapasitas (macet total)** | **309** | **71,9%** |

**92,1% episode training berada di atas kapasitas simpang; rata-rata
permintaan 2,46× kapasitas.** Dalam kondisi macet total, pengaturan lampu
seperti apa pun tidak bisa mengatasi — antrean tetap tumbuh, dan keputusan
alokasi nyaris tidak berpengaruh.

Ini menjelaskan banyak hal sekaligus: kenapa kebijakan v4 memilih aksi yang
sama 54% waktu, kenapa reward-nya cepat mendatar, dan kenapa PPO paling buruk
justru di seed 3000 yang lalu lintasnya sepi (model tidak pernah berlatih di
kondisi lengang yang realistis).

**Konsekuensi untuk urutan kerja: Bug I WAJIB diperbaiki sebelum insentif
reward bisa dinilai sama sekali.** Perbaikan Bug E sendiri sudah benar dan tetap
diperlukan, tapi mengevaluasi apakah reward mendorong perilaku yang tepat tidak
mungkin dilakukan di lingkungan yang 92% macet total.


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

### ✅ HASIL VALIDASI SUMO (30 Agustus) — JANGAN ubah `REFERENCE_VOLUME`

Peringatan di atas dijalankan: Scenario Generator **sungguhan lewat SUMO** pada
6 snapshot tersebar (ramai s/d sepi), masing-masing dievaluasi dua kali dengan
`REFERENCE_VOLUME` 30 (sekarang) vs 10 (usulan perbaikan).

| Metrik | Sekarang (30) | Usulan (10) | Perubahan | Menang di |
|---|---:|---:|---:|---|
| Delay | 23,71 s | 24,64 s | **+3,9% LEBIH BURUK** | 0 dari 6 |
| Antrean | 72,33 m | 77,00 m | **+6,5% LEBIH BURUK** | 0 dari 6 |
| Throughput | 27,67 | 28,33 | +2,4% lebih baik | 2 dari 6 |

**Keputusan: `REFERENCE_VOLUME` TETAP 30. Jangan diubah.**

### Kenapa "memperbaiki" satuannya justru memperburuk

Ketidakcocokan satuannya nyata, tapi konsekuensi memperbaikinya tidak seperti
dugaan. Penyebabnya ada pada arti `volume` itu sendiri:

**`volume` = crossing = kendaraan yang SUDAH LEWAT, bukan yang sedang MENUNGGU.**
Lengan dengan crossing tinggi justru lengan yang sedang **lancar**; lengan yang
butuh hijau adalah yang **antreannya panjang**. Karena
`demand_score = max(volume_score, queue_score, density_score)`, menaikkan bobot
volume membuat lengan yang sudah lancar merebut hijau dari lengan yang macet —
persis kebalikan dari yang diinginkan.

Jadi perilaku sekarang (volume praktis diabaikan, keputusan ditentukan antrean &
kepadatan) **kebetulan sudah benar**, meski dicapai lewat konstanta yang salah
satuan. Ini "bug yang menyelamatkan", bukan bug yang harus diperbaiki.

**Yang harus dicatat di laporan teknis:** pengukuran CV (crossing) **memang
tidak memengaruhi keputusan durasi hijau** — dan itu **disengaja secara
fungsional**, karena crossing bukan indikator permintaan yang tepat. Antrean dan
kepadatan (`total_di_zona`) yang menentukan. Jangan tulis "volume ikut
menentukan durasi hijau" di laporan, karena tidak benar.

### Sisi PPO tetap diperbaiki (skala 60 → 10), dengan alasan berbeda

`FEATURE_SCALES["volume"]` **tetap diubah** ke 10 karena situasinya berbeda:
di PPO, volume adalah **masukan jaringan saraf**, bukan komponen `max()`.
Jaringan bebas memberi bobot berapa pun — termasuk mendekati nol — asalkan
fiturnya **bervariasi** dan bisa dipelajari. Dengan skala 60 fitur itu terjepit
di 3% bawah rentang dan praktis tidak bisa dipelajari sama sekali; dengan skala
10 jaringan punya kesempatan memutuskan sendiri seberapa penting volume.

⚠️ **Ini argumen, bukan hasil pengukuran.** Belum diuji apakah PPO dengan skala
baru benar-benar lebih baik — itu baru terjawab setelah training ke-5.


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

### ✅ DIPERBAIKI 30 Agustus

`_maju_profil()` memajukan profil satu langkah tiap `FEATURE_WINDOW_SECONDS`
(5) detik simulasi, jadi permintaan bergerak persis seperti rekaman CV aslinya.
Diukur, 5 seed × 6 langkah, aksi seragam 30 detik:

| | Beku (lama) | Bergerak (baru) |
|---|---:|---:|
| Laju throughput rata-rata | 0,435 | **0,645 (+48%)** |
| Antrean maksimum | 115,0 | **81,0 (−30%)** |
| Antrean rata-rata | 39,5 | 56,0 |
| Ragam permintaan dalam episode (sd) | 0,91 | 0,62 |

Throughput naik hampir setengah dan kemacetan ekstrem berkurang jelas — episode
tidak lagi terjebak di satu kondisi padat yang dibekukan.

**Tapi rasio permintaan/kapasitas masih 2,41×.** Bug I bukan satu-satunya
penyebab. Lihat Bug N.

---

## 🔴 Bug N (BARU, 30 Agustus) — permintaan dari data CV melampaui kapasitas jaringan SUMO

Ditemukan saat memverifikasi Bug I. Ini **bukan** bug kode, melainkan
ketidakcocokan antara data dan model simulasi — tapi dampaknya ke training
sama besarnya.

| Besaran | Nilai |
|---|---:|
| Permintaan rata-rata dari data CV | **1,66–1,74 kend/detik** |
| Kapasitas teoretis jaringan SUMO (8 lajur, siklus 4 fase) | **~1,00 kend/detik** |
| Throughput yang benar-benar tercapai di simulasi | **~0,65 kend/detik** |

Jaringan SUMO punya **2 lajur per lengan (8 total)**. Dengan saturation flow
lazim 0,5 kend/detik/lajur dan tiap lengan mendapat ¼ waktu siklus, kapasitas
teoretisnya ~1,00 kend/detik — **secara fisik tidak mungkin** melayani
permintaan 1,66 kend/detik yang diturunkan dari data CV.

Artinya lingkungan training akan **selalu** jenuh, seberapa pun bagusnya
pengaturan lampu. Padahal simpang aslinya jelas **tidak** jenuh — data CV
mencatat antrean rata-rata cuma **2,7 kendaraan** (maks 17).

### Kemungkinan penyebab (belum dipastikan)

1. **Simpang asli punya lebih banyak lajur** daripada yang dimodelkan jaringan.
2. **Sepeda motor menerobos dan memadat** melebihi saturation flow berbasis
   lajur — data CV mencatat **29,9% motor** (mobil 64,6%, bus 4,1%, truk 1,4%),
   sementara environment menyuntikkan **100% `smart_car`** (salinan
   `DEFAULT_VEHTYPE`, mobil 5 meter). Ini **pasti** menyumbang, tapi 30% motor
   saja tidak cukup menjelaskan selisih 2,4×.
3. Hitungan crossing CV melebihi jumlah kendaraan sebenarnya.

**Catatan sampingan:** batas kecepatan ruas masuk north & south terbaca
**100 km/jam** di jaringan — nilai jalan bebas hambatan, kemungkinan artefak
impor OSM. Perlu diperiksa terpisah.

### Pilihan penanganan

**Kalibrasi skala permintaan** adalah jalan paling pragmatis: kalikan profil
dengan faktor sehingga tingkat kejenuhan simulasi menyerupai simpang aslinya
(target terukur: antrean simulasi mendekati antrean nyata, rata-rata ±2,7
kendaraan). Yang penting untuk belajar mengatur lampu adalah **rasio
permintaan terhadap kapasitas**, bukan angka mutlaknya.

⚠️ **Ini keputusan pemodelan, bukan perbaikan bug** — harus disepakati dan
**ditulis terang-terangan di laporan teknis**, jangan disembunyikan.

### 🔬 DIAGNOSIS LANJUTAN (30 Agustus) — dua masalah terpisah, keduanya di jaringan

Pemeriksaan jaringan SUMO menemukan penyebabnya lebih spesifik dari sekadar
"kapasitas kurang". Ada **dua** hal:

#### N-1. Lajur lebih sedikit daripada yang dibutuhkan

2 lajur per lengan (8 total), 20 gerakan terkendali. Dengan saturation flow
lazim 0,5 kend/detik/lajur dan tiap lengan mendapat ¼ siklus:
kapasitas ≈ **1,00 kend/detik**, sementara permintaan dari data CV
**1,66 kend/detik**. Untuk melayaninya butuh **±3,3 lajur per lengan**.

#### N-2. Ruas pendekat terlalu pendek — kendaraan tidak bisa masuk sama sekali

Panjang ruas pendekat sangat timpang, dan north **tidak punya ruas apa pun di
belakangnya** (jalannya berhenti 62 m sebelum simpang di model):

| Lengan | Panjang ruas | Muat | Diminta | Melintas | Terlayani | Nyangkut tak bisa masuk |
|---|---:|---:|---:|---:|---:|---:|
| north | 62 m | 18 | 338 | 113 | 33% | **215** |
| east | 57 m | 16 | 281 | 115 | 41% | **169** |
| south | **522 m** | 149 | 172 | 133 | **77%** | 5 |
| west | 292 m | 83 | 432 | 160 | 37% | **233** |

**622 kendaraan tertahan di antrean penyisipan SUMO** — tidak pernah masuk
simulasi karena jaringannya tidak muat. Korelasinya jelas: lengan berruas
panjang terlayani 77%, yang terpendek cuma 33%.

**Yang paling berbahaya: 622 kendaraan itu tidak terlihat oleh PPO.** Mereka
tidak masuk hitungan antrean (`getLastStepHaltingNumber` hanya membaca ruas
yang ada), tidak masuk observasi, dan tidak masuk reward. Agent belajar di
dunia yang **menyembunyikan sebagian besar permintaannya sendiri**.

Ini juga berarti **metrik antrean selama ini undercount** — bukan cuma untuk
PPO, tapi untuk seluruh evaluasi berbasis `ppo_env`.

### Yang perlu diverifikasi manusia (tidak bisa saya cek sendiri)

**Berapa lajur sebenarnya tiap pendekat Simpang Pingit?** Cek lewat citra
satelit / Google Street View, hitung lajur di garis henti tiap lengan
(termasuk pelebaran/flare yang sering ada menjelang simpang).

- Kalau **3–4 lajur** → jaringan hasil impor OSM memang salah, dan jalan yang
  benar adalah **membangun ulang jaringan** dengan area lebih luas + jumlah
  lajur yang benar. Ini memperbaiki semua hasil simulasi, bukan cuma PPO.
- Kalau memang **2 lajur** → berarti hitungan crossing CV yang perlu ditinjau
  (kemungkinan overcount), dan kalibrasi skala permintaan jadi pilihan yang
  sah.

**Petunjuk tambahan bahwa impor OSM-nya bermasalah:** batas kecepatan ruas
masuk north & south terbaca **100 km/jam** — nilai jalan bebas hambatan, mustahil
untuk pendekat simpang dalam kota.


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

---

## 🔴 Bug O (BARU, 30 Agustus) — permintaan dihitung 2× karena garis CV memotong kedua arah

**Ini akar penyebab terbesar dari Bug N, dan ditemukan karena pertanyaan yang
tepat: "kok angkanya besar sekali?"**

`jumlah_crossing` di `crossing_simpang.csv` menghitung kendaraan yang melintasi
garis **ke arah mana pun**. Di `cv/vehicle_counter_pingit.py`:

```python
if sisi_lama * sisi_baru < 0:      # cuma cek PINDAH SISI
    akum["total"] += 1             # tidak ada filter arah
```

Perilaku ini **disengaja untuk CV** dan sudah didokumentasikan di
`hasil-validasi-akurasi-cv.md` ("kedua arah lalu lintas dihitung").

Masalahnya muncul saat angka itu dipakai sebagai **permintaan pendekat** oleh
`load_demand_profiles()`. Jalan pendekat Simpang Pingit **dua arah** —
diverifikasi geometris pada jaringan SUMO:

| Lengan | Jarak ruas masuk ↔ ruas keluar | Beda arah | Kesimpulan |
|---|---:|---:|---|
| north | **29,1 m** | **180°** | jalan yang sama, dua arah |
| east | **28,4 m** | **179°** | jalan yang sama, dua arah |

Jadi satu garis hitung memotong **dua arus sekaligus**: kendaraan yang MASUK ke
simpang dan yang KELUAR dari simpang. Memakainya mentah sebagai permintaan
pendekat **menggandakan angkanya**.

### Bukti kecocokan

| | Sebelum dibagi 2 | Sesudah dibagi 2 |
|---|---:|---:|
| Permintaan total | 90,5 kend/menit = **1,66 kend/detik** | 45,3 = **0,75 kend/detik** |
| Kapasitas jaringan SUMO | ~1,00 kend/detik | ~1,00 kend/detik |
| Status | **di ATAS kapasitas → macet permanen** | **di BAWAH kapasitas** ✓ |

Versi yang sudah dibagi konsisten dengan kenyataan lapangan: data CV mencatat
antrean nyata rata-rata cuma **2,7 kendaraan** — simpang aslinya jelas tidak
jenuh.

### Hasil setelah diperbaiki (diukur)

| | Sebelum Bug O | Sesudah |
|---|---:|---:|
| Terlayani north | 33% | **56%** |
| Terlayani east | 41% | **73%** |
| Terlayani south | 77% | **84%** |
| Terlayani west | 37% | **55%** |
| Kendaraan nyangkut tak bisa masuk | 622 | **176 (−72%)** |
| Antrean rata-rata | 56,0 | 42,2 |

⚠️ **Pembagi 2 adalah TAKSIRAN, bukan pengukuran** — mengasumsikan arus masuk
dan keluar kira-kira seimbang. Perbaikan yang benar adalah **memfilter arah di
`hitung_crossing()`** sehingga `volume` berarti arus masuk saja. Itu mengubah
keluaran CV produksi, jadi belum dikerjakan.

### ⚠️ Masalahnya BELUM tuntas

Setelah Bug O diperbaiki, antrean simulasi masih **42,2 kendaraan** vs
**2,7 di lapangan** — masih ~15× lipat, dan 176 kendaraan tetap tidak bisa
masuk. Jadi Bug N-1 (kurang lajur) dan N-2 (ruas terlalu pendek) **tetap
berlaku** dan masih perlu verifikasi jumlah lajur asli.

---

## 📋 STATUS AKHIR — siap untuk training ke-5 (30 Agustus)

Arahan pembimbing: *"simulasikan saja, tidak harus sempurna dan sesuai sekali."*
Itu menyederhanakan keputusan — **jaringan SUMO tidak dibangun ulang**, cukup
permintaannya dikalibrasi. Yang tetap wajib dibereskan adalah **kejenuhan
permanen**, karena itu bukan soal kemiripan dengan lapangan melainkan soal
PPO punya sesuatu untuk dipelajari atau tidak.

| Bug | Status |
|---|---|
| **E** reward throughput tidak dinormalkan waktu | ✅ Diperbaiki — korelasi durasi↔reward +0,978 → −0,983 |
| **F** evaluasi durasi tidak setara | ✅ Diperbaiki — skew 18–20% → 1,9–4,7% |
| **G** skala `volume` salah satuan | ✅ Sisi PPO diperbaiki (60→10). Sisi produksi **sengaja tidak diubah** — divalidasi SUMO, memperbaikinya justru memperburuk delay +3,9% |
| **H** cap injeksi memotong permintaan | ✅ **Hilang sendiri** setelah kalibrasi — yang kena cap 11,6% → **0,00%** |
| **I** profil permintaan dibekukan | ✅ Diperbaiki — throughput +48%, antrean maksimum −30% |
| **J** 4 fitur observasi konstan | ✅ Dihapus, observasi 25 → 21 fitur (+1 test regresi) |
| **K/N** lingkungan jenuh permanen | ✅ Ditangani lewat kalibrasi `SKALA_PERMINTAAN = 0,40` (diukur, bukan ditebak) |
| **L** nama checkpoint bentrok antar-run | ✅ Diperbaiki — diturunkan dari `--output` + subfolder per-run |
| **O** permintaan terhitung 2× (garis CV dua arah) | ✅ Diperbaiki — nyangkut tak bisa masuk 622 → 176 |

**Verifikasi:** `pytest backend/` = **91 passed**, 1 gagal (checkpoint lama
tidak kompatibel — memang begitu, observasi berubah 25→21; beres sendiri
setelah training ulang). Smoke test training 600 langkah berjalan penuh dan
menghasilkan model `Box(21,)` + `MultiDiscrete([10 10 10 10])` yang benar.

### Yang TIDAK diperbaiki, dan alasannya

- **N-1 (kurang lajur) & N-2 (ruas pendekat pendek)** — akar masalahnya ada di
  jaringan hasil impor OSM. Tidak dibangun ulang sesuai arahan pembimbing;
  dampaknya ditangani lewat kalibrasi permintaan.
- **Antrean simulasi (16,6) masih di atas antrean lapangan (2,7)** —
  disadari dan diterima. Kalibrasi mengejar lingkungan yang bisa dipelajari,
  bukan replika lapangan.
- **Arah crossing belum difilter di CV** — pembagi 2 masih taksiran. Perbaikan
  benar-nya mengubah keluaran CV produksi, jadi ditunda.

### Kalimat untuk laporan teknis

> "Permintaan lalu lintas pada lingkungan pelatihan dikalibrasi agar tingkat
> kejenuhan simpang simulasi berada pada rentang operasional yang wajar.
> Kalibrasi diperlukan karena jaringan hasil impor OpenStreetMap memodelkan
> lebih sedikit lajur dan ruas pendekat yang lebih pendek daripada simpang
> sebenarnya, sehingga permintaan lapangan apa adanya menghasilkan kondisi
> jenuh permanen yang justru tidak merepresentasikan kondisi nyata — antrean
> terukur di lapangan rata-rata hanya 2,7 kendaraan."

**Jangan** menulis "simulasi merepresentasikan Simpang Pingit secara akurat".
Tulis: "simulasi berbasis geometri Simpang Pingit dengan permintaan
terkalibrasi".

---

## 🔴 Bug P (BARU, 30 Agustus) — training v5 dihentikan di checkpoint 30k: reward tidak bisa mendeteksi lengan yang ditelantarkan

**Training v5 (dijalankan Rahmat) dihentikan manual di 30.000/100.000 langkah**
setelah pemantauan tiap-10k menemukan pola yang memburuk secara konsisten:

| Checkpoint | Aksi dominan | Korelasi permintaan (Spearman) |
|---|---:|---:|
| 10k | 46% | — |
| 20k | 50% | +0,083 |
| 30k | **83%** | **−0,133** |

Diverifikasi dengan uji terkontrol: dipaksa 3 skenario permintaan EKSTRIM
(satu lengan=40, tiga lainnya=0), model 30k mengeluarkan **aksi yang persis
sama** di ketiganya — sama sekali tidak membaca observasi permintaan.

### Akar penyebab

`_metrics()` menghitung `queue` sebagai **jumlah 4 lengan digabung** —
`sum(getLastStepHaltingNumber(...) for a in FIXED_CYCLE_ORDER)`. Secara
matematis ini tidak bisa membedakan "4 lengan masing-masing antre 2" dari
"1 lengan antre 8, 3 lengan kosong" — keduanya sama-sama total 8.

Dikombinasikan dengan kalibrasi permintaan (Bug K/N, `SKALA_PERMINTAAN=0,40`)
yang membuat lalu lintas ringan, siklus pendek TETAP sudah cukup menjaga total
antrean rendah tanpa perlu tahu lengan mana yang sibuk. PPO menemukan jalan
pintas itu dan berhenti belajar mengalokasikan secara adaptif — bukan karena
gagal belajar, tapi karena berhasil mengoptimalkan reward yang ternyata tidak
menuntut perilaku adaptif sama sekali.

### Perbaikan

Tambah komponen reward baru berbasis lengan **TERBURUK**
(`max_queue_lengan`), terpisah dari `queue_penalty` berbasis total:

```
FAIRNESS_REWARD_WEIGHT = 0,10   (QUEUE_REWARD_WEIGHT diturunkan 0,35 -> 0,25)
MAX_QUEUE_LENGAN_SATURATION_VEH = 20,0   (diukur: p50=7, p95=12, maks=15)
```

**Terverifikasi lewat 2 uji terkontrol:**

1. **Kasus ekstrem (satu lengan 40, lainnya 0):** mengutamakan lengan sibuk
   sekarang **menang telak** — reward +0,0765 vs bagi rata +0,0073 vs sengaja
   diabaikan −0,0180. `fairness_penalty` turun dari 0,040 ke 0,015 saat lengan
   sibuk diprioritaskan, naik ke 0,053 saat diabaikan.
2. **Kasus skew sedang (rasio ±2:1 dari data nyata):** bagi rata masih
   menang. **Ini bukan bug** — diverifikasi penyebabnya `wait_penalty`, bukan
   fairness: memberi satu lengan porsi besar (mis. 60 dari total 120 detik)
   membuat lengan lain menunggu lebih lama menyaksikan satu fase panjang
   berjalan, menaikkan waktu tunggu sistem secara keseluruhan. Untuk skew
   sedang, alokasi mendekati rata memang bisa jadi pilihan yang masuk akal
   secara teknik lalu lintas, bukan cuma jalan pintas.

### Status: smoke test 20k sedang diverifikasi sebelum training penuh ulang

Sebelum melanjutkan ke training 100k, dijalankan dulu training singkat (20k
langkah) untuk memastikan perilaku terkunci-ke-satu-aksi benar-benar hilang
dengan reward baru, bukan cuma menang di kasus buatan tangan.

### ⚠️ Revisi 1 GAGAL — smoke test 20k membuktikan max() tidak cukup

Hasil smoke test (checkpoint 20k, reward pakai `max_queue_lengan`):

- Keragaman aksi TETAP terkunci: 2 kombinasi dari 24 langkah (71%/29%)
- Korelasi permintaan TETAP negatif: −0,083
- Uji ekstrem TETAP gagal: lengan dengan permintaan 40 tetap cuma dapat hijau
  terpendek (15 detik)
- **Temuan baru yang memberatkan:** `explained_variance = −0,113` (negatif —
  fungsi nilai PPO lebih buruk daripada asal tebak rata-rata). Training
  manapun sebelumnya di titik yang sebanding selalu positif.

Diagnosis: `max()` melompat setiap kali lengan "terburuk" berpindah antar
langkah -- sinyal patah yang membuat fungsi nilai kesulitan belajar, sehingga
gradiennya tidak sampai memperbaiki kebijakan meski komponennya sendiri benar
di uji-pasangan sederhana.

### Revisi 2 — jumlah kuadrat antrean per lengan (lebih halus)

Diukur (5 seed x 3 panjang rotasi): `Σq²` per langkah -- min 14, p50 76,
p95 155, maks 347, rata-rata 87,9. `QUEUE_KUADRAT_SATURATION = 500,0`
(~44% kepala ruang di atas maksimum teramati).

Dipilih karena secara matematis tetap menghukum konsentrasi di satu lengan
lebih keras daripada sebaran rata (untuk total antrean Q yang sama, Σq²
minimum saat merata, maksimum saat terkumpul di satu lengan) tapi berubah
HALUS seiring antrean bergeser antar lengan, bukan melompat seperti max().

Uji ekstrem diulang: NORTH DIUTAMAKAN masih menang jelas (+0,0885 vs bagi rata
+0,0270 vs sengaja diabaikan +0,0082) -- selisihnya sebanding dengan versi
max(), jadi daya bedanya tidak berkurang, cuma jadi lebih halus.

**Status: smoke test 20k kedua sedang berjalan untuk verifikasi nyata.**

### ⚠️ Revisi 2 JUGA GAGAL — jumlah kuadrat tidak lebih baik dari max()

Hasil smoke test kedua (checkpoint 20k, reward pakai `queue_kuadrat`):

- Keragaman aksi TETAP terkunci: 2 kombinasi dari 24 langkah (75% -- malah
  sedikit lebih terkonsentrasi dari revisi 1)
- Korelasi permintaan membaik tipis tapi masih lemah: −0,083 → **+0,125**
- Uji ekstrem TETAP gagal identik: west permintaan 40 tetap cuma 15 detik
- `explained_variance` justru LEBIH negatif: **−0,223** (dari −0,113)

### Diagnosis diperbarui: bukan bentuk reward, tapi eksplorasi berhenti terlalu cepat

Dua bentuk reward yang BERBEDA (max vs kuadrat) menghasilkan tingkat kuncian
yang HAMPIR SAMA, dan `entropy_loss` juga hampir identik di keduanya
(−5,04 vs −5,09). Ini petunjuk kuat bahwa masalahnya bukan di bentuk fungsi
reward -- kedua bentuk sudah terbukti benar secara matematis di uji-pasangan
terkontrol -- melainkan **PPO berhenti mengeksplorasi sebelum sempat
menemukan & mengeksploitasi sinyal fairness itu**.

### Revisi 3 — naikkan `ent_coef` (bonus eksplorasi PPO)

`ent_coef` sebelumnya di-hardcode 0,01 di `train_ppo.py`, sekarang jadi
argumen `--ent-coef` (default tetap 0,01). Smoke test dengan **0,05** (5x
lipat) sedang berjalan untuk menguji apakah menambah eksplorasi memecah
kuncian ini -- pendekatan standar PPO untuk "kebijakan terkunci ke sedikit
aksi", berbeda dari 2 revisi sebelumnya yang mengutak-atik bentuk reward.

### Revisi 3 — hasil 20k/50k/60k, dan kenapa akhirnya DITERIMA sebagai keterbatasan

Smoke test 20k (ent_coef=0,05, reward tetap `queue_kuadrat` dari revisi 2 --
keduanya berjalan BERSAMA, bukan bergantian) sempat menjanjikan: keragaman
aksi naik ke 5 kombinasi (67% dominan, turun dari 71-83%), korelasi membaik
ke +0,175 (terbaik sejauh itu). Checkpoint ini kemudian di-*resume* (bukan
dilatih ulang dari nol) ke 50k lalu 60k dengan pemantauan per-10k yang sama:

| Checkpoint | `entropy_loss` | `explained_variance` | Kombinasi aksi dominan | Korelasi | Uji ekstrem (utara/timur/selatan/barat) |
|---|---:|---:|---:|---:|---|
| 20k | −6,68 | −0,115 | 5 kombinasi, 67% | +0,175 | 0/3 benar |
| 50k | −4,56 | **+0,113** (pertama positif) | 7 kombinasi, 54% | +0,133 | 1/3 -- utara benar |
| 60k | −4,62 → −4,72 | +0,164 → +0,201 | 6 kombinasi, **75%** | **−0,083** | 1/3 -- utara benar, sama persis dgn 50k |

**Training dihentikan manual di 60k** setelah pola ini terbaca: `explained_
variance` naik terus di sepanjang 20k→60k, tapi itu SEJALAN dengan kebijakan
yang makin mengunci ke pola tetap (dominasi kombinasi aksi naik lagi dari
54%→75% di 10k terakhir), bukan sejalan dengan kebijakan menjadi lebih
responsif ke permintaan. Korelasi permintaan-aksi tidak pernah stabil positif
kuat di checkpoint manapun (rentang −0,083 s/d +0,175, semuanya lemah dan
naik-turun tak beraturan tanpa tren jelas).

**Kesimpulan setelah membandingkan seluruh 5 percobaan (max-based, kuadrat,
kuadrat+ent_coef di 20k/50k/60k):** uji ekstrem gagal dengan pola yang
**identik** di semuanya -- lengan barat dan selatan tidak pernah menang
perlakuan ekstrem, di percobaan manapun, dengan reward shaping apapun. Hanya
lengan utara yang pernah "menang", dan baru muncul setelah entropi dinaikkan.
Konsistensi kegagalan lintas 5 percobaan yang berbeda mekanismenya (2 bentuk
reward + 1 hyperparameter berbeda) adalah indikasi kuat ini **bukan** salah
tuning, melainkan keterbatasan struktural: utara adalah lengan dengan service
rate terburuk di jaringan (Bug N-2, 56% vs 73-84% lengan lain, akibat panjang
edge & tidak ada edge hulu) -- kemungkinan sinyal struktural ini secara
konsisten mengalahkan sinyal permintaan instan dalam kontribusinya ke reward,
sehingga kebijakan yang hampir tanpa syarat mengutamakan utara memang
mendekati optimal untuk fungsi reward saat ini, bukan cacat pembelajaran.

**Keputusan (Rahmat, 30 Agustus, setelah melihat tabel perbandingan lengkap):
diterima sebagai keterbatasan yang didokumentasikan, bukan dikejar lebih
jauh.** Sesuai arahan dosen pembimbing ("simulasikan saja, tidak harus
sempurna") dan mengingat 4 percobaan perbaikan berbeda sudah gagal dengan pola
kegagalan yang sama, sisa waktu menjelang presentasi dialokasikan ke evaluasi
resmi dan penulisan laporan, bukan iterasi ke-5.

**Checkpoint 60k dipromosikan jadi `decision_engine/models/smarttwin_ppo_v5.zip`**
(disalin dari `checkpoints/smoke_entcoef/smoke_entcoef_60000_steps.zip`) dan
menggantikan `decision_engine/models/smarttwin_ppo.zip` (path default yang
dipakai `PPOEngine`). Penggantian ini sekaligus memperbaiki bug terpisah yang
baru ketahuan: `smarttwin_ppo.zip` yang lama adalah checkpoint v1 dari SEBELUM
Bug J diperbaiki (ruang observasi 25 fitur, bukan 21), sehingga
`test_real_checkpoint_reaches_recommendation_endpoint` gagal diam-diam --
`PPOEngine` jatuh ke `ppo-fallback-rule-based` di setiap pemanggilan tanpa
error yang terlihat. Setelah diganti checkpoint v5, `pytest backend/tests/`
kembali 92/92 lulus.

### Hasil evaluasi resmi v5 (checkpoint 60k, 3 seed, `evaluate_ppo.py` yang sudah diperbaiki Bug F)

| Metrik | Seed 1000 | Seed 2000 | Seed 3000 |
|---|---|---|---|
| `mean_queue_veh` | **−46,4%** menang | **−46,7%** menang | **−50,6%** menang |
| `mean_wait_per_vehicle_s` | **−62,8%** menang | **−60,2%** menang | **−63,2%** menang |
| `throughput_veh_per_hour` | **+2,18%** menang | −0,70% seri | −0,58% seri |
| Ringkasan | menang 3/3, gate lulus | menang 2, seri 1 | menang 2, seri 1 |

**Totalnya, 9 perbandingan: menang 7, seri 2, kalah 0.** PPO **tidak pernah
kalah** pada metrik lalu lintas manapun di seed manapun -- lompatan besar dari
hasil v4 (menang 3, kalah 4, seri 2). Detail lengkap ada di
`docs/hasil-evaluasi-ppo-v5.md`.

**Catatan penting supaya tidak disalahpahami:** hasil bagus ini TIDAK berarti
Bug P selesai. Kemungkinan besar penjelasannya adalah kebalikan dari yang
diharapkan -- kebijakan yang hampir tanpa syarat memprioritaskan utara
(lengan paling parah dilayani jaringan) ternyata memang strategi pengaturan
sinyal yang secara global jauh lebih baik daripada rule-based, TERLEPAS dari
apakah ia benar-benar responsif ke fluktuasi permintaan per siklus. Bagus
untuk throughput/antrean sistem, tapi belum tentu adil per-lengan saat
kondisi menyimpang jauh dari pola rata-rata yang dipelajari. Ini harus
disebutkan eksplisit di laporan teknis, bukan diklaim sebagai "PPO belajar
alokasi adaptif".

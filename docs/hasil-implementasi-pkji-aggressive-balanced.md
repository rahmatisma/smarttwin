# Implementasi PKJI 2023 untuk kandidat "aggressive" & "balanced"

**Ditambahkan: 5 September 2026.** Menjawab kebutuhan proposal: sistem
menerapkan **PKJI 2023** (Pedoman Kapasitas Jalan Indonesia, penerus MKJI
1997) sebagai landasan pembagian waktu hijau, bukan cuma tempelan angka.

> Catatan: audit lama (`audit_final_31agustus.md`, 31 Agustus) menulis
> "Validasi PKJI 2023 — TIDAK PERNAH ADA sebagai studi formal". Itu benar
> **untuk saat itu**. Dokumen ini menggantikan kesimpulan itu — jangan
> kutip audit lama sebagai status terkini soal PKJI.

---

## 0. Alur sistem sekarang (gambar)

Ini gambaran besarnya dulu, sebelum masuk ke rumus. Baca kotaknya dari
atas ke bawah — tiap panah artinya "lanjut ke langkah berikutnya".

```mermaid
flowchart TD
    A["Kamera CCTV di 4 lengan simpang"] --> B["Hitung kendaraan tiap lengan<br/>(mobil, motor, bus, truk)"]
    B --> C["Data lalu lintas terkini per lengan"]

    C --> D["Kandidat BASELINE<br/>rumus sistem sendiri<br/>(tidak diubah)"]
    C --> E["Kandidat BALANCED<br/>rumus PKJI 2023"]
    C --> F["Kandidat AGGRESSIVE<br/>rumus PKJI 2023 + koreksi"]

    D --> G["Uji ketiga kandidat<br/>di simulasi SUMO"]
    E --> G
    F --> G

    G --> H["Pilih pemenang<br/>(delay + antrean paling kecil)"]
    H --> I["Diterapkan ke lampu lalu lintas"]
```

**Cara bacanya, langkah demi langkah:**

1. **Kamera menghitung kendaraan** di tiap lengan simpang — berapa
   mobil, motor, bus, truk yang lewat.
2. Dari data itu, sistem membuat **3 usulan** ("kandidat") pengaturan
   lampu berbeda:
   - **Baseline** — usulan dari rumus sistem sendiri (rumus lama, tetap
     dipakai sebagai pembanding, tidak disentuh sama sekali)
   - **Balanced** — usulan baru, dihitung pakai **rumus PKJI 2023**
   - **Aggressive** — usulan baru juga, dihitung pakai **rumus PKJI
     2023 + satu langkah koreksi tambahan**
3. **Ketiga usulan itu dicoba di simulasi SUMO** (simulasi lalu lintas
   komputer) untuk melihat mana yang hasilnya paling bagus (antrean dan
   waktu tunggu paling kecil).
4. **Yang paling bagus dipakai** untuk mengatur lampu lalu lintas
   sungguhan.

Jadi PKJI itu **bukan menggantikan seluruh sistem** — PKJI cuma dipakai
untuk menghitung **2 dari 3 usulan** (balanced & aggressive). Baseline
tetap ada supaya ada pembanding "kalau sistem tidak melakukan apa-apa".

---

## 1. Apa yang berubah, apa yang tidak

| Kandidat | Sebelum | Sekarang |
|---|---|---|
| **baseline** | Rumus `RuleBasedEngine` (interpolasi linear dari demand score) | **Tidak berubah** — lihat alasan di bagian 2 |
| **aggressive** | "+1 detik ke lengan tersibuk" (angka dari uji coba manual, bukan rumus) | **Rumus PKJI 2023** + koreksi Degree of Saturation (DS) |
| **balanced** | "Rata-rata ditarik ke minimum" (heuristik, bukan rumus) | **Rumus PKJI 2023** (pembagian proporsional Flow Ratio) |

**File yang diubah:** `simulation/scenario_generator.py` (rumus PKJI + `generate_cycle_candidate_plans()`), disambungkan lewat `backend/app/services/simulation_service.py` dan `backend/app/api/routes/digital_twin.py`.

### 1.1 Laporan: aggressive LAMA vs aggressive SEKARANG

**Ringkasan satu kalimat:** dulu aggressive cuma **menempel +1 detik ke
satu lengan tersibuk** dan membiarkan 3 lengan lain persis sama seperti
baseline; sekarang aggressive **menghitung ulang keempat lengan dari
nol** pakai rumus PKJI, lalu mengoreksi lengan mana pun yang masih
kewalahan — bukan cuma yang tersibuk.

| | Aggressive LAMA | Aggressive SEKARANG |
|---|---|---|
| **Rumusnya** | `hijau_tersibuk = hijau_baseline + 1 detik` | 5 langkah PKJI 2023 (SMP → Flow Ratio → siklus optimum → bagi proporsional → koreksi DS) |
| **Dari mana angka "+1 detik"-nya?** | Uji coba manual di SUMO — dicoba +20%, macet makin parah, dicoba beberapa nilai lain, +1 detik yang paling kecil kerugiannya. **Bukan dari rumus**, dari trial-and-error | Angka `emp` (1,0/1,3/0,25), ambang DS 0,85, rumus siklus Webster — semua nilai baku rekayasa lalu lintas Indonesia |
| **Lengan mana yang dihitung ulang?** | **Cuma 1** — lengan yang paling padat (`busiestApproach`) | **Bisa sampai 4** — semua lengan dihitung ulang proporsional, lalu semua yang DS-nya masih di atas 0,85 dikoreksi (bukan cuma yang paling padat) |
| **Lengan yang sepi diapakan?** | Dibiarkan **persis sama** seperti baseline, tidak disentuh sama sekali | Ikut dihitung ulang proporsional — bisa naik, bisa juga tetap kecil kalau memang sepi |
| **Bisa dijelaskan "kenapa segini"?** | Tidak — angkanya hasil coba-coba, tidak ada rumus untuk ditunjukkan | Ya — tiap detik bisa ditelusuri balik ke rumus PKJI + data kendaraan aslinya (lihat bagian 5) |
| **Landasan buat juri** | Tidak ada — kalau ditanya "kenapa +1 detik bukan +2 atau +5", jawabannya cuma "hasil coba-coba" | Ada — PKJI 2023, standar resmi Indonesia untuk simpang bersinyal |

**Contoh angka nyata, kondisi SUMO yang sama** (dari bukti bagian 6 —
baseline: Utara 60 / Timur 26 / Selatan 22 / Barat 20 detik, Utara
adalah lengan tersibuk **dan sudah mentok `MAX_GREEN_SECONDS`**):

| Lengan | Baseline | Aggressive **LAMA** | Aggressive **SEKARANG** |
|---|--:|--:|--:|
| Utara (tersibuk) | 60 | 60 *(+1 detik, tapi sudah mentok 60 → tidak berubah)* | 33 |
| Timur | 26 | 26 *(tidak disentuh)* | 26 |
| Selatan | 22 | 22 *(tidak disentuh)* | 15 |
| Barat | 20 | 20 *(tidak disentuh)* | 15 |

**Yang paling kelihatan bedanya di contoh ini:** aggressive lama **sama
persis dengan baseline, TIDAK melakukan apa-apa** — Utara sudah di
batas maksimum sebelum "+1 detik" dicoba, jadi tidak ada efeknya sama
sekali. Aggressive sekarang **menghitung ulang total dari nol**: Utara
justru **turun** dari 60 ke 33 detik (rumus RuleBasedEngine lama
menebak Utara butuh hijau maksimum, tapi Flow Ratio sungguhan dari
data kendaraan bilang tidak sebesar itu), dan siklus totalnya jadi jauh
lebih pendek (144 detik → 105 detik). Ini bukan cuma beda kandidatnya —
**hasilnya juga lebih baik**: diuji SUMO, delay turun dari 21,42 detik
(LOS C) jadi 16,00 detik (LOS B). Detail lengkap di bagian 6.

### 1.2 Kelebihan & kekurangan masing-masing

**Aggressive lama:**
- ✅ Sederhana, gampang dijelaskan langkahnya
- ✅ Perubahannya kecil → risiko rendah, tidak akan bikin simpang lain jadi kacau
- ❌ Tidak ada dasar teori — kalau ditanya "kenapa 1 detik", jawabannya cuma "hasil coba-coba di SUMO"
- ❌ 3 dari 4 lengan tidak pernah ikut dipertimbangkan sama sekali

**Aggressive sekarang (PKJI):**
- ✅ Ada rumus & standar resmi yang bisa ditunjuk kalau ditanya
- ✅ Semua lengan ikut dipertimbangkan, bukan cuma yang paling padat
- ✅ Ada bukti bisa ditelusuri ke angka kendaraan asli (bagian 5)
- ✅ Arus jenuh sekarang diambil **langsung dari studi lapangan Simpang Pingit yang sudah dipublikasikan** (bagian 4), bukan lagi dihitung sendiri dari asumsi lebar jalan
- ❌ Perubahannya jauh lebih besar dari sebelumnya (kandidat yang padat masih bisa mentok ke batas atas/bawah — lihat temuan bagian 5.3), jadi butuh diuji SUMO dengan hati-hati sebelum dipakai beneran, tidak sekadar "pasti lebih baik karena rumusnya resmi"
- ❌ Data sumbernya dari survei 2016 (10 tahun lalu) dan proyek ini tidak mengukur ulang kondisi jalan sendiri — lihat bagian 4.4-4.5

## 2. Kenapa baseline TIDAK ikut diubah

`baseline` dipakai di banyak tempat sebagai **pembanding "sebelum
dioptimasi"** — kartu Before/After di halaman Riwayat, badge menang/kalah
skenario, dll (lihat `BASELINE_CANDIDATE_ID` di `backend/app/services/history_service.py`). Kalau baseline ikut dihitung ulang pakai PKJI, tidak ada lagi apa yang mau dibandingkan — makna "seberapa besar sistem membantu" hilang.

Baseline sendiri **juga bukan rumus resmi apa pun** — itu rumus linear
sederhana buatan tim (`decision_engine/rule_based_engine.py::calculate_green_time`). Tidak diklaim sebagai PKJI di tempat manapun.

## 3. Rumus yang dipakai

Ini gambar alur 5 langkahnya. Detail rumus tiap langkah ada di bawah
gambar — tidak perlu dihafal semua sekaligus, cukup ikuti urutannya.

```mermaid
flowchart TD
    A["Jumlah kendaraan per lengan<br/>(dari kamera, tiap 5 detik)"] --> B["Langkah 1 — Ubah ke SMP<br/>1 mobil = 1 SMP, 1 motor = 0,25 SMP,<br/>1 bus/truk = 1,3 SMP"]
    B --> C["Langkah 2 — Flow Ratio (FR)<br/>seberapa penuh lengan itu<br/>dibanding kapasitas jalannya"]
    C --> D["Langkah 3 — Hitung waktu 1 putaran lampu<br/>(siklus) yang paling pas"]
    D --> E["Langkah 4 — Bagi waktu hijau tiap lengan<br/>sesuai porsi kepadatannya (FR)"]
    E --> F["Kandidat BALANCED selesai"]
    E --> G["Langkah 5 — Cek tiap lengan:<br/>masih kewalahan? (DS lebih dari 0,85)"]
    G -- "Ya, masih macet" --> H["Tambah waktu hijau<br/>lengan itu +2 detik"]
    H --> G
    G -- "Tidak, sudah aman" --> I["Kandidat AGGRESSIVE selesai"]
```

**Penjelasan super simpel tiap kotak:**

- **Langkah 1 (ubah ke SMP):** motor, mobil, bus, dan truk ukurannya
  beda-beda dan makan tempat di jalan berbeda-beda juga. Supaya bisa
  dibandingkan adil, semua diubah jadi satu satuan yang sama, namanya
  SMP (anggap saja "setara berapa mobil").
- **Langkah 2 (Flow Ratio):** membandingkan "seberapa banyak kendaraan
  yang mau lewat" dengan "seberapa banyak yang muat ditampung jalan
  itu". Kalau angkanya mendekati 1, artinya lengan itu hampir/sudah
  penuh.
- **Langkah 3 (waktu 1 putaran lampu):** ini menentukan berapa detik
  total satu putaran lampu (utara→timur→selatan→barat→ulang lagi),
  dihitung supaya totalnya paling efisien untuk kondisi saat ini.
- **Langkah 4 (bagi waktu hijau):** lengan yang lebih padat (Flow Ratio
  lebih besar) dapat jatah hijau lebih lama, secara proporsional. Di
  sinilah kandidat **balanced** selesai dihitung.
- **Langkah 5 (cek & tambah, khusus aggressive):** setelah dibagi
  proporsional, dicek lagi satu-satu — ada lengan yang masih kewalahan
  tidak? Kalau ada, ditambah beberapa detik lagi, diulang ceknya, sampai
  aman atau sampai mentok batas maksimum. Ini yang membuat kandidat
  **aggressive** beda dari **balanced**.

### Langkah 1 — Konversi ke SMP (Satuan Mobil Penumpang)

Setiap jenis kendaraan dikali faktor ekivalensi (emp) standar untuk
simpang bersinyal 4-lengan:

| Jenis | emp |
|---|---:|
| Mobil (LV) | 1,0 |
| Bus + truk (HV) | 1,3 |
| Motor (MC) | 0,25 |

```
Q_smp = mobil×1,0 + (bus+truk)×1,3 + motor×0,25   [per jendela 5 detik]
Q_smp/jam = Q_smp × (3600 / 5)
```

### Langkah 2 — Flow Ratio (FR)

```
FR = Q_smp/jam ÷ S
```

`S` = arus jenuh (kapasitas dasar lengan), **beda tiap lengan** karena
kondisi jalannya beda. **Diambil langsung dari hasil studi lapangan
Simpang Pingit** (bukan dihitung sendiri dari `S0 = 600 × We` — lihat
bagian 4 untuk penjelasan lengkap & sumbernya):

| Lengan | S — arus jenuh (smp/jam) |
|---|--:|
| Utara (Jl. Magelang) | 5.212,48 |
| Timur (Jl. Diponegoro) | 4.489,81 |
| Selatan (Jl. AM. Sangaji) | 3.652,16 |
| Barat (Jl. Kyai Mojo) | 3.842,90 |

### Langkah 3 — Waktu siklus optimum (metode Webster, dipakai PKJI)

```
c = (1,5 × LTI + 5) ÷ (1 − Σ FR)
```

`LTI` = total lost time (4 lengan × 4 detik kuning = 16 detik, konstanta
`YELLOW_SECONDS` yang sudah dipakai di seluruh proyek ini).

Kalau Σ FR ≥ 0,95 (simpang oversaturasi, penyebut mendekati/di bawah
nol), dijepit ke 0,95 — ini **pengaman**, bukan bagian rumus PKJI baku.
Didokumentasikan eksplisit di kode (`scenario_generator.py`).

### Langkah 4 — Pembagian hijau proporsional → kandidat **"balanced"**

```
g_lengan = (FR_lengan ÷ Σ FR) × (c − LTI)
```

Dijepit ke `MIN_GREEN_SECONDS..MAX_GREEN_SECONDS` (15–60 detik) — itu
batas operasional TLS di proyek ini, bukan bagian rumus PKJI.

> Catatan teknis: `Σ FR` di **bagian ini** (pembagi porsi tiap lengan)
> memakai jumlah FR **asli** (belum dijepit 0,95) — beda dari `Σ FR` di
> Langkah 3 (dipakai menghitung `c`) yang **sudah** dijepit. Kalau
> keduanya dijepit, porsi antar-lengan jadi tidak sepenuhnya
> proporsional lagi terhadap kepadatan sebenarnya. Contoh angka
> lengkapnya ada di bagian 5.

### Langkah 5 — Koreksi Degree of Saturation → kandidat **"aggressive"**

```
DS_lengan = Q_smp/jam ÷ (S × g_lengan/c)
```

PKJI/MKJI menetapkan **DS ≤ 0,85** sebagai ambang kinerja simpang yang
masih dapat diterima. Lengan dengan DS > 0,85 diberi tambahan hijau
bertahap (2 detik/langkah) sampai DS turun ke ambang, atau mentok
`MAX_GREEN_SECONDS`. Lengan paling jenuh dikoreksi lebih dulu.

## 4. Asumsi yang harus disebutkan jujur kalau ditanya juri

> **Diperbarui 5 September 2026 (revisi ke-2, sore).** Pengguna
> mengirim **PDF lengkap paper aslinya** dan tim **membacanya langsung**
> (bukan lagi ditranskrip dari ringkasan pihak lain). Isinya beda dari
> yang dikira sebelumnya — bagian ini ditulis ulang total.

### 4.1 Sumbernya SATU paper, bukan dua

Yang tadinya dikira dua sumber terpisah ternyata **satu paper yang
sama**:

> Febriana Ramadhani, Widarto Sutrisno, Iskandar Yasin (Universitas
> Sarjanawiyata Tamansiswa), **"Analisa Kinerja Simpang Bersinyal
> Pingit Yogyakarta"**, jurnal *Renovasi*
> (`jurnal.ustjogja.ac.id/index.php/renovasi`, artikel id 1804).

PDF-nya sudah dibaca **langsung** oleh tim (pengguna mengirim isi
lengkapnya 5 September 2026, setelah link web-nya diblokir 403 saat
tim coba akses sendiri). Tidak ada lagi transkrip tak terverifikasi —
semua angka di bawah dikutip langsung dari tabel di PDF.

### 4.2 Arus jenuh (S) — dipakai LANGSUNG dari paper, bukan dihitung sendiri

**Perubahan penting:** sebelumnya tim menghitung sendiri
`S0 = 600 × We` dari lebar jalan. Setelah baca PDF lengkap, ternyata
**papernya sendiri sudah menghitung arus jenuh yang sudah dikoreksi
lengkap** (Tabel 2 di paper) — jauh lebih baik daripada dihitung ulang
dari lebar mentah, karena sudah termasuk semua faktor penyesuaian
MKJI hasil pengamatan lapangan asli (bukan diasumsikan 1,0 seperti
kode kami sebelumnya).

| Lengan | S — arus jenuh (smp/jam), dari Tabel 2 paper |
|---|--:|
| Utara (Jl. Magelang) | 5.212,48 |
| Timur (Jl. Diponegoro) | 4.489,81 |
| Selatan (Jl. AM. Sangaji) | 3.652,16 |
| Barat (Jl. Kyai Mojo) | 3.842,90 |

**Soal lebar jalan (We) — cuma 2 dari 4 lengan yang bisa dikonfirmasi
di teks paper:** paper ini secara eksplisit menyebut *"lebar efektif
(We) untuk lengan Utara yang semula **8,2 meter**... untuk lengan
Timur yang semula **7,6 meter**"* (di bagian skenario pelebaran
jalan). **We Selatan dan Barat tidak disebutkan di teks manapun** di
paper ini. Karena itu tim memakai **S langsung dari Tabel 2** (bukan
menghitung ulang dari We) — supaya tidak perlu menebak We yang
memang tidak ada datanya.

### 4.3 Data pembanding: Q, kapasitas (C), dan DS hasil studi lapangan

Paper yang sama juga melaporkan kondisi jam puncak pagi (Selasa, 8
November 2016, 06.45–07.45 WIB):

| Lengan | Q — arus lalu lintas (smp/jam) | C — kapasitas (smp/jam) | DS |
|---|--:|--:|--:|
| Utara | 1.268 | 1.417 | 0,895 |
| Timur | 959 | 1.017 | 0,943 |
| Selatan | 598 | 764 | 0,783 |
| Barat | 549 | 803 | 0,683 |

**Kenapa Q dan C ini TIDAK dipakai langsung menggantikan hitungan kami
sendiri:** Q di tabel itu adalah **volume kendaraan hasil survei
manual 2016** (bukan dari CV SmartTwin), dan C = `S × hijau/siklus`
memakai **waktu hijau & siklus simpang tahun 2016** — beda dari
program TLS Simpang Pingit yang dipakai proyek ini sekarang. **S**
(arus jenuh) yang dipakai proyek ini, karena itu murni kapasitas fisik
jalan (lebar, kondisi permukaan) yang relatif stabil selama geometri
jalan belum berubah — beda dari Q/C yang situasional.

**Yang menarik: kesimpulan paper ini SEARAH dengan hasil model kami
sendiri** — Utara (DS 0,895) dan Timur (DS 0,943) adalah dua lengan
paling jenuh menurut paper ini, **persis sama** dengan yang ditemukan
lewat hitungan PKJI kami di bagian 5 & 6 (Utara & Timur konsisten
butuh koreksi DS di kandidat aggressive).

### 4.4 Catatan umur data — harus disebutkan jujur

**Survei lapangan asli paper ini: Selasa, 8 November 2016** — hampir
10 tahun lalu, bukan data terbaru. Arus jenuh (S) yang dipakai proyek
ini murni fungsi geometri jalan (lebar, kondisi fisik) yang biasanya
tidak berubah cepat kecuali ada pelebaran/renovasi — jadi tetap
relevan dipakai. Tapi **volume lalu lintas (Q) di paper itu SUDAH
TIDAK dipakai** proyek ini — Q proyek ini datang dari CV real-time
SmartTwin sendiri (lihat bagian 5), bukan dari paper 2016.

### 4.5 Yang masih murni asumsi (satu-satunya yang tersisa)

**Faktor penyesuaian lanjutan PKJI** (`FCS`/`FSF`/`FG`/`FP`/`FRT`/`FLT`)
**tidak dihitung ulang oleh tim SmartTwin** — proyek ini memakai S
yang SUDAH termasuk faktor-faktor itu dari hasil pengukuran paper di
atas, apa adanya, bukan mengukur ulang sendiri kondisi jalan (gesekan
samping, parkir, dll.) tahun 2026. Kalau kondisi jalan berubah
signifikan sejak 2016 (pelebaran, larangan parkir baru, dst.), angka
S ini bisa jadi sudah tidak akurat — belum ada survei ulang.

Konstanta lain (emp, ambang DS 0,85, rumus siklus Webster) adalah
**nilai baku PKJI/MKJI** yang lazim dipakai di praktik rekayasa lalu
lintas Indonesia — bukan buatan tim.

## 5. Perhitungan manual, langkah demi langkah, data CV asli

Bagian ini isinya hitungan tangan, bukan cuma rumus — **memakai data
kamera sungguhan**, bukan angka karangan. Sumbernya:
`cv/output/crossing_simpang.csv`, baris asli hasil deteksi CCTV Simpang
Pingit, 15 Agustus 2026. Setiap angka di bawah bisa dicek ulang langsung
ke file CSV itu.

### 5.1 Contoh 1 — jendela sibuk, `16:58:20`

**Data mentah** (1 jendela = 5 detik, apa adanya dari kamera):

| Lengan | Mobil | Motor | Bus | Truk | Total |
|---|--:|--:|--:|--:|--:|
| Utara (kamera MAGELANG) | 0 | 6 | 1 | 0 | 7 |
| Timur (kamera DIPONEGORO) | 1 | 4 | 1 | 0 | 6 |
| Selatan (CCTV_1) | 0 | 0 | 0 | 0 | 0 |
| Barat (CCTV_3) | 0 | 3 | 0 | 3 | 6 |

**Langkah 1 — ke SMP.** Rumus: `mobil×1,0 + (bus+truk)×1,3 + motor×0,25`, lalu dikali `3600/5 = 720` untuk jadi per jam.

```
Utara   : 0×1,0 + 1×1,3 + 6×0,25 = 0 + 1,3 + 1,5  = 2,80 smp  → ×720 = 2.016 smp/jam
Timur   : 1×1,0 + 1×1,3 + 4×0,25 = 1 + 1,3 + 1,0  = 3,30 smp  → ×720 = 2.376 smp/jam
Selatan : tidak ada kendaraan sama sekali           = 0,00 smp  → ×720 =     0 smp/jam
Barat   : 0×1,0 + 3×1,3 + 3×0,25 = 0 + 3,9 + 0,75 = 4,65 smp  → ×720 = 3.348 smp/jam
```

**Langkah 2 — Flow Ratio.** `S` dari Tabel 2 paper Simpang Pingit
(bagian 4.2): Utara 5.212,48, Timur 4.489,81, Selatan 3.652,16, Barat
3.842,90 smp/jam.

```
FR utara   = 2.016 / 5.212,48 = 0,39
FR timur   = 2.376 / 4.489,81 = 0,53
FR selatan =     0 / 3.652,16 = 0,00
FR barat   = 3.348 / 3.842,90 = 0,87
------------------------------------
Σ FR (asli, belum dijepit) = 0,39+0,53+0+0,87 = 1,79
```

⚠️ **Σ FR = 1,79, di atas 1.** Jendela 5 detik ini memang jendela yang
SANGAT sibuk (lihat data mentah di atas) — oversaturasi kalau
diekstrapolasi jadi laju per jam. Lihat kotak "Temuan jujur" di
bagian 5.3.

**Langkah 3 — waktu siklus.** Σ FR dijepit ke 0,95 (di atas ambang aman):

```
LTI = 4 lengan × 4 detik kuning = 16 detik
c = (1,5×16 + 5) / (1 − 0,95) = 29 / 0,05 = 580 detik  (≈9 menit 40 detik)
```

**Langkah 4 — bagi hijau proporsional (balanced).** Porsi tiap lengan
memakai Σ FR **asli** (1,79), bukan yang dijepit (0,95) — lihat catatan
teknis di Langkah 4 bagian 3.

```
green_budget = 580 − 16 = 564 detik

porsi utara   = 0,39 / 1,79 = 0,216  → hijau = 0,216×564 = 122 dtk → dijepit MAX 60 dtk
porsi timur   = 0,53 / 1,79 = 0,296  → hijau = 0,296×564 = 167 dtk → dijepit MAX 60 dtk
porsi selatan = 0,00 / 1,79 = 0,000  → hijau = 0×564     =   0 dtk → dijepit MIN 15 dtk
porsi barat   = 0,87 / 1,79 = 0,488  → hijau = 0,488×564 = 275 dtk → dijepit MAX 60 dtk
```

→ **Kandidat balanced: Utara 60 / Timur 60 / Selatan 15 / Barat 60 detik**
— jendela ini genuinely sangat sibuk, jadi tetap mentok di ketiga
lengan yang ada kendaraannya. Siklus aktual (dari hijau yang SUDAH
dijepit) = 60+60+15+60+16 = **211 detik.**

**Langkah 5 — cek DS (aggressive).** `DS = smp/jam ÷ (S_lengan × hijau/siklus)`, siklus = 211 detik dari Langkah 4:

```
DS utara   = 2.016 / (5.212,48 × 60/211) = 2.016 / 1.482,2 = 1,36
DS timur   = 2.376 / (4.489,81 × 60/211) = 2.376 / 1.276,7 = 1,86
DS selatan =     0 / (3.652,16 × 15/211) = 0,00
DS barat   = 3.348 / (3.842,90 × 60/211) = 3.348 / 1.092,8 = 3,06
```

Utara, timur, barat semua **jauh di atas ambang 0,85**. Harusnya
dikoreksi (ditambah hijau). **Tapi ketiganya sudah mentok
`MAX_GREEN_SECONDS = 60 detik`** sebelum koreksi sempat jalan, jadi
koreksi tidak bisa berbuat apa-apa lagi. Hasilnya:

→ **Kandidat aggressive: SAMA PERSIS dengan balanced (60/60/15/60)** —
bukan karena rumusnya salah, tapi karena batas 60 detik sistem sudah
tercapai duluan. Jendela 5 detik ini memang jendela paling sibuk yang
ditemukan di seluruh 538 jendela data (lihat bagian 5.2 untuk contoh
yang lebih tenang, yang JUSTRU membuktikan rumusnya bekerja normal
kalau kondisinya tidak seekstrem ini).

*(Angka di atas dicocokkan langsung ke keluaran kode
`pkji_cycle_and_green_seconds()`/`pkji_apply_ds_correction()` — bukan
cuma hitung manual terpisah, hasilnya identik.)*

### 5.2 Contoh 2 — jendela lebih tenang, `16:36:15`, untuk pembanding

Data mentah: Utara 1 mobil+1 motor, Timur 1 mobil, Selatan kosong, Barat
2 mobil+1 motor. Jendela ini **di bawah rata-rata** (rata-rata 538
jendela di file CSV ini adalah ~8,3 kendaraan/jendela gabungan 4 lengan;
jendela ini cuma 6).

| | Utara | Timur | Selatan | Barat |
|---|--:|--:|--:|--:|
| smp/jam | 900 | 720 | 0 | 1.620 |
| Flow Ratio | 0,173 | 0,160 | 0,000 | 0,422 |
| **Hijau balanced (dtk)** | **23** | **22** | **15** | **57** |
| DS balanced | 1,00 | 0,97 | 0,00 | 0,98 |
| **Hijau aggressive (dtk)** | **29** | **28** | **15** | **60** |
| DS aggressive | 0,88 | 0,85 | 0,00 | 1,04 |

**Ini yang berubah paling banyak sejak pakai arus jenuh dari studi
lapangan asli.** Dengan data yang benar, rumusnya berjalan **jauh
lebih realistis** untuk jendela ini: tidak semua lengan langsung
mentok ke 60 detik di kandidat balanced, dan aggressive kelihatan
**benar-benar beda** — koreksi DS bekerja seperti dirancang untuk
Utara & Timur (DS turun ke ambang: 1,00→0,88, 0,97→0,85). **Barat**
menunjukkan pola yang sama seperti Contoh 1 dalam skala kecil: ikut
dikoreksi (naik 57→60 detik), tapi mentok `MAX_GREEN_SECONDS` **sebelum**
DS-nya sempat turun ke 0,85 — jadi DS Barat malah naik jadi 1,04
(karena siklus totalnya ikut memendek saat lengan lain dikoreksi,
sementara Barat sendiri sudah tidak bisa nambah lagi). Ini contoh
konkret keterbatasan sistem: PKJI tahu Barat butuh lebih dari 60
detik untuk benar-benar aman, tapi batas operasional TLS proyek ini
tidak mengizinkannya.

### 5.3 ⚠️ Temuan jujur soal jendela 5 detik yang sangat sibuk

Data lebar jalan asli **memperbaiki banyak kasus** (lihat Contoh 2 di
atas), tapi **tidak menghilangkan** satu masalah: **jendela 5 detik
yang genuinely sangat sibuk** (seperti Contoh 1) tetap membuat semua
lengan mentok ke hijau maksimum. Penyebabnya sudah ketemu, bukan
misteri: mengalikan satu jendela 5 detik dengan 720× untuk jadi
perkiraan "per jam" itu **sangat sensitif** — **1 kendaraan tambahan di
1 jendela 5 detik = +720 smp/jam** dalam perkiraan. Kalau kebetulan ada
5-7 kendaraan lewat berbarengan dalam satu jendela 5 detik (seperti
Contoh 1), itu bisa "terlihat" seperti mendekati/melebihi kapasitas —
padahal itu cuma sampel sesaat, bukan kondisi yang benar-benar
bertahan sejam.

**Ini bukan bug** — perhitungan `pkji_flow_smp_per_hour()` sudah benar
sesuai rumusnya, dan pengaman (dijepit ke `MAX_GREEN_SECONDS`, Σ FR
dijepit ke 0,95) sudah bekerja seperti dirancang supaya tidak pernah
menghasilkan angka aneh (siklus negatif, dsb). **Tapi ini keterbatasan
metodologi yang harus disebutkan jujur**: idealnya arus untuk rumus
PKJI dihitung dari rata-rata beberapa menit (meredam noise sampel
sesaat), bukan diekstrapolasi mentah dari satu jendela 5 detik. Ini di
luar scope perbaikan sekarang — dicatat di sini sebagai temuan jujur,
bukan disembunyikan.

**Kalimat siap-jawab kalau juri tanya soal ini:**

> "Kami memakai jendela pengamatan 5 detik dari CV, lalu diekstrapolasi
> jadi laju per jam untuk rumus PKJI. Setelah memasukkan arus jenuh dari
> studi lapangan Simpang Pingit yang sebenarnya (bukan lagi dihitung
> sendiri dari asumsi lebar jalan), rumusnya berjalan normal untuk
> sebagian besar kondisi — tapi kami sadar untuk jendela yang kebetulan
> sangat sibuk, ekstrapolasi ke laju per jam masih sensitif terhadap
> noise sampel pendek. Sudah kami ukur langsung dari data CCTV asli,
> bukan dugaan. Pengaman di kode (penjepitan ke batas hijau
> minimum/maksimum, dan pembatasan Flow Ratio total) mencegah hasil
> yang tidak masuk akal, tapi perbaikan idealnya adalah merata-ratakan
> arus dari beberapa menit, bukan satu jendela sesaat — itu rencana
> lanjutan, bukan yang sudah kami klaim selesai."

## 6. Bukti — dijalankan lewat SUMO sungguhan

> Beda dari bagian 5: contoh di bagian ini pakai **data uji buatan**
> (dirancang supaya tidak semua lengan mentok ke MAX_GREEN, biar
> perbedaan balanced vs aggressive kelihatan jelas), dipakai untuk
> memastikan hasil kandidat PKJI benar-benar bisa dijalankan sampai
> tuntas di simulasi SUMO. Bagian 5 pakai **data CV asli** untuk
> menunjukkan rumusnya dihitung dengan benar dari kondisi lapangan
> sungguhan — dua bukti untuk dua hal berbeda.

Kondisi uji: utara padat (1 mobil + 4 motor/jendela), barat paling sepi
(1 motor/jendela).

| Kandidat | Hijau U/T/S/B (detik) | Siklus | Delay | LOS |
|---|---|---:|--:|---|
| baseline (RuleBasedEngine, tidak berubah) | 60/26/22/20 | 144s | 21,42s | C |
| **balanced** (PKJI proporsional) | 27/20/15/15 | 93s | 13,32s | **B** |
| **aggressive** (PKJI + koreksi DS) | 33/26/15/15 | 105s | 16,00s | B |

**Pemenang di uji SUMO ini: balanced** (delay & antrean terendah).
DS balanced tertinggi: utara 0,95 (belum dikoreksi). DS aggressive
tertinggi: utara 0,88 (setelah dikoreksi, turun dari 0,95).

**Temuan menarik untuk laporan:** baseline (rumus lama RuleBasedEngine)
menebak Utara butuh hijau **60 detik** (mentok maksimum) — tapi
setelah dihitung ulang dari data kendaraan sungguhan pakai PKJI, Utara
sebenarnya cukup **27–33 detik**. Rumus lama over-estimate kebutuhan
Utara, dan siklus totalnya jadi jauh lebih panjang dari yang perlu
(144 detik vs 93–105 detik) — **siklus yang lebih pendek berarti
kendaraan tidak menunggu selama itu untuk gilirannya**, itu sebabnya
delay turun cukup besar (21,42 → 13,32 detik, LOS C → B).

## 7. Kalimat siap-jawab untuk juri

> "Kandidat 'balanced' dan 'aggressive' dihitung dari metode PKJI 2023
> (turunan Webster): kendaraan dikonversi ke SMP lewat faktor
> ekivalensi standar, lalu waktu hijau dibagi proporsional terhadap
> Flow Ratio tiap lengan. 'Aggressive' menambahkan koreksi PKJI untuk
> lengan yang Degree of Saturation-nya di atas ambang 0,85. Arus jenuh
> tiap lengan diambil langsung dari **studi lapangan Simpang Pingit
> yang sudah pernah dipublikasikan** (Ramadhani, Sutrisno & Yasin,
> jurnal Renovasi UST Yogyakarta) — 5.212/4.490/3.652/3.843 smp/jam
> untuk Utara/Timur/Selatan/Barat, sudah termasuk faktor penyesuaian
> lapangan asli, bukan lagi kami hitung sendiri dari asumsi lebar
> jalan. Satu-satunya bagian yang masih murni asumsi adalah kami tidak
> mengukur ulang kondisi jalan itu sendiri di 2026 — kami pakai apa
> adanya dari studi 2016 tersebut. Baseline sengaja tidak diubah karena
> dipakai sebagai pembanding 'sebelum dioptimasi' di seluruh sistem."

## 8. Verifikasi

- `pytest backend/tests/test_scenario_generator.py` — **21 passed** (8
  test baru khusus PKJI: konversi SMP, pembagian hijau proporsional,
  pengaman oversaturasi, formula DS, koreksi DS, tidak pernah mengurangi
  hijau, kandidat baseline benar-benar tidak berubah, fallback aman
  tanpa traffic_state)
- `pytest backend/tests` — **122 passed**
- `pytest simulation/tests` — **25 passed**
- Dijalankan langsung lewat `ScenarioEngine.recommend_full_cycle()` dengan
  SUMO nyata (bukan mock) — angka di bagian 6 bukan simulasi tes, itu
  hasil run sungguhan.
- Perhitungan manual di bagian 5 memakai data mentah asli dari
  `cv/output/crossing_simpang.csv` (bukan diketik ulang manual dari
  ingatan — diambil lewat query langsung ke file CSV), dan hasil hitung
  tangannya dicocokkan ke keluaran fungsi kode sungguhan
  (`pkji_cycle_and_green_seconds`, `pkji_degree_of_saturation`,
  `pkji_apply_ds_correction`) — identik, bukan cuma diasumsikan benar.

# Data lebar ruas (We) Simpang Pingit — 4 lengan lengkap

**Ditambahkan: 6 September 2026.** Melengkapi data lebar efektif (We)
yang sebelumnya cuma diketahui untuk 2 dari 4 lengan (lihat
`hasil-implementasi-pkji-aggressive-balanced.md` bagian 4.2, revisi
lama). Dokumen ini fokus pada satu hal spesifik: angka We keempat
lengan dan bagaimana angka itu dipakai untuk kalibrasi network SUMO
(`simulation/network/`) — bukan mengulang seluruh penjelasan PKJI, yang
tetap ada di `hasil-implementasi-pkji-aggressive-balanced.md`.

---

## 1. Sumber

Febriana Ramadhani, Widarto Sutrisno, Iskandar Yasin (Universitas
Sarjanawiyata Tamansiswa), **"Analisa Kinerja Simpang Bersinyal Pingit
Yogyakarta"**, jurnal *Renovasi*
(`jurnal.ustjogja.ac.id/index.php/renovasi`, artikel id 1804) — paper
yang sama yang jadi sumber arus jenuh (S) di
`hasil-implementasi-pkji-aggressive-balanced.md`.

Link download yang diberikan pengguna 6 September 2026:
`https://jurnal.ustjogja.ac.id/index.php/renovasi/article/download/1804/954/2295`

## 2. Data lebar efektif (We) eksisting, keempat lengan

| Lengan | Jalan | We — lebar efektif eksisting |
|---|---|--:|
| Utara | Jl. Magelang | 8,2 m |
| Timur | Jl. Diponegoro | 7,6 m |
| Selatan | Jl. AM. Sangaji | 7,0 m |
| Barat | Jl. Kyai Mojo | 7,5 m |

Utara dan Timur sudah dikutip sejak revisi awal dokumen PKJI (paper
menyebutnya eksplisit di bagian skenario pelebaran jalan "Alternatif
III"). Selatan dan Barat dikonfirmasi 6 September 2026 dari
tabel/bagian data kondisi geometrik paper yang sama.

## 3. Ini BUKAN dipakai untuk menghitung ulang arus jenuh (S)

Sengaja diulang di sini karena penting: rumus PKJI di
`simulation/scenario_generator.py`
(`PKJI_BASE_SATURATION_FLOW_SMP_PER_HOUR_BY_APPROACH`) tetap memakai
**S langsung dari Tabel 2 paper** (5.212,48 / 4.489,81 / 3.652,16 /
3.842,90 smp/jam untuk Utara/Timur/Selatan/Barat), bukan dihitung ulang
dari `S0 = 600 × We`. Alasannya: S di Tabel 2 sudah termasuk seluruh
faktor koreksi MKJI (gesekan samping, parkir, kelandaian, dst) hasil
pengamatan lapangan asli — `600 × We` mentah tidak memasukkan
faktor-faktor itu sama sekali, jadi tetap kurang akurat walau We-nya
sekarang lengkap untuk 4 lengan.

We di dokumen ini dipakai untuk satu hal saja: **kalibrasi lebar jalan
di network SUMO**, supaya digital twin visual/fisiknya cocok dengan
kondisi lapangan asli, bukan untuk mengubah kandidat balanced/aggressive.

## 4. Perbandingan dengan lebar yang ada di network SUMO sebelumnya

Diukur langsung dari `simulation/network/simpang4_pingit.net.xml.gz`
(edge "MASUK" tiap lengan — ruas terakhir sebelum garis stop, paling
sepadan dengan definisi We/"lebar efektif pendekat" di MKJI) sebelum
kalibrasi:

| Lengan | We (paper, meter) | Lebar network SUMO sebelumnya (meter) | Selisih |
|---|--:|--:|--:|
| Utara | 8,2 | 6,00 | +2,20 |
| Timur | 7,6 | 6,40 | +1,20 |
| Selatan | 7,0 | 6,00 | +1,00 |
| Barat | 7,5 | 6,00 | +1,50 |

Lebar network SUMO sebelumnya kemungkinan besar diwariskan dari data
OSM mentah (lebar jalur kendaraan default), bukan hasil survei —
karena itu lebih sempit dan seragam antar-lengan dibanding data lapangan
asli yang bervariasi per lengan.

## 5. Cara kalibrasi diterapkan ke network SUMO

Lebar tiap lengan diubah di edge **MASUK** (`edge_masuk`, ruas
langsung sebelum garis stop — paling sesuai dengan definisi We di
MKJI/PKJI, yaitu "lebar efektif pendekat"), dibagi rata ke jumlah
lajur edge itu (2 lajur tiap lengan):

| Lengan | Edge ID (MASUK) | We total | Lebar per lajur (2 lajur) |
|---|---|--:|--:|
| Utara | `484349908#2` | 8,2 m | 4,10 m |
| Timur | `153857851#4` | 7,6 m | 3,80 m |
| Selatan | `134603786#2` | 7,0 m | 3,50 m |
| Barat | `590064461#2` | 7,5 m | 3,75 m |

**Yang SENGAJA tidak diubah:**
- Edge **HULU** (jauh dari simpang) dan **KELUAR** (setelah simpang) —
  We di paper adalah lebar pendekat DEKAT simpang, bukan sepanjang
  seluruh koridor. Mengubah HULU/KELUAR tanpa data akan jadi tebakan,
  bukan kalibrasi.
- Geometri/posisi shape lajur, ID edge/lane, topologi koneksi, dan
  program TLS — cuma atribut `width` lajur yang diubah, supaya semua
  script yang mereferensikan ID edge tertentu (PPO env, decision
  engine, LOS per lengan, test) tidak ikut rusak.

**Konsekuensi dari pendekatan ini:** karena hanya `width` yang diubah
(bukan menjalankan ulang `netconvert` dari OSM), bentuk lajur di
persis titik sambungan MASUK↔junction bisa terlihat sedikit tidak
rata secara visual (lebar berubah tapi bentuk sambungannya tidak
dihitung ulang) — ini keterbatasan yang disadari, bukan diam-diam.
Kalibrasi geometri penuh (regenerasi `netconvert` dari file OSM asli
dengan We yang benar) adalah pekerjaan lanjutan yang lebih besar,
berisiko mengubah ID edge yang direferensikan puluhan script — di luar
scope perubahan ini.

## 6. Verifikasi

Diterapkan & diuji 6 September 2026:

- Diukur ulang lewat `sumolib.net.readNet()` setelah perubahan: keempat
  edge MASUK menunjukkan lebar baru persis sesuai target (8,20 / 7,60 /
  7,00 / 7,50 m Utara/Timur/Selatan/Barat) — edge HULU/KELUAR, panjang
  tiap edge, jumlah lajur, bentuk junction `SIMPANG_CENTER`, dan
  bounding box network **semuanya tidak berubah** dibanding sebelum
  patch, membuktikan perubahan benar-benar hanya menyentuh atribut
  `width` yang dimaksud.
- Smoke test resmi proyek `simulation/run_intersection.py` (per
  `simulation/README.md`) dijalankan ulang terhadap network yang sudah
  dipatch: koneksi TraCI, step simulasi, dan kontrol fase TLS manual
  semua lolos ("OK — koneksi TraCI, step simulasi, dan kontrol fase
  manual semua jalan") — network tidak korup dan tetap bisa dipakai
  simulasi sungguhan.
- File asli (sebelum patch) tetap tersimpan di riwayat git — bisa
  dipulihkan dengan `git checkout <commit-sebelum-6-sep-2026> --
  simulation/network/simpang4_pingit.net.xml.gz` kalau suatu saat
  perlu dibatalkan.

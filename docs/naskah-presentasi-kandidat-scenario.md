# Naskah presentasi: baseline, balanced, aggressive

**Ditambahkan: 7 September 2026.** Ini bukan dokumen teknis — ini **naskah
yang bisa langsung dibacakan/dihafalkan** saat presentasi atau demo ke
juri/dosen. Tanpa rumus, tanpa istilah pemrograman. Kalau butuh angka dan
rumus lengkapnya, itu ada di
[`cara-hitung-kandidat-baseline-balanced-aggressive.md`](cara-hitung-kandidat-baseline-balanced-aggressive.md).

---

## Kalimat pembuka (30 detik)

> "Sistem kami tidak langsung memutuskan satu pengaturan lampu. Setiap kali
> mau mengubah lampu, sistem dulu **membuat 3 usulan berbeda**, mengujinya
> di simulasi, baru pakai yang hasilnya paling bagus. Tiga usulan itu kami
> beri nama **baseline**, **balanced**, dan **aggressive**."

---

## 1. Baseline — itu `RuleBasedEngine`, pakai rumus sendiri (bukan PKJI)

**Identitas teknisnya, bilang persis begini:**
> "Baseline itu **RuleBasedEngine** — mesin keputusan berbasis ATURAN
> (rule-based), bukan PKJI, bukan juga machine learning/AI. Dia pakai
> **rumus buatan tim sendiri**, namanya *demand score*: tiga hal dilihat
> dari kamera — **volume kendaraan**, **panjang antrean**, dan
> **kepadatan (density)** — diambil yang PALING TINGGI dari ketiganya,
> lalu itu dipakai sebagai dasar untuk menentukan lama hijau, secara
> linear dari 15 detik (paling sepi) sampai 60 detik (paling padat)."

Jadi kalau ditanya "baseline itu apa": **RuleBasedEngine**, sebagai
**pembanding "sebelum dioptimasi"**, pakai **demand score (volume/antrean/
densitas)** sebagai dasar, hasilnya **durasi hijau linear 15-60 detik**.

**Analoginya (kalau perlu penjelasan lebih santai):** bayangkan satpam yang berdiri di simpang, lihat sekilas
jalan mana yang paling ramai (paling banyak motor/mobil, antreannya paling
panjang), terus main tebak: "jalan ini keliatannya paling padat, kasih
lampu hijau lebih lama." Semakin padat kelihatannya, semakin lama hijaunya
— dari minimum 15 detik sampai maksimum 60 detik.

**Yang penting disebut:**
- Ini rumus **lama**, sudah ada sejak awal, dan **sengaja tidak diubah**.
- Kenapa tidak diubah? Karena baseline dipakai sebagai **pembanding**
  "kalau sistem tidak dioptimasi sama sekali" — kalau ikut diubah, kita
  jadi tidak punya apa-apa untuk dibandingkan.
- Kelemahannya: dia cuma menebak dari kamera, **tidak tahu kapasitas asli
  jalan itu** — jadi kadang menaksir kebutuhan hijau kebesaran padahal
  jalannya sebenarnya masih sanggup menampung.

**Kalimat siap pakai:**
> "Baseline itu cara sistem lama menebak — dia lihat seberapa ramai jalan
> dari kamera, terus kasih hijau lebih lama kalau keliatannya makin
> padat. Sederhana, tapi cuma tebakan, tidak berdasarkan kapasitas jalan
> yang sebenarnya."

---

## 2. Balanced — pakai rumus PKJI 2023 sebagai dasar pembagian hijau

**Identitas teknisnya, bilang persis begini:**
> "Balanced itu pakai **rumus PKJI 2023** (Pedoman Kapasitas Jalan
> Indonesia, turunan metode Webster) sebagai dasar hitungnya — bukan
> tebakan dari tim. Rumus PKJI ini dipakai untuk DUA hal: pertama,
> menghitung **durasi satu putaran lampu (siklus) yang paling optimum**;
> kedua, **membagi waktu hijau ke 4 lengan secara proporsional**, sesuai
> **Flow Ratio** tiap lengan — yaitu perbandingan antara jumlah kendaraan
> yang lewat dengan **kapasitas asli jalan itu (arus jenuh)**, yang
> datanya diambil dari studi lapangan Simpang Pingit yang sudah pernah
> diteliti dan dipublikasikan."

Jadi kalau ditanya "balanced itu apa": pakai **rumus PKJI 2023** sebagai
dasar, fungsinya untuk **menghitung siklus optimum + membagi hijau
proporsional ke Flow Ratio tiap lengan**, hasilnya kandidat siklus yang
paling ringkas/efisien.

**Analoginya (kalau perlu penjelasan lebih santai):** bayangkan **membagi kue** ke 4 orang. Bukan dibagi rata
begitu saja, tapi dibagi **sesuai lapar tidaknya masing-masing** — dan
"lapar" di sini bukan cuma dilihat sekilas, tapi dihitung pakai **rumus
resmi Indonesia untuk simpang lampu lalu lintas** (namanya PKJI 2023),
yang membandingkan jumlah kendaraan yang lewat dengan **kapasitas asli**
jalan itu (data ini kami ambil dari studi lapangan Simpang Pingit yang
sudah pernah diteliti dan dipublikasikan, bukan kami tebak sendiri).

**Yang penting disebut:**
- Ini **bukan** rumus tebak-tebakan — ini standar resmi rekayasa lalu
  lintas Indonesia (PKJI 2023, turunan metode Webster yang juga dipakai
  di standar internasional HCM).
- Semua kendaraan (mobil, motor, bus, truk) dulu **disetarakan** ke satu
  satuan yang sama (karena satu bus makan tempat jauh lebih banyak dari
  satu motor), baru dihitung porsinya.
- Hasilnya: jalan yang lebih padat dapat porsi hijau lebih besar, jalan
  yang lebih sepi dapat porsi lebih kecil — **proporsional**, bukan rata.

**Kalimat siap pakai:**
> "Balanced itu membagi waktu hijau secara proporsional, pakai rumus
> resmi PKJI 2023 — bukan tebakan. Jalan yang lebih padat dibanding
> kapasitas aslinya dapat jatah hijau lebih besar, yang sepi dapat lebih
> kecil, semuanya dihitung dari data kendaraan sungguhan dan kapasitas
> jalan yang sudah pernah diteliti di lokasi ini."

---

## 3. Aggressive — balanced + koreksi Degree of Saturation (DS) PKJI

**Identitas teknisnya, bilang persis begini:**
> "Aggressive itu hasil **balanced yang dikoreksi**, pakai konsep PKJI
> juga namanya **Degree of Saturation (DS)** — perbandingan arus
> kendaraan dengan kapasitas lengan itu SETELAH dapat porsi hijau
> proporsional dari balanced tadi. Kalau DS suatu lengan masih di atas
> ambang **0,85** (artinya masih akan macet), lengan itu dikasih
> **tambahan hijau bertahap (2 detik per langkah)** sampai DS-nya turun
> ke ambang aman, atau sampai mentok batas hijau maksimum sistem (60
> detik)."

Jadi kalau ditanya "aggressive itu apa": **balanced + koreksi**, pakai
**Degree of Saturation PKJI** sebagai pemicu koreksinya, fungsinya untuk
menyelamatkan lengan yang **masih akan macet** meski sudah dibagi
proporsional.

**Analoginya (kalau perlu penjelasan lebih santai):** setelah kue dibagi proporsional (itu tadi si "balanced"),
ada **satu langkah tambahan**: dicek satu-satu, **masih ada jalan yang
bakal kewalahan** meski sudah dapat porsinya? Kalau ada, jalan itu dikasih
**tambahan** sedikit demi sedikit sampai amannya, atau sampai batas hijau
maksimum yang boleh dipakai sistem ini.

**Yang penting disebut:**
- Ambang "kewalahan"-nya juga standar resmi PKJI/MKJI, namanya **Degree
  of Saturation** — kalau di atas 0,85, artinya jalan itu masih akan
  macet meski sudah dapat porsi proporsional.
- Bedanya dengan versi lama aggressive (kalau ditanya "dulu vs sekarang"):
  **dulu** aggressive cuma menambah 1 detik ke 1 jalan tersibuk, 3 jalan
  lain dibiarkan sama seperti baseline — **tidak berdasar rumus apa pun**.
  **Sekarang**, semua 4 jalan dihitung ulang dari nol pakai PKJI, lalu
  yang masih kewalahan ditambah bertahap — bisa lebih dari satu jalan.
- Jujur soal keterbatasannya: kadang jalan yang sudah dikoreksi bisa
  "kembali sedikit di atas ambang" lagi setelah jalan lain ikut
  dikoreksi (karena total durasi satu putaran lampu ikut berubah) — itu
  keterbatasan yang kami sadari dan catat, bukan disembunyikan.

**Kalimat siap pakai:**
> "Aggressive itu hasil balanced yang dicek ulang — kalau masih ada
> jalan yang menurut rumus resmi bakal tetap macet, jalan itu dikasih
> tambahan waktu hijau sedikit demi sedikit sampai amannya, atau sampai
> batas maksimum yang boleh dipakai sistem kami."

---

## 4. Bagaimana pemenangnya dipilih

**Analoginya:** ketiga usulan tadi tidak asal dibandingkan di atas kertas.
Ketiganya **benar-benar dicoba dulu di simulasi lalu lintas komputer**
(SUMO) — kondisi yang sama persis untuk ketiganya — baru dilihat mana
yang hasilnya membuat kendaraan **paling sedikit menunggu** dan
**antreannya paling pendek**. Yang paling bagus itu yang dipakai untuk
lampu sungguhan.

**Kalimat siap pakai:**
> "Ketiga usulan itu bukan pilih-pilih di atas kertas — ketiganya kami
> jalankan di simulasi lalu lintas dulu, kondisi yang sama persis, baru
> kami bandingkan mana yang hasilnya paling sedikit membuat kendaraan
> menunggu. Jadi keputusan akhirnya berbasis bukti simulasi, bukan
> asumsi."

---

## 5. Kalau juri tanya "yang mana paling bagus?"

**Jangan jawab "aggressive pasti paling bagus" atau "balanced pasti
menang"** — jawaban jujurnya:

> "Tidak selalu sama — tergantung kondisi lalu lintas saat itu. Tapi dari
> pengujian yang sudah kami lakukan, **balanced** lebih sering menang
> dibanding dua lainnya, karena durasi satu putaran lampunya paling
> ringkas sehingga kendaraan tidak menunggu terlalu lama. Baseline paling
> sering kalah karena dia menaksir kebutuhan hijau lebih besar dari yang
> sebenarnya diperlukan."

---

## Tabel contekan cepat (untuk sesi tanya-jawab)

| | Baseline | Balanced | Aggressive |
|---|---|---|---|
| **Satu kalimat** | Tebakan dari kamera, cara lama | Bagi hijau proporsional, rumus resmi PKJI | Balanced + koreksi jalan yang masih macet |
| **Berdasarkan apa** | Seberapa ramai kelihatannya (volume/antrean/densitas) | Kepadatan dibanding kapasitas asli jalan (Flow Ratio) | Sama seperti balanced + Degree of Saturation |
| **Standar/rumus** | Buatan tim sendiri, bukan standar resmi | PKJI 2023 (turunan Webster) | PKJI 2023 + ambang DS 0,85 |
| **Kenapa tetap dipakai** | Pembanding "sebelum dioptimasi" | Opsi paling ringkas/efisien | Opsi paling "aman" untuk jalan padat |
| **Kelemahan jujur** | Bisa menaksir kebesaran, tidak tahu kapasitas asli | Tidak menjamin semua jalan aman dari macet | Bisa "sedikit meleset lagi" di jalan yang paling padat |

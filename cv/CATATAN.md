# Catatan buat Melpi — apa yang aku ubah di vehicle_counter.py

Hai Mel, aku (Rahmat) sempat pegang bagian CV sementara kamu fokus ngerjain
rekaman Simpang Pingit. Ini catatan apa aja yang aku ubah dan **kenapa**,
biar kamu nggak kaget pas buka lagi kodenya.

**Yang penting duluan: pipeline kamu nggak aku tulis ulang.** YOLO + ByteTrack,
counting line, tracking centroid, estimasi antrean, estimasi density, sampai
tulis CSV — semuanya tetap punya kamu dan tetap jalan. Yang aku sentuh cuma
bagian konfigurasi dan penamaan kolom. Logika deteksinya nggak aku utak-atik.

---

## ⚠️ PENTING sebelum jalanin ulang `vehicle_counter_pingit.py`

Ketauan 29 Agustus pas nyoba `--conf`: `cv/output/crossing_simpang.csv`,
`percobaan_logic_simpang.csv`, dan `snapshot_zona.csv` itu **DITULIS ULANG DARI
NOL** tiap run (mode `"w"`, bukan nambah) — dan ketiganya **TIDAK ter-track
git** (`.gitignore` baris `cv/output/*.csv`, sengaja karena dianggap bisa
dibuat ulang). Kalau kamu jalanin skrip ini buat eksperimen (coba parameter
beda, tes 1 kamera doang, dst), `git checkout` **TIDAK BISA** memulihkan data
lama yang ketimpa — itu bakal hilang beneran.

**Sebelum jalanin apa pun yang bukan run produksi penuh (4 kamera, durasi
penuh):** copy manual dulu ke folder lain.

```powershell
cd cv\output
mkdir _backup_sebelum_tes
copy crossing_simpang.csv _backup_sebelum_tes\
copy percobaan_logic_simpang.csv _backup_sebelum_tes\
copy snapshot_zona.csv _backup_sebelum_tes\
```

Detail lengkap kejadiannya ada di `docs/STATUS-DAN-SISA-KERJA.md` item P-5.

---

## 1. Path nggak lagi nunjuk ke `D:\smarttwin\`

**Dulu:**

```python
MODEL_PATH = r"D:\smarttwin\cv\models\yolo26s.pt"
CAMERAS = {
    "Simpang 1": r"D:\smarttwin\cv\videos\simpang1.mp4",
    ...
}
```

**Sekarang:**

```python
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "yolo26s.pt")
```

**Kenapa:** path `D:\smarttwin\` itu cuma ada di laptop kamu. Pas aku coba
jalanin di laptopku (reponya di drive E:), langsung error nggak nemu model —
padahal filenya ada, cuma beda drive. Tiap orang yang mau bantu ngetes jadi
harus edit kodenya dulu, dan gampang kelupaan ke-commit.

`BASE_DIR` itu otomatis nunjuk ke folder `cv/` tempat file itu sendiri berada.
Jadi mau reponya di `D:\`, `E:\`, atau laptop siapa pun, path-nya ketemu
sendiri tanpa diedit. Struktur foldernya sama persis kayak punya kamu
(`cv/models/`, `cv/videos/`, `cv/output/`), cuma cara nunjuknya yang beda.

---

## 2. `"Simpang 1"`..`"Simpang 4"` jadi `north` / `south` / `east` / `west`

**Kenapa:** ini yang paling ngubah cara mikirnya, jadi aku jelasin agak
panjang.

Di kode lama, 4 kamera dinamain `"Simpang 1"` sampai `"Simpang 4"`, dan nama
itu langsung dipakai jadi `intersection_id` di CSV. Artinya secara data, itu
kebaca sebagai **4 persimpangan yang berbeda**.

Padahal SmartTwin cuma modelin **satu** simpang — Simpang Pingit — yang punya
**4 lengan** (utara, selatan, timur, barat), masing-masing dipantau satu
kamera. Jadi harusnya `intersection_id`-nya satu dan sama untuk semua baris,
yang beda itu lengannya.

Ini juga nyambung ke `docs/data-contract.md`, kontrak data yang jadi pegangan
antar modul. Di situ ada:

```python
Approach = Literal["north", "south", "east", "west"]
```

Backend dan dashboard udah pakai istilah `approach` dengan 4 nilai itu. Kalau
CV ngirim `"Simpang 2"`, nggak ada yang bisa nyocokin itu lengan yang mana.

**Efeknya di CSV:** ada kolom baru `approach`, dan `intersection_id` sekarang
konstan `"simpang4-pingit"`:

```
timestamp, intersection_id, approach, lane_id, ...
2026-08-15 10:00:01, simpang4-pingit, north, lane_1, ...
2026-08-15 10:00:01, simpang4-pingit, east,  lane_2, ...
```

`lane_id` tetap ada dan artinya nggak berubah — itu **lajur di dalam satu
lengan**. Jadi sekarang bertingkat: satu simpang → 4 lengan → tiap lengan
punya beberapa lajur.

**Yang belum dikerjain:** nama file videonya aku tebak jadi
`pingit_north.mp4`, `pingit_south.mp4`, dst. Begitu rekaman kamu jadi dan
ketauan sudut kameranya ngadep ke mana, tolong sesuaiin. `COUNTING_LINES` dan
`LANE_REGIONS` juga masih nilai default yang sama semua buat 4 lengan —
belum dikalibrasi, karena emang nunggu footage kamu.

---

## 3. `queue_length` → `queue_length_veh`, `density` → `density_index`

Cuma ganti nama, **hitungannya nggak aku ubah sama sekali**.

**Kenapa:** namanya bikin orang salah nyangka soal satuan.

- `queue_length` kedengeran kayak panjang antrean dalam meter. Padahal di
  kodenya itu **jumlah kendaraan** yang hampir nggak gerak (`+= 1` per
  kendaraan). Bukan panjang.
- `density` kedengeran kayak kepadatan beneran (kendaraan per km). Padahal
  itu `jumlah kendaraan / fraksi lebar lane` — angka relatif terhadap frame
  video, bukan ukuran dunia nyata. Kamu sendiri udah nulis ini di komentar
  kode, cuma nama kolomnya nggak nyeritain hal yang sama.

Jadi sekarang: `queue_length_veh` (jelas satuannya kendaraan) dan
`density_index` (jelas itu indeks, bukan veh/km).

Ini penting buat lomba. Kalau di laporan kita nulis "density 128" dan juri
nanya "itu kendaraan per kilometer?", kita harus bisa jawab jujur. Nama
kolom yang jujur bikin kita nggak kejebak ngeklaim yang nggak bisa kita
buktikan. Nanti kalau kameranya udah dikalibrasi ke ukuran asli, baru boleh
ada kolom `density_veh_per_km` beneran.

---

## 4. Kolom baru: `queue_length_m_est`

Ini **tambahan**, bukan pengganti. `queue_length_veh` tetap ada.

Rumusnya:

```python
QUEUE_SPACE_M = {
    "motorcycle": 2,
    "car": 5,
    "bus": 10,
    "truck": 10,
}
```

Tiap kendaraan yang lagi ngantre dikali angka meter sesuai jenisnya, terus
dijumlah.

**Kenapa dibedain per jenis:** awalnya mau pakai angka rata 7 meter buat
semua kendaraan, tapi itu bias banget di simpang Indonesia. Contoh nyata —
antrean 20 motor + 5 mobil + 1 truk:

| cara hitung | hasil |
|---|---|
| rata 7 m | 182 m |
| per jenis | 75 m |

Selisihnya lebih dari 2x. Di lengan yang isinya motor semua, angka rata bikin
antrean keliatan jauh lebih panjang dari aslinya.

### ⚠️ Ini yang paling penting kamu tau

**Angka 2 / 5 / 10 meter itu ESTIMASI KESEPAKATAN TIM, BUKAN dari tabel
resmi PKJI 2023.**

Aku tulis ini gede-gede karena kalau nanti ada yang nanya kamu — dosen
pembimbing, juri, atau anak tim lain — kamu harus bisa jawab dengan benar.
Jangan sampai kejawab "itu dari PKJI", karena bukan.

Angka itu maksudnya panjang badan kendaraan **ditambah** jarak antar-kendaraan
pas ngantre. Masuk akal, tapi belum divalidasi ke standar mana pun. Makanya
nama kolomnya sengaja ada `_est` di belakang — biar nggak pernah ketuker sama
hasil pengukuran.

**Kalau nanti ada waktu:** angka ini bisa dicek ulang ke tabel SMP (Satuan
Mobil Penumpang) di PKJI 2023. Kalau ternyata beda, tinggal ubah angka di
`QUEUE_SPACE_M`, nggak usah ngutak-atik rumusnya. Dan itu bakal jadi nilai
tambah buat validasi kita.

### Catatan teknis kecil

Awalnya rumus ini aku hitung dari `motorcycle_count`, `car_count`, dst. —
tapi itu keliru, karena kolom-kolom itu isinya **semua kendaraan yang
kedeteksi** di lane, termasuk yang lagi melaju. Jadi angka meternya kegedean,
nggak nyambung sama `queue_length_veh` yang cuma ngitung yang berhenti.

Udah aku benerin. Sekarang ada penghitung `queue_car`, `queue_motorcycle`,
`queue_bus`, `queue_truck` yang naik di blok `if is_queue_vehicle:` yang sama
persis sama `queue_length`. Jadi dua kolom queue itu dijamin ngitung kendaraan
yang sama, bukan kebetulan cocok.

---

## 5. `requirements.txt` sekarang di-pin versinya

```
ultralytics>=8.4.0
lap>=0.5.12
```

Dulu isinya cuma `ultralytics` polos tanpa versi. Ini dua masalah yang aku
kena sendiri pas setup:

**`ultralytics>=8.4.0`** — bobot `yolo26s.pt` itu cuma ada di rilis aset
ultralytics **v8.4.0**. Aku cek langsung ke servernya: di rilis v8.3.0 file
itu **nggak ada**, jadi balikannya 404. Artinya kalau kamu install ulang dan
pip-nya kebetulan ngasih ultralytics versi lama, auto-download modelnya bakal
gagal dan keliatan kayak modelnya ilang — padahal masalahnya di versi library.

**`lap>=0.5.12`** — ini yang lebih nyebelin. `lap` itu dipakai ByteTrack buat
nyocokin deteksi antar-frame, **tapi statusnya dependency opsional** di
ultralytics, jadi `pip install ultralytics` nggak masang dia. Gejalanya aneh:
`model.predict()` jalan normal, tapi `model.track()` (yang kita pakai) tiba-tiba
diem 20 detik buat download `lap` sendiri di tengah jalan. Kalau pas demo
laptopnya nggak ada internet, `track()` gagal total.

Aku udah ngetes: sebelum `lap` kepasang `track()` makan 20,75 detik; sesudah
kepasang cuma 0,24 detik.

**Buat setup ulang di laptop kamu:**

```powershell
cd cv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Kalau koneksi lagi lemot, model bisa diunduh manual — link dan checksum-nya
udah aku catat di komentar `requirements.txt`, taruh aja di `cv/models/`.

---

## Data hasil run kamu aman

CSV hasil run kamu tanggal 14 Agustus (13.086 baris) aku rename jadi:

```
cv/output/smarttwin_traffic_data_melpi_20260814.csv
```

**Nggak dihapus, isinya utuh, dan tetap disimpan di repo** sebagai baseline
buat laporan teknis. Aku kasih pengecualian khusus di `.gitignore` supaya file
itu doang yang ikut ke-commit, sementara CSV hasil run lain tetap di-ignore.

Alasan di-rename: kode nulis CSV-nya mode append. Kalau namanya dibiarin sama,
data run berikutnya bakal nempel di bawah data kamu dan kecampur — apalagi
sekarang jumlah kolomnya udah beda.

---

## Ringkasan kolom CSV sekarang (12 kolom)

```
timestamp
intersection_id      <- konstan "simpang4-pingit"
approach             <- BARU: north / south / east / west
lane_id              <- lajur di dalam satu lengan
vehicle_count
car_count
motorcycle_count
bus_count
truck_count
queue_length_veh     <- dulu "queue_length"
queue_length_m_est   <- BARU, estimasi meter
density_index        <- dulu "density"
```

Oh iya, kolom `person_count` dan `bicycle_count` udah dilepas dari CSV
sebelumnya, karena kontrak datanya cuma ngatur 4 jenis kendaraan. Tapi
**deteksi person-nya tetap jalan** — soalnya itu yang dipakai
`person_is_rider()` biar pengendara motor nggak kehitung dua kali. Kalau
deteksinya ikut dibuang, `motorcycle_count` malah jadi salah.

---

Ada yang kurang jelas atau menurut kamu keputusannya kurang pas, bilang aja —
ini kodenya kamu yang bangun, aku cuma nyambungin ke bagian lain. 🙏

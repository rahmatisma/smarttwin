# Hasil Validasi Akurasi Deteksi CV (Manual vs Sistem) — 29 Agustus 2026

Dikerjakan Rahmat, memenuhi item S-4 di `docs/STATUS-DAN-SISA-KERJA.md`. Tidak ada ground truth beranotasi (mAP/precision/recall formal) di repo ini — dokumen ini adalah pengganti murah: hitung manual dari rekaman asli, dibandingkan dengan angka `jumlah_crossing` yang dicatat sistem di `cv/output/crossing_simpang.csv`.

## Metode

8 potongan video @1 menit, dipilih otomatis dari data CSV asli (bukan dipilih manual, supaya tidak bias memilih segmen yang "kelihatan gampang") — 2 kondisi (ramai/sepi) untuk tiap 4 arah lalu lintas yang punya garis hitung di sistem ini:

| Arah | Kamera | Nama garis di kode |
|---|---|---|
| Selatan | CCTV_1 | `selatan` |
| Utara | CCTV_2 | `MAGELANG` |
| Timur | CCTV_2 | `DIPONEGORO` |
| Barat | CCTV_3 | `barat` |

CCTV_4 tidak divalidasi — kamera itu tidak punya garis hitung di kode (`CROSSING_LINES` di `cv/vehicle_counter_pingit.py:312`), dipakai untuk kepadatan zona, bukan hitungan lewat.

**Aturan hitung manual:** kendaraan dihitung +1 pas badannya melintasi garis referensi (lihat `cv/output/garis_referensi_CCTV_1.jpg`, `_2.jpg`, `_3.jpg`), kedua arah lalu lintas dihitung — sama seperti logika sistem (`hitung_crossing()` di `cv/vehicle_counter_pingit.py:868`: tanda berlawanan = lintas, tidak difilter arah). Kendaraan yang belum sampai garis saat waktu potongan habis tidak dihitung di potongan itu (masuk potongan berikutnya kalau ada).

## Hasil per potongan

| # | Arah | Kondisi | Rentang video | Manual | Sistem (CV) | Selisih | Akurasi |
|---|---|---|---|---:|---:|---:|---:|
| 1 | Selatan | ramai | CCTV_1 7:31–8:31 | 65 | 33 | −32 | 50,8% |
| 2 | Selatan | sepi | CCTV_1 24:16–25:11 | 36 | 8 | −28 | 22,2% |
| 3 | Utara | ramai | CCTV_2 19:16–20:16 | 143 | 56 | −87 | 39,2% |
| 4 | Utara | sepi | CCTV_2 8:28–9:23 | 30 | 19 | −11 | 63,3% |
| 5 | Timur | ramai | CCTV_2 3:38–4:38 | 135 | 48 | −87 | 35,6% |
| 6 | Timur | sepi | CCTV_2 21:16–22:16 | 12 | 19 | +7 | 41,7% |
| 7 | Barat | ramai | CCTV_3 41:35–42:35 | 51 | 53 | +2 | **96,1%** |
| 8 | Barat | sepi | CCTV_3 40:39–41:35 | 56 | 23 | −33 | 41,1% |

**Rata-rata akurasi: 48,7%** (rentang 22,2%–96,1%).

Manual dihitung terpisah per kelas kendaraan (mobil/motor/bus) saat sesi hitung; tabel di atas memakai total gabungan karena kolom `jumlah_crossing` di CSV juga total gabungan.

## Interpretasi — jujur, bukan dipoles

**Ini bukan hasil yang bisa diklaim "akurat".** Rata-rata 48,7% berarti sistem, pada sampel ini, kehilangan sekitar separuh kendaraan yang sebenarnya lewat. Ini **jauh** di bawah target awal (sempat diharapkan ~90%+ di rencana kerja) dan harus dilaporkan apa adanya.

**Bukan cuma satu penyebab — ada DUA masalah berbeda yang bercampur, dikonfirmasi lewat pengamatan langsung (bukan cuma statistik) saat menonton video beranotasi berdampingan dengan video mentah:**

### Masalah 1 — Kendaraan hilang (penyebab dominan, bikin UNDERcounting)

| Yang diamati | Mekanisme (dicek ke kode) |
|---|---|
| Motor cepat baru kedeteksi **setelah** lewat garis (CCTV_1) | `hitung_crossing()` butuh posisi kendaraan di frame SEBELUMNYA (`prev_pos`) untuk tahu dia "lewat". Kalau track baru muncul persis pas/setelah lewat garis, `prev_pos` kosong → lintasnya **tidak pernah tercatat** ([`vehicle_counter_pingit.py:852-855`](../cv/vehicle_counter_pingit.py#L852-L855)) |
| Motor dempet-dempetan tidak kedeteksi sama sekali (CCTV_1, CCTV_3) | Oklusi — YOLO tidak bisa memisahkan motor yang bertumpuk rapat jadi kotak individual. Ini soal deteksi, bukan tracking |
| Kamera jauh, baru kedeteksi pas sudah dekat/di luar area (CCTV_2) | Mekanisme sama seperti motor cepat di atas (butuh `prev_pos`), pemicunya jarak/skala objek yang kecil, bukan kecepatan |

Bukti tambahan: CCTV_3 sampel ramai (41:35, kendaraan sedikit & tidak saling menutupi) hasilnya **96,1%** — nyaris sempurna. CCTV_3 sampel sepi (40:39) justru **41,1%** karena kendaraan yang ada saling menutupi dari sudut kamera samping. Ini membuktikan **oklusi**, bukan jumlah kendaraan, yang jadi variabel penentu — "ramai/sepi" cuma proxy kasar untuk oklusi.

### Masalah 2 — Kendaraan terhitung ganda di garis yang salah (bikin OVERcounting, sampel #6)

Dicurigai langsung oleh Rahmat saat menonton CCTV_2 (21:16–22:16, DIPONEGORO/Timur): "jangan-jangan lewat ke Utara?" — **terbukti benar setelah dihitung**. `sisi_garis()` ([`vehicle_counter_pingit.py:465-479`](../cv/vehicle_counter_pingit.py#L465-L479)) menghitung sisi memakai garis **tak terbatas** (perpanjangan matematis dari `p1` ke `p2`), bukan dibatasi cuma di segmen pendek yang digambar di layar.

Titik potong garis tak terbatas MAGELANG × DIPONEGORO cuma berjarak **0,016** (skala 0–1 frame) dari ujung sungguhan garis DIPONEGORO — praktis menempel. Simulasi satu lintasan kendaraan dekat titik itu **memicu kedua garis sekaligus**:
```
vs garis MAGELANG: LEWAT (dihitung)
vs garis DIPONEGORO: LEWAT (dihitung)
```
Satu kendaraan fisik yang sama bisa tercatat sebagai lewat Utara **dan** Timur. Ini **bug nyata dan reproducible**, bukan dugaan — kemungkinan besar penjelas sampel #6 (CV 19 vs manual 12).

**⚠️ Dicoba 29 Agustus, DIKEMBALIKAN — bukan perbaikan bersih.** Sempat dibuat `segmen_berpotongan()` yang membatasi pengecekan lintas ke SEGMEN garis (bukan garis tak terbatas), dan itu **terbukti benar secara matematis** lewat simulasi titik. Tapi saat diuji di video sungguhan (CCTV_2, 4 sampel yang punya hitungan manual): sampel #6/#5 (DIPONEGORO) membaik — sampel #6 melonjak dari 41,7% ke 83,3% — **tapi sampel #3/#4 (MAGELANG) memburuk parah** (39,2%→14,0% dan 63,3%→26,7%). Rata-rata ke-4 sampel itu turun (44,9%→40,8%), jadi secara agregat **bukan perbaikan bersih**. Dugaan penyebab regresi MAGELANG belum dibuktikan (kemungkinan pengecekan ketat menolak crossing sah yang lintasannya miring/dekat ujung garis).

Kode **dikembalikan** ke versi sebelum perbaikan ini (`git show 9387c13:cv/vehicle_counter_pingit.py`) — angka 48,7% di atas tetap yang resmi dilaporkan. Detail investigasi lengkap ada di `STATUS-DAN-SISA-KERJA.md` item P-5, disimpan sebagai catatan kalau ada waktu untuk melanjutkan investigasi setelah 31 Agustus.

### Yang belum diverifikasi (di luar scope validasi ini)

Motor sering terbaca sebagai mobil di CCTV_2 (salah klasifikasi kelas) — diamati langsung, tapi belum jelas apakah ini ikut merusak `track_id` (kalau tracker mempertimbangkan kelas saat mencocokkan objek antar-frame, salah klasifikasi bisa memicu ID baru → memicu Masalah 1 juga). Belum dicek: apakah `CONFIDENCE=0.35` terlalu tinggi untuk motor kecil/jauh, dan apakah `imgsz=1280` cukup untuk kamera CCTV_2 yang lebih jauh dari simpang.

## Kalimat yang aman untuk laporan/presentasi

> "Validasi manual pada 8 sampel (4 arah × 2 kondisi lalu lintas) menunjukkan akurasi rata-rata 48,7%, dengan variasi besar antar kondisi (22%–96%). Pengamatan langsung frame-by-frame mengidentifikasi dua mekanisme berbeda: (1) kendaraan yang bergerak cepat atau jauh dari kamera kadang baru terdeteksi setelah melewati garis hitung, sehingga lintasannya tidak tercatat — terkonfirmasi lewat pembacaan kode; dan (2) pada kamera yang merekam dua ruas jalan sekaligus, ditemukan dan dikonfirmasi lewat perhitungan geometri bahwa perpanjangan matematis dua garis hitung yang berbeda dapat saling tumpang tindih di dekat persimpangan, berpotensi menghitung satu kendaraan pada dua arah sekaligus. Kedua temuan sudah didokumentasikan dengan lokasi kode dan rencana perbaikan yang jelas."

**Jangan** mengklaim angka akurasi tinggi (90%+) — itu tidak didukung data. **Jangan** menyebut ini sebagai "hampir sempurna" berdasarkan sampel #7 saja — itu satu dari delapan.

## Data mentah hitungan manual (per kelas kendaraan)

| # | Mobil | Motor | Bus | Catatan |
|---|---:|---:|---:|---|
| 1 | 19 | 46 | — | |
| 2 | 4 | 31 | 1 | |
| 3 | 37 | 106 | — | |
| 4 | 0 | 30 | — | |
| 5 | 31 | 104 | — | |
| 6 | 4 | 8 | — | Sedikit karena lampu merah |
| 7 | 12 | 39 | — | |
| 8 | 15 | 41 | — | |

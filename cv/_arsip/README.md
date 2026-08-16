# cv/_arsip — jejak kerja investigasi sinkronisasi CCTV

Dibuat **16 Agustus 2026**, sesudah keempat video tersinkron
(`cv/videos/synced/CCTV_*_sync.mp4`) selesai dibuat.

Folder ini **bukan bagian jalur produksi**. Tidak ada satu pun skrip di
`cv/` yang membaca isinya, dan menghapus seluruh folder ini tidak akan
merusak apa pun yang bisa dijalankan ulang. Yang disimpan di sini adalah
barang bukti: hal-hal yang sudah selesai menjawab pertanyaannya, tapi
sayang dibuang karena itulah dasar keputusan yang ditulis di
[`../CATATAN-sync-cctv1.md`](../CATATAN-sync-cctv1.md).

**Kenapa disimpan tapi di-gitignore.** Nilainya forensik, bukan
operasional — berguna kalau hasil sinkronisasi nanti terasa janggal dan
kesimpulan di CATATAN perlu diadu ulang dengan buktinya. Tapi isinya PNG
dan video mentah berukuran besar yang bisa dihasilkan ulang dari video
sumber; itu tidak layak masuk riwayat git. Hanya berkas README ini yang
ikut ke repo, supaya orang yang meng-clone tahu apa yang ada di disk saya
dan kenapa. Aturannya ada di `.gitignore` (`cv/_arsip/*` +
`!cv/_arsip/README.md`).

---

## Isi

### `crop_check/` — 25 PNG, ±20 MB

Potongan gambar dari video, dipakai untuk memeriksa dugaan satu per satu
selama investigasi PERINGATAN CCTV 1. Dihasilkan oleh skrip probe sekali
pakai yang sudah tidak ada lagi — **tidak ada kode di `cv/` yang bisa
membuat ulang berkas-berkas ini**, itu alasan utama foldernya disimpan.

| Pola nama | Isinya | Menjawab apa |
|---|---|---|
| `GEOM_CCTV1..4.png` | pita timestamp keempat kamera, berdampingan | menggugurkan Hipotesis A (geometri glyph): CCTV 1 ternyata 1920×1080 sama seperti CCTV 3/4 |
| `band_t*.png`, `glyph_t*.png` | pita jam & tiap glyph pada beberapa detik | memastikan pembaca digit menatap kotak yang benar |
| `MELESET_CCTV1_idx*_resid*.png` (8) | frame yang residual fit-nya meleset | jamnya terbaca benar — yang salah label waktunya, bukan digitnya |
| `LOMPATAN_frame881_ke_882.png` | dua frame berurutan yang jamnya melompat | bukti seek pada fMP4 mendarat di tempat lain |
| `MUNDUR_frame181800_ke_183000.png` | seek maju, jam justru mundur | idem, dan tidak mungkin dijelaskan oleh salah baca digit |
| `EKOR_frame207120_ke_207240.png` | ujung akhir CCTV 1 | memastikan filenya utuh, bukan terpotong |

### `keping_sync/` — 76 berkas MP4, ±6,5 GB

Potongan mentah per video hasil tahap potong `sync_videos.py`
(19 keping × 4 kamera), sebelum disambung jadi `CCTV_*_sync.mp4`.
Sebelumnya ada di `cv/videos/synced/_keping/`.

`sync_videos.py` memang sengaja tidak menghapusnya — pesan penutupnya
berbunyi *"Keping mentahnya sengaja tidak dihapus (di `_keping/`) supaya
bisa diperiksa kalau sambungannya terasa janggal."* Alasan itu masih
berlaku, cuma tempatnya dipindah ke sini supaya `cv/videos/synced/`
isinya hanya keluaran final.

Ini penghuni terbesar folder ini. **Kalau butuh ruang disk, ini yang
pertama dihapus** — hasil akhirnya sudah ada, dan kepingnya bisa dibuat
ulang dengan menjalankan ulang tahap potong.

### `probe_pts.py` — 17 KB

Skrip probe dua fase yang membandingkan `CAP_PROP_POS_MSEC` (PTS asli)
dengan `idx / fps`, lalu menguji apakah `cap.set()` benar-benar mendarat
di frame yang diminta — dengan jam burned-in sebagai wasit.

**Diarsipkan karena pertanyaannya sudah terjawab.** Hasilnya
mengonfirmasi Hipotesis C: yang rusak sumbu-x (posisi frame), bukan
sumbu-y (pembacaan jam). Kesimpulan itu sudah dituangkan ke
`../CATATAN-sync-cctv1.md`, dan **versi final `sync_videos.py` tidak lagi
memakai `cap.set()` sama sekali** — jadi skrip ini tidak punya lagi
sesuatu untuk diperiksa di jalur produksi.

Skrip ini hanya membaca, tidak pernah menulis video. Kalau dijalankan
lagi dari sini, jalankan dari `cv/` (`python _arsip\probe_pts.py`) —
`BASE_DIR`-nya masih menunjuk ke folder tempat berkasnya berada, jadi
keluarannya akan mendarat di `cv/_arsip/output/`, bukan `cv/output/`.

---

## Yang TIDAK ada di sini

- `cv/output/smarttwin_traffic_data.csv` — **dihapus**, bukan diarsipkan.
  Itu hasil hitung dari video sebelum sinkronisasi, jadi angkanya tidak
  merepresentasikan apa pun yang masih berlaku. Tidak ada nilai forensik
  yang perlu disimpan.
- `cv/output/clockmap/` — **tetap di `cv/output/`**. Itu keluaran normal
  `sync_videos.py` yang dibuat ulang tiap `--dry-run`, bukan barang
  investigasi. Di-gitignore karena regenerated, bukan karena arsip.
- `cv/output/sync_report.json` + `.csv` — **tetap di `cv/output/` dan
  ikut di-commit.** Keduanya metadata produksi (offset & durasi potong
  tiap kamera) yang menjelaskan bagaimana `CCTV_*_sync.mp4` dibuat.

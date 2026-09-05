# Patch geometri Utara & Timur (belum aktif di produksi)

**Status: eksperimen, disimpan terpisah — BUKAN network yang dipakai demo.**
Network produksi tetap `simulation/network/simpang4_pingit.net.xml.gz`, tidak disentuh.

## Kenapa

`docs/audit-bug-ppo-sebelum-training-ke-5.md` (Bug N-2) menemukan ruas Utara & Timur
di network SUMO kependekan drastis dibanding kondisi lapangan asli:
- Utara: cuma 62,42 m di model, padahal antrean real (paper Ramadhani/Sutrisno/Yasin,
  jurnal Renovasi UST) sampai 171 m
- Timur: cuma 57,38 m di model, padahal antrean real sampai 184 m

Diduga ini akar masalah "Bug P" (PPO pilih kasih ke Utara) — bukan fakta fisik simpang,
tapi cacat geometri hasil import OSM yang sengaja tidak diperbaiki sebelumnya (arahan
pembimbing: "simulasikan saja, tidak harus sempurna").

## Isi folder ini

- `extra_nodes.nod.xml` — patch node: geser ujung Utara (`1089852868`) lebih jauh,
  tambah node baru `east_upstream_ext` untuk Timur (lihat catatan "kenapa node baru,
  bukan geser node lama" di bawah)
- `extra_edges.edg.xml` — patch edge: perpanjang shape `484349908#0` (Utara) dan
  `153857851#2` (Timur, dipindah ke node baru)

## Kenapa Timur dapat node BARU, bukan geser node lama

Ujung asli Timur (`cluster_9169071114_9169071219`) itu junction bersama dengan 2 gang
kecil (~0,7-0,8m) dan 1 ruas lain (`590386082#1`, 61m) yang arahnya beda. Kalau node itu
digeser, ketiga ruas itu ikut ketarik dan bentuknya rusak. Makanya ruas Timur dilepas ke
node baru sendiri, tiga ruas lainnya dibiarkan utuh (sudah diverifikasi panjangnya nyaris
tidak berubah).

## Cara reproduksi / regenerasi

```
netconvert --sumo-net-file simulation/network/simpang4_pingit.net.xml.gz ^
  --node-files simulation/network/geometry_patch_utara_timur/extra_nodes.nod.xml ^
  --edge-files simulation/network/geometry_patch_utara_timur/extra_edges.edg.xml ^
  -o simulation/network/simpang4_pingit_extended.net.xml
```
(Perlu `SUMO_HOME` sudah di-set, lihat CLAUDE.md bagian SUMO/TraCI setup.)

## Hasil panjang ruas sesudah patch

| Lengan | Sebelum | Sesudah | Target (antrean real) |
|---|--:|--:|--:|
| Utara | 62,42 m | 190,00 m | ≥171 m |
| Timur | 57,38 m | 207,38 m | ≥184 m |
| Selatan | 521,90 m | tidak diubah | ≥225 m (sudah cukup) |
| Barat | 292,13 m | tidak diubah | ≥126 m (sudah cukup) |

## Sudah divalidasi

- Jumlah edge non-internal sama (49=49) dibanding network asli yang di-re-export identik
  lewat netconvert — tidak ada edge hilang/dobel
- 3 edge yang seharusnya tidak berubah (2 gang kecil + `590386082#1`) panjangnya nyaris
  sama seperti semula
- Peringatan netconvert dibandingkan ke baseline: 3 dari 4 sudah ada sejak awal, 1
  peringatan baru memang diharapkan (koneksi gang kecil ke ruas Timur lama dihapus,
  karena memang sudah tidak nyambung lagi)
- TLS `SIMPANG_CENTER` tetap 1 program, 4 fase
- Smoke test TraCI: 200 langkah simulasi jalan tanpa error

## BELUM divalidasi (perlu sebelum dipromosikan jadi network produksi)

- [ ] `pytest simulation/tests` lengkap jalan di atas network baru ini
- [ ] Uji SUMO dengan kendaraan sungguhan (bukan cuma smoke test 0 kendaraan) —
  pastikan rute lama masih valid ke edge yang sudah dipindah/diperpanjang
- [ ] Cek ulang apakah Bug P (PPO pilih kasih ke Utara) beneran berkurang setelah
  network ini dipakai untuk training ulang
- [ ] Verifikasi visual pakai `sumo-gui` atau `netedit` (belum pernah dilihat manusia,
  baru divalidasi lewat skrip)

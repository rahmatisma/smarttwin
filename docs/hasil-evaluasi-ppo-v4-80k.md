# Hasil Evaluasi PPO v4 — Checkpoint 80.000 Langkah

**Dijalankan 30 Agustus 2026 (pagi), Rahmat.** Evaluasi checkpoint tengah jalan
training v4 (80k dari 100k) — bukan hasil final. Dokumen ini bukan status
tracker; status tetap di `docs/STATUS-DAN-SISA-KERJA.md`.

**Identitas checkpoint terverifikasi:** `action_space = MultiDiscrete([10 10 10 10])`
(4 dimensi = pasca perbaikan Bug A/B/D), `num_timesteps = 80000`. Bukan
checkpoint lama yang namanya kebetulan sama.

---

## Ringkasan eksekutif

| Aspek | Hasil |
|---|---|
| Perbaikan Bug A/B/D (29 Agustus) | ✅ **Bertahan** — 0/24 saturasi antrean, 0/24 saturasi throughput |
| Proses belajar | ✅ Naik monoton −1,12 → −0,21, **tapi plateau sejak ~40k langkah** |
| Gerbang kualitas resmi | ❌ `quality_gate_passed: false` (2 dari 3 metrik) |
| **Validitas gerbang kualitas itu sendiri** | 🔴 **Tidak sahih — lihat Bug F** |
| Bug baru ditemukan | 🔴 **2 (Bug E dan Bug F), keduanya terukur, bukan dugaan** |

**Kesimpulan terpenting:** klaim "PPO selalu kalah pada throughput" — yang selama
ini jadi alasan utama PPO tidak diaktifkan — **tidak terbukti**. Angka itu
artefak dari membandingkan dua kebijakan pada **durasi simulasi yang berbeda**.
Setelah dinormalkan per detik, defisitnya hilang sepenuhnya di ketiga seed.

Ini **bukan** berarti "PPO mengalahkan rule-based". Yang benar: **seri**.

---

## 1. Yang sehat — perbaikan 29 Agustus bertahan

Diukur langsung pada 24 langkah keputusan, checkpoint 80k, split eval:

| Komponen | Nilai | Saturasi |
|---|---|---|
| Antrean | min 29, maks 51, rata-rata 38,4 | **0/24** (ambang 100) |
| Throughput per langkah | min 58, maks 162, rata-rata 104,5 | **0/24** (ambang 200) |

Ketiga komponen reward hidup dan punya gradien (tidak ada yang mentok):

| Komponen | Rata-rata | Rentang |
|---|---:|---|
| `throughput_reward` | +0,2351 | 0,1305 – 0,3645 |
| `queue_penalty` | −0,1343 | 0,1015 – 0,1785 |
| `wait_penalty` | −0,1008 | 0,0687 – 0,1249 |

Ambang saturasi yang dinaikkan 29 Agustus (Bug B) terbukti tepat — tidak ada
lagi reward buta seperti yang terjadi di v2.

---

## 2. Proses belajar — naik, tapi berhenti di tengah jalan

Dari `training_monitor.csv`, 6.778 episode, 7,48 jam:

| Desil | Episode | Reward rata-rata |
|---|---|---:|
| 0 | 0–677 | −1,1246 |
| 1 | 677–1.354 | −0,6702 |
| 2 | 1.354–2.031 | −0,4389 |
| 3 | 2.031–2.708 | −0,3456 |
| 4 | 2.708–3.385 | −0,2718 |
| 5 | 3.385–4.062 | −0,2406 |
| 6 | 4.062–4.739 | −0,2324 |
| 7 | 4.739–5.416 | −0,2093 |
| 8 | 5.416–6.093 | −0,2268 |
| 9 | 6.093–6.778 | −0,2077 |

200 episode pertama −1,395 → 200 terakhir −0,2624. Belajarnya nyata.

**Tapi perhatikan desil 5–9: −0,241 / −0,232 / −0,209 / −0,227 / −0,208.**
Praktis datar — perbaikan berhenti sekitar **episode 3.400, kira-kira 40.000
langkah**. Separuh training terakhir (40k→80k, ±3,5 jam) tidak memberi
perbaikan berarti.

Ini **mengulang persis Temuan A dari training v2 200k**: menambah timestep
tidak membantu. Menyelesaikan sisa 80k→100k kemungkinan besar juga tidak akan
mengubah apa pun.

---

## 3. 🔴 Bug E — reward throughput tidak dinormalkan terhadap waktu

`throughput_norm = min(1.0, arrived / 200.0)`, dan `arrived` **diakumulasi
sepanjang jendela rotasi**. Panjang rotasi ditentukan agent sendiri (76–256
detik). Antrean dan waktu tunggu diukur **snapshot di akhir jendela**, jadi
tidak ikut memanjang dan tidak mengimbangi.

Akibatnya: **memperpanjang siklus otomatis menaikkan reward, tanpa perlu
memperbaiki apa pun.**

Diukur langsung — aksi seragam, 4 langkah per pola, split eval:

| Pola aksi | Durasi rotasi | Throughput mentah | **Throughput/detik** | Reward |
|---|---:|---:|---:|---:|
| Semua 15 detik | 76 s | 46,8 | **0,615** | −0,0556 |
| Semua 30 detik | 136 s | 91,2 | **0,671** | −0,0367 |
| Semua 60 detik | 256 s | 167,5 | **0,654** | **+0,0851** |

- Korelasi durasi rotasi ↔ throughput mentah: **+0,999**
- Korelasi durasi rotasi ↔ reward: **+0,978**
- **Throughput per detik praktis datar** (0,615 / 0,671 / 0,654 — variasi ~6%)

Artinya: efisiensi lalu lintas **tidak berubah**, tapi reward naik **3,6 kali
lipat** hanya karena siklusnya diperpanjang. Agent diberi insentif untuk hal
yang salah.

**Perbaikan yang disarankan:** bagi `arrived` dengan `window_seconds` lalu
normalkan terhadap laju maksimum yang wajar (mis. kendaraan/detik), bukan
terhadap jumlah mentah. Perlu diukur ulang ambangnya seperti waktu Bug B.

---

## 4. 🔴 Bug F — evaluasi membandingkan durasi simulasi yang tidak setara

**Ini yang membatalkan verdict gerbang kualitas selama ini.**

`evaluate_ppo.py` menjalankan **jumlah LANGKAH tetap** (12 langkah × 3 episode),
bukan **durasi simulasi tetap**. Karena PPO dan rule-based memilih panjang
siklus yang berbeda, keduanya mensimulasikan jumlah detik yang berbeda —
lalu `total_throughput_veh` keduanya dibandingkan langsung seolah setara.

Diukur, 12 langkah, split eval:

| Seed | Waktu sim PPO | Waktu sim rule | Throughput mentah | **Throughput per detik** |
|---|---:|---:|---:|---:|
| 1000 | 2.482 s | 2.942 s | −14,8% | **+1,0%** |
| 2000 | 2.702 s | 2.992 s | −9,7% | **+0,0%** |
| 3000 | 1.692 s | 1.957 s | −11,7% | **+2,2%** |

Rule-based konsisten mensimulasikan **18–20% lebih banyak detik** (siklusnya
memang lebih panjang: 245 detik vs 207 detik). Wajar saja kalau totalnya lebih
banyak — ia diberi waktu lebih banyak.

**Setelah dinormalkan per detik, defisit throughput hilang total di ketiga
seed** (+1,0% / +0,0% / +2,2%).

### Konsekuensi yang harus dipahami

**Ketiga metrik lalu lintas terpengaruh cacat yang sama, bukan cuma
throughput.** `mean_accumulated_wait_s` juga menumpuk seiring waktu, dan
antrean cenderung membesar pada siklus panjang. Artinya **dua "kemenangan" PPO
(antrean −12,8%, tunggu −6,4%) juga tidak sahih** — keduanya kebetulan
menguntungkan PPO karena PPO memilih siklus lebih pendek.

Jadi bukan "PPO sebenarnya menang" — melainkan **ketiga angka itu sama-sama
belum bisa dipakai**, dan satu-satunya yang sudah saya normalkan (throughput)
hasilnya **seri**.

**Perbaikan yang disarankan:** samakan anggaran waktu simulasi kedua kebijakan
(mis. jalankan sampai N detik simulasi, bukan N langkah), atau laporkan semua
metrik dalam bentuk laju (per detik / per kendaraan), bukan total mentah.

---

## 5. Perilaku kebijakan

24 langkah, `deterministic=True`:

| Lengan | Durasi hijau dipilih (detik) |
|---|---|
| north | min 15, maks 45, rata-rata 40,2 |
| east | min 40, maks 60, rata-rata 58,8 |
| south | min 25, maks 60, rata-rata 55,8 |
| west | min 15, maks 60, rata-rata 29,8 |

Keragaman aksi: **8 kombinasi unik dari 24 langkah**, dengan `[45, 60, 60, 15]`
muncul 54%. Rendah tapi belum degenerate (bukan satu aksi terus-menerus).

⚠️ **Belum diverifikasi:** sekilas terlihat lengan dengan demand rata-rata
terendah di split eval (south, 13,4 veh/menit) justru diberi hijau kedua
terpanjang, sedangkan yang tertinggi (west, 32,0 veh/menit) diberi terpendek.
**Tapi ini membandingkan rata-rata split terhadap aksi pada episode tertentu —
bukan perbandingan yang sahih.** Perlu pengujian yang mencocokkan profil
per-langkah dengan aksi per-langkah sebelum bisa diklaim sebagai temuan.

---

## 6. Rekomendasi

1. **Jangan aktifkan PPO sekarang.** Bukan karena terbukti kalah, tapi karena
   **belum ada satu pun perbandingan yang sahih** — Bug F membatalkan ketiga
   metrik. Aturan berhenti di STATUS-DAN-SISA-KERJA.md tetap berlaku.
2. **Perbaiki Bug F dulu, baru Bug E.** Bug F murni soal metodologi pengukuran
   (tidak perlu training ulang, bisa langsung dievaluasi ulang dengan checkpoint
   yang sudah ada). Bug E butuh training ulang karena mengubah fungsi reward.
3. **Jangan tambah timestep.** Plateau sejak 40k sudah terukur (bagian 2), dan
   ini pengulangan kedua dari pola yang sama.
4. **Untuk laporan/juri, kalimat yang jujur:**
   > "Evaluasi otomatis kami awalnya menolak PPO karena throughput-nya tampak
   > 15% lebih rendah. Investigasi lanjutan menemukan bahwa perbandingan itu
   > sendiri cacat — kedua kebijakan dibandingkan pada durasi simulasi yang
   > tidak setara. Setelah dinormalkan per satuan waktu, selisihnya hilang di
   > ketiga seed pengujian. Kami memilih tetap memakai rule-based yang
   > terverifikasi, karena setelah temuan ini kami belum punya perbandingan
   > yang sahih untuk mendukung aktivasi PPO."

   Ini lebih kuat daripada versi lama: menunjukkan tim menemukan cacat pada
   metode pengujiannya sendiri, bukan sekadar menerima hasil apa adanya.

---

## Lampiran — cara mereproduksi

Semua angka di atas dari script diagnostik sekali pakai (tidak di-commit,
scratchpad). Perintah evaluasi resmi:

```powershell
$env:SUMO_HOME = "$PWD\.venv\Lib\site-packages\sumo"
.venv\Scripts\python.exe -m decision_engine.evaluate_ppo `
  --model decision_engine/models/checkpoints/smarttwin_ppo_80000_steps.zip `
  --episodes 3 --seed 1000 `
  --data cv/output/crossing_simpang.csv `
  --density-data cv/output/snapshot_zona.csv `
  --output decision_engine/models/eval_v4_checkpoint80k.json
```

Hasil mentahnya tersimpan di `decision_engine/models/eval_v4_checkpoint80k.json`
(dan `eval_v4_checkpoint10k.json`, `eval_v4_checkpoint50k.json` untuk
perbandingan antar-checkpoint).

**Catatan penting saat mereproduksi:** `metrics["arrived"]` di dict info
**bukan** throughput per langkah — itu `getArrivedNumber()` sesaat (1 detik
terakhir, nilainya ~0,2). Yang dipakai reward adalah **`throughput_interval`**.
Saya sempat salah membaca key ini dan hampir melaporkan bug palsu.

# PPO SmartTwin — Buku Pegangan Tim dari Nol sampai Endpoint

Dokumen ini khusus menjelaskan **apa yang dilakukan PPO, dari mana PPO mengetahui
keadaan lampu, bagaimana melatihnya, bagaimana mengujinya, dan kapan model aman
dipasang ke backend**. Perintah diasumsikan dijalankan dari
`D:\LOMBA\kmipn\smarttwin` menggunakan PowerShell.

## 1. Jawaban singkat atas pertanyaan “input PPO cuma empat fitur?”

Tidak. Input model PPO SmartTwin adalah vektor **25 angka**. Angka 4 yang terlihat
pada action bukan jumlah fitur input, melainkan empat pilihan lengan/fase.

```text
Traffic kamera/SUMO (20)  status lampu (5)
┌──────────────────────┐  ┌─────────────────────────────┐
│ 4 lengan × 5 fitur   │  │ fase aktif one-hot (4)      │
│ = 20 angka           │  │ durasi hijau aktif (1)      │
└──────────┬───────────┘  └──────────────┬──────────────┘
           └──────────────┬──────────────┘
                          v
                 observation 25 angka
                          |
                          v
                       PPO/MLP
                          |
                          v
       action [fase_awal, hijau_N, hijau_E, hijau_S, hijau_W]
```

Untuk setiap lengan dalam urutan tetap `north, east, south, west`, kelima fitur
traffic adalah:

| Posisi | Makna | Normalisasi |
|---:|---|---|
| 0, 5, 10, 15 | volume/flow yang crossing dalam window 5 detik | `min(volume / 60, 1)` |
| 1, 6, 11, 16 | kendaraan mengantre | `min(queue / 30, 1)` |
| 2, 7, 12, 17 | estimasi panjang antrean meter | `min(queue_m / 150, 1)` |
| 3, 8, 13, 18 | density index | `min(density / 33, 1)` |
| 4, 9, 14, 19 | kecepatan rata-rata km/jam | `min(speed / 60, 1)` |

Posisi 20–23 adalah one-hot fase. Contoh fase timur aktif:
`[north,east,south,west] = [0,1,0,0]`. Posisi 24 adalah durasi hijau aktif
dibagi 60. Hijau 30 detik menjadi `0.5`.

Jadi lampu **bukan ditebak PPO**. Saat training, statusnya dibaca dari state
internal environment setelah program lampu dikirim ke TraCI. Saat inference,
backend mengirim `currentPhase` dan `currentGreenSeconds` ke
`PPOEngine.build_observation()`. Dengan begitu model mengetahui dua hal:

1. kondisi traffic empat lengan;
2. kondisi kontrol lampu ketika keputusan berikut dibuat.

Jika informasi lampu dihilangkan, dua keadaan traffic yang sama tetapi fase
aktifnya berbeda tampak identik bagi agent. Itu melanggar sifat Markov dan dapat
membuat policy mengganti fase secara tidak tepat.

## 2. Peran LSTM, PPO, rule-based, dan SUMO

Mereka bukan empat versi algoritma untuk tugas yang sama.

| Komponen | Pertanyaan yang dijawab | Input | Output |
|---|---|---|---|
| CV | “Kondisi sekarang apa?” | video CCTV | count, queue, density |
| LSTM | “Kondisi beberapa saat ke depan bagaimana?” | riwayat traffic | forecast traffic |
| PPO/rule-based | “Kontrol lampu apa yang dipilih?” | state + status lampu (+ forecast) | fase awal + 4 durasi |
| SUMO | “Apa dampak kontrol itu?” | demand + program TLS | queue, waiting, throughput |
| Scenario Generator | “Di antara kandidat ini mana terbaik?” | tiga kandidat durasi | kandidat pemenang |

LSTM adalah supervised learning. Ia belajar dari pasangan riwayat dan kondisi
masa depan. PPO adalah reinforcement learning. Ia tidak diberi label “jawaban
durasi yang benar”, tetapi mencoba action, menerima reward, lalu memperbarui
policy. Karena itu prediksi LSTM tidak membuat PPO menjadi tidak berguna: LSTM
memperkirakan keadaan, PPO memilih tindakan.

Pada inference, jika forecast diberikan, implementasi membaurkan 70% state
aktual dan 30% forecast sebelum normalisasi. Bobot itu parameter sistem awal,
bukan kebenaran ilmiah permanen; bobot harus divalidasi pada data evaluation.

## 3. Apa sebenarnya yang dipelajari PPO?

PPO mempelajari policy `π(a|s)`: distribusi kemungkinan action `a` ketika melihat
state `s`. MLP menerima 25 angka lalu menghasilkan distribusi untuk lima bagian
action. Selama training, action disampling agar agent bereksplorasi. Saat endpoint
memakai `deterministic=True`, dipilih action paling kuat agar hasil stabil.

PPO juga melatih value function `V(s)`, yaitu perkiraan total reward masa depan
dari state sekarang. Perbedaan antara hasil aktual dan perkiraan value membentuk
advantage. Advantage positif berarti action lebih baik daripada dugaan; negatif
berarti lebih buruk. PPO mengubah policy beberapa epoch, tetapi rasio policy baru
terhadap policy lama di-*clip* supaya satu batch buruk tidak mengubah policy
terlalu ekstrem.

Istilah penting:

- **timestep**: satu pemanggilan `env.step()`, bukan satu detik SUMO;
- **episode**: rangkaian 12 keputusan secara default;
- **rollout**: kumpulan 512 timestep sebelum PPO memperbarui jaringan;
- **reward**: angka kualitas satu transisi;
- **return**: akumulasi reward saat ini dan masa depan;
- **gamma 0,99**: seberapa kuat reward masa depan diperhitungkan;
- **GAE lambda 0,95**: kompromi bias/variance saat menghitung advantage;
- **entropy coefficient 0,01**: mencegah policy terlalu cepat berhenti mencoba;
- **clip range 0,2**: batas perubahan relatif update policy.

## 4. Action dan urutan fisik lampu

Action space adalah:

```text
MultiDiscrete([4, 10, 10, 10, 10])
```

Contoh action `[1, 3, 5, 4, 2]` berarti:

- index fase awal `1` = east;
- north index 3 = 30 detik;
- east index 5 = 40 detik;
- south index 4 = 35 detik;
- west index 2 = 25 detik.

Daftar index durasi adalah `0..9 = 15,20,25,30,35,40,45,50,55,60` detik.
Urutan siklus fisik tetap **utara → timur → selatan → barat**. Item pertama
hanya menentukan dari posisi mana siklus diterapkan saat keputusan dibuat;
setelah itu rotasi tetap mengikuti urutan fisik. Setiap hijau selalu diikuti
kuning 4 detik. PPO tidak diperbolehkan mengeluarkan state lampu mentah yang
berbahaya atau menyalakan dua konflik arah.

## 5. Bagaimana environment training bekerja

Kode utama berada di `decision_engine/ppo_env.py`.

### Reset

`reset(seed)` melakukan hal berikut:

1. menutup koneksi episode lama;
2. memilih profil demand dari data CV berdasarkan seed;
3. menjalankan `sumo.exe` headless dengan network Pingit;
4. membuat tipe kendaraan;
5. melakukan warm-up 20 detik;
6. membaca traffic SUMO dan membentuk observation 25 fitur.

Loader membaca pasangan data yang sama dengan ingest produksi:
`cv/output/crossing_simpang.csv` untuk flow dan
`cv/output/snapshot_zona.csv` untuk memastikan window/lengan pengukuran
kehadiran tersedia. Crossing 5 detik dikalikan 12 menjadi kendaraan/menit.
Kehadiran zona tidak pernah dijumlahkan ke flow. Jika salah satu file belum
dibuat oleh CV, training berhenti eksplisit dan tidak diam-diam kembali memakai
CSV lama.
Dataset dipisah deterministik: 80% awal untuk train, 20% akhir untuk evaluation.

### Step

`step(action)`:

1. mengubah lima index menjadi fase awal dan empat durasi;
2. membangun delapan fase SUMO: N hijau, N kuning, E hijau, E kuning, S hijau,
   S kuning, W hijau, W kuning;
3. memasang program melalui `trafficlight.setProgramLogic()`;
4. memulai pada fase yang dipilih action;
5. menginjeksi demand dan menjalankan SUMO 30 detik;
6. membaca queue, accumulated waiting, throughput;
7. menghitung reward dan observation berikutnya.

Satu timestep PPO defaultnya 30 detik simulasi, bukan satu siklus penuh dan bukan
satu detik. Episode 12 step berarti horizon 360 detik atau 6 menit simulasi.

### Reward aktif

```text
queue_norm      = min(queue_vehicle / 40, 1)
wait_norm       = min(total_wait / (vehicle_aktif × 120), 1)
throughput_norm = min(vehicle_tiba_dalam_interval / 15, 1)

reward = +0.45 × throughput_norm
         -0.35 × queue_norm
         -0.20 × wait_norm
         -starvation_penalty
```

Jika suatu lengan tidak dipilih sebagai fase awal lebih dari tiga keputusan,
penalti bertambah `0.05` per keputusan berlebih. Ini tidak berarti lengan itu
tidak pernah hijau—rotasi tetap berjalan—tetapi mencegah policy selalu memulai
dari arah sama.

Reward adalah fungsi objektif desain. Ia bukan “hukuman dari manusia” sebanyak
50 kali. Environment memberi reward otomatis pada setiap timestep. Dengan
`n_steps=512`, PPO baru melakukan satu update setelah 512 interaksi. Itulah alasan
50 reward tidak memadai bahkan untuk satu rollout.

## 6. Instalasi sekali saja

```powershell
cd D:\LOMBA\kmipn\smarttwin
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r decision_engine\requirements-rl.txt
python -c "import gymnasium, stable_baselines3, traci; print('dependency OK')"
```

Kode otomatis mencari SUMO dalam urutan: argumen eksplisit, PATH, lalu
`simulation\.venv\Lib\site-packages\sumo\bin\sumo.exe`. Training memakai
`sumo.exe`, bukan `sumo-gui.exe`, sehingga tidak membuka jendela terpisah.

## 7. Validasi environment dan smoke training

### Pilihan A — dijalankan dari root proyek (disarankan)

Pastikan prompt PowerShell berada di:

```text
(.venv) PS D:\LOMBA\kmipn\smarttwin>
```

Kemudian jalankan sebelum training panjang:

```powershell
python -m decision_engine.train_ppo `
  --timesteps 2048 `
  --n-steps 512 `
  --episode-steps 12 `
  --decision-seconds 30 `
  --check-env `
  --output decision_engine/models/smarttwin_ppo_smoke
```

### Pilihan B — dijalankan dari folder `decision_engine`

Jika prompt sudah berada di:

```text
(.venv) PS D:\LOMBA\kmipn\smarttwin\decision_engine>
```

gunakan perintah berikut. Perhatikan output cukup `models/...`, jangan
`decision_engine/models/...` karena current directory sudah `decision_engine`.

```powershell
python -m train_ppo `
  --timesteps 2048 `
  --n-steps 512 `
  --episode-steps 12 `
  --decision-seconds 30 `
  --check-env `
  --output models/smarttwin_ppo_smoke
```

Kedua cara menjalankan kode yang sama. Jangan mencampurkan working directory
Pilihan B dengan path output Pilihan A karena hasilnya akan masuk ke folder
`decision_engine/decision_engine/models`.

`--check-env` memeriksa shape, dtype, reset, step, serta action/observation space.
PPO mengumpulkan kelipatan rollout 512, sehingga nilai aktual dapat sedikit
melampaui `--timesteps`. Smoke berhasil jika proses selesai, tidak ada TraCI
exception, dan file `smarttwin_ppo_smoke.zip` terbentuk. Smoke **bukan bukti
kualitas model**.

Untuk pengecekan super-singkat bahwa file dapat disimpan, boleh memakai
`--timesteps 8 --n-steps 8 --episode-steps 2 --decision-seconds 1`. Jangan pakai
konfigurasi kecil ini untuk menghasilkan kandidat model.

## 8. Training kandidat

### RunPod/Linux (disarankan untuk training panjang)

Launcher `decision_engine/train_ppo_runpod.sh` memakai konfigurasi kandidat yang
sama, memvalidasi dua CSV dan executable SUMO sebelum mulai, serta default ke
CPU karena bottleneck utama adalah SUMO dan PPO memakai MLP kecil.

```bash
cd /workspace/smarttwin-runpod
source .venv-ppo/bin/activate
PPO_TIMESTEPS=100000 PPO_SEED=42 \
  bash decision_engine/train_ppo_runpod.sh
```

Smoke test bisa memakai launcher yang sama tanpa mengubah file:

```bash
PPO_TIMESTEPS=2048 \
PPO_OUTPUT=/workspace/smarttwin-runpod/decision_engine/models/smarttwin_ppo_smoke \
  bash decision_engine/train_ppo_runpod.sh
```

Untuk melanjutkan checkpoint terakhir:

```bash
PPO_TIMESTEPS=50000 \
PPO_RESUME=/workspace/smarttwin-runpod/decision_engine/models/checkpoints/smarttwin_ppo_10000_steps.zip \
  bash decision_engine/train_ppo_runpod.sh
```

Selain model `.zip`, script Python menulis `.training.json` berisi waktu,
device, parameter, versi library, dan SHA-256 kedua dataset. File metadata ini
harus ikut diunduh agar training dapat diaudit dan direproduksi.

Untuk kandidat awal deadline:

```powershell
python -m decision_engine.train_ppo `
  --timesteps 100000 `
  --seed 42 `
  --data cv/output/crossing_simpang.csv `
  --density-data cv/output/snapshot_zona.csv `
  --output decision_engine/models/smarttwin_ppo
```

Jika tetap berada di folder `decision_engine`, bentuk ekuivalennya:

```powershell
python -m train_ppo `
  --timesteps 100000 `
  --seed 42 `
  --data ../cv/output/crossing_simpang.csv `
  --density-data ../cv/output/snapshot_zona.csv `
  --output models/smarttwin_ppo
```

Output:

- `smarttwin_ppo.zip`: checkpoint final yang dibaca backend;
- `checkpoints/`: checkpoint tiap 10.000 callback calls;
- `training_monitor.csv`: reward dan panjang episode;
- `tensorboard/`: hanya aktif jika paket tensorboard terpasang.

Jangan menilai training hanya karena reward terakhir besar. Reward bergerak
karena profil dan seed berubah. Bandingkan rata-rata evaluation pada seed sama.

## 9. Berapa lama training?

Kecepatan tergantung CPU dan SUMO. Ukur dari smoke di komputer yang benar-benar
dipakai. Rumus:

```text
step_per_detik = jumlah timestep / durasi nyata detik
estimasi_jam   = target timestep / step_per_detik / 3600
```

Jalankan 2.048 dahulu. Bila 2.048 step memerlukan 20 menit, 100.000 step kira-kira
`100000/2048 × 20 = 976 menit = 16,3 jam`. Jangan menjanjikan angka jam sebelum
benchmark lokal. Karena satu step menjalankan 30 detik SUMO, bottleneck utama
adalah simulasi CPU, bukan jaringan MLP.

Tahapan yang disarankan:

| Tahap | Timesteps | Keputusan |
|---|---:|---|
| validasi | 512–2.048 | hanya cek pipeline |
| smoke | 5.000–10.000 | cek save/load dan tren log |
| kandidat | 50.000–100.000 | mulai dibandingkan baseline |
| lebih kuat | 200.000–500.000, ≥3 seed | klaim lebih meyakinkan |

Lebih banyak timestep bukan jaminan. Model harus menang di data evaluation yang
tidak dipakai belajar.

## 10. Pengujian PPO melawan rule-based

```powershell
python -m decision_engine.evaluate_ppo `
  --model decision_engine/models/smarttwin_ppo.zip `
  --episodes 10 `
  --seed 1000 `
  --output decision_engine/models/evaluation.json
```

Jika dijalankan dari folder `decision_engine`:

```powershell
python -m evaluate_ppo `
  --model models/smarttwin_ppo.zip `
  --episodes 10 `
  --seed 1000 `
  --output models/evaluation.json
```

Runner menjalankan PPO dan baseline pada **anggaran waktu simulasi yang sama**
(`--seconds-per-episode`, default 1.800 detik = 30 menit simulasi per episode),
bukan jumlah langkah yang sama.

> ⚠️ **Kenapa waktu, bukan langkah?** Satu langkah keputusan = satu rotasi penuh
> yang panjangnya dipilih agent sendiri (76-256 detik). Versi lama berhenti
> setelah 12 langkah, sehingga PPO dan rule-based bisa mensimulasikan jumlah
> detik yang berbeda 18-20% -- lalu total throughput-nya dibandingkan seolah
> setara. Itu bikin PPO terlihat kalah throughput ~15% padahal per detik justru
> seri. Lihat Bug F di `docs/audit-bug-ppo-sebelum-training-ke-5.md`.

Metrik lalu lintas dilaporkan sebagai **laju / rata-rata per kendaraan**, bukan
total mentah: `throughput_veh_per_hour`, `mean_queue_veh`,
`mean_wait_per_vehicle_s`. Blok `fairness` di keluaran JSON menunjukkan berapa
detik simulasi yang benar-benar dijalankan tiap kebijakan plus `skew_percent` --
**periksa nilai ini**; kalau >= 5% perbandingannya belum setara.

Selisih di bawah `TIE_THRESHOLD_PERCENT` (2%) dicatat sebagai **seri**, bukan
kemenangan, supaya gerbang kualitas tidak lolos karena noise. Bagian
`comparison` meluluskan `quality_gate_passed=true` hanya jika queue, waiting,
dan throughput **ketiganya menang di atas ambang** itu. Untuk hasil lomba, ulangi minimal
seed 1000, 2000, dan 3000;
simpan seluruh laporan, lalu laporkan mean/median dan variasinya.

`rule_based_action()` sekarang memanggil `RuleBasedEngine.recommend()` dan
`RuleBasedEngine.recommend_cycle()` produksi dengan `TrafficState` simulasi yang
sama persis dengan input PPO. Fase dan empat durasi hasil engine hanya dipetakan
ke opsi action terdekat (15–60 detik, step 5) karena itulah ruang aksi PPO.

Kriteria aktivasi yang disarankan:

1. tidak ada crash/action invalid;
2. reward evaluation PPO minimal sama dengan baseline;
3. mean dan maksimum queue tidak memburuk material;
4. waiting time tidak memburuk;
5. throughput tidak turun;
6. hasil tidak hanya bagus pada satu seed;
7. fallback endpoint tetap berhasil saat checkpoint tidak ada.

## 10A. Cara membaca metrik hasil evaluasi

File seperti `evaluation.json`, `evaluation_seed_2000.json`, dan
`evaluation_seed_3000.json` **bukan model yang berbeda**. Model PPO yang diuji
tetap satu, yaitu `models/smarttwin_ppo.zip`. File JSON tersebut hanya laporan
pengujian model yang sama pada seed/kondisi acak berbeda.

### `mean_reward`

`mean_reward` adalah rata-rata skor gabungan yang diberikan environment:

```text
reward = bonus throughput
         - penalti antrean
         - penalti accumulated waiting
         - penalti starvation
```

Reward SmartTwin bukan probabilitas, persentase, maupun skor yang wajib berada
di antara 0 dan 1. Cara membacanya:

- semakin besar nilainya, semakin baik menurut rumus reward;
- `-0,09` lebih baik daripada `-0,20`;
- nilai negatif bukan tanda error;
- mendekati `0` biasanya berarti total penalti semakin kecil;
- nilai positif mungkin terjadi jika bonus melampaui penalti;
- nilai `1` tidak berarti akurasi atau kualitas 100%.

Urutan contoh dari terbaik menuju terburuk:

```text
-0,09 > -0,12 > -0,20 > -0,32
```

Reward tidak boleh dibaca sendirian. PPO bisa memiliki reward lebih tinggi tetapi
masih kalah pada salah satu metrik karena reward merupakan gabungan beberapa
komponen dan bobot.

### `mean_queue_veh`

Rata-rata jumlah kendaraan yang berhenti/mengantre pada setiap timestep
evaluasi. **Semakin kecil semakin baik.** Bandingkan PPO dan rule-based pada seed
yang sama karena demand seed berbeda dapat menghasilkan tingkat kemacetan yang
berbeda.

### `mean_accumulated_wait_s`

Rata-rata total waktu tunggu yang telah terakumulasi oleh seluruh kendaraan
aktif, dalam detik. Ini bukan waktu tunggu satu kendaraan. Contoh:

```text
20 kendaraan × rata-rata 48 detik menunggu ≈ 960 detik accumulated waiting
```

**Semakin kecil semakin baik.** Nilai ini juga dipengaruhi jumlah kendaraan
aktif, sehingga harus dibaca bersama queue dan throughput.

### `total_throughput_veh`

Jumlah kendaraan yang berhasil menyelesaikan perjalanan selama seluruh episode
evaluasi. **Semakin besar biasanya semakin baik.** Throughput tinggi tetap perlu
dibaca bersama queue dan waiting; meloloskan banyak kendaraan tetapi menyisakan
antrean yang jauh lebih buruk belum tentu merupakan kontrol terbaik.

### `comparison.quality_gate_passed`

Nilai berikut:

```json
"traffic_metrics_won": 3,
"traffic_metrics_total": 3,
"quality_gate_passed": true,
"recommended_for_activation": true
```

berarti PPO tidak lebih buruk pada ketiga metrik operasional: queue, waiting,
dan throughput. Reward tetap dilaporkan dalam `comparison.metrics.mean_reward`,
tetapi kemenangan reward tidak dapat meluluskan quality gate sendirian.

### Cara menghitung peningkatan

Untuk metrik yang semakin kecil semakin baik, seperti queue dan waiting:

```text
penurunan_% = (rule_based - PPO) / rule_based × 100%
```

Untuk throughput yang semakin besar semakin baik:

```text
perubahan_% = (PPO - rule_based) / rule_based × 100%
```

Hasil negatif pada rumus throughput berarti throughput PPO menurun.

### Contoh hasil aktual tiga seed

Model `smarttwin_ppo.zip` telah diuji masing-masing 10 episode pada seed 1000,
2000, dan 3000. Karena jumlah episode sama, rata-rata ketiga laporan dapat
dibandingkan langsung:

| Metrik | PPO | Rule-based | Interpretasi |
|---|---:|---:|---|
| Mean reward | -0,142 | -0,208 | PPO lebih baik menurut reward gabungan |
| Mean queue | 14,38 | 14,98 | PPO sekitar 4,0% lebih rendah |
| Mean accumulated waiting | 568,36 | 590,88 | PPO sekitar 3,8% lebih rendah |
| Total throughput tiga run | 4.701 | 4.961 | PPO sekitar 5,2% lebih rendah |

Pada seed 3000, PPO memiliki reward lebih tinggi tetapi queue dan waiting lebih
buruk daripada rule-based. Ini contoh nyata mengapa kemenangan reward tidak boleh
dianggap sebagai kemenangan seluruh metrik.

Kesimpulan yang aman untuk hasil tersebut:

> Pada 30 episode evaluasi dari tiga seed, PPO memperoleh reward rata-rata lebih
> tinggi, menurunkan antrean sekitar 4,0%, dan menurunkan accumulated waiting
> sekitar 3,8% dibanding baseline rule-based. Namun throughput PPO masih sekitar
> 5,2% lebih rendah, sehingga PPO menjanjikan tetapi belum unggul mutlak pada
> seluruh indikator.

Ringkasan arah metrik:

| Metrik | Arah yang diinginkan |
|---|---|
| Mean reward | Semakin besar; `-0,1` lebih baik dari `-0,3` |
| Mean queue | Semakin kecil |
| Mean accumulated waiting | Semakin kecil |
| Total throughput | Semakin besar |
| `comparison.quality_gate_passed` | `true` hanya jika queue, waiting, dan throughput semuanya tidak lebih buruk |

## 11. Memasang model ke endpoint

Tambahkan ke `backend/.env` asli—`.env.example` hanya contoh:

```env
SMARTTWIN_DECISION_ENGINE=ppo
SMARTTWIN_PPO_MODEL_PATH=decision_engine/models/smarttwin_ppo.zip
```

Restart backend. Path relatif diselesaikan terhadap root proyek. Bila model lolos
load dan action valid, response bersumber `ppo`. Bila file hilang, dependency
rusak, shape checkpoint berbeda, atau action tidak valid, `PPOEngine` otomatis
memanggil rule-based dan memberi source `ppo-fallback-rule-based`.

Untuk mode demo paling aman:

```env
SMARTTWIN_DECISION_ENGINE=rule-based
```

Rule-based tidak dihapus. Ia tetap baseline, fallback, dan kontrol operasional
saat PPO belum terbukti. Setelah mengubah `.env`, backend wajib direstart karena
engine dibuat saat service diinisialisasi.

## 11A. Verifikasi endpoint PPO sebelum frontend

Jalankan backend dari folder `backend`:

```powershell
cd D:\LOMBA\kmipn\smarttwin\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Periksa status engine tanpa bergantung pada Supabase:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/recommendation/engine-status |
  ConvertTo-Json
```

Kondisi PPO siap memiliki nilai berikut:

```json
{
  "configuredMode": "ppo",
  "activeEngine": "PPOEngine",
  "ppoAvailable": true,
  "fallbackEnabled": true,
  "modelFile": "smarttwin_ppo.zip",
  "loadError": null
}
```

Endpoint `POST /recommendation/engine-test` menerima `TrafficState` langsung dan
menjalankan inferensi read-only. Endpoint ini digunakan untuk pengujian sebelum
frontend karena tidak bergantung pada koneksi Supabase. Contoh PowerShell:

```powershell
$now = (Get-Date).ToUniversalTime()
$body = @{
  intersectionId = "simpang4-pingit"
  windowStart = $now.AddSeconds(-5).ToString("o")
  windowEnd = $now.ToString("o")
  approaches = @(
    @{approach="north"; volume=18; queueLengthVeh=7; queueLengthMEst=49; densityIndex=12; avgSpeedKmh=20},
    @{approach="east";  volume=12; queueLengthVeh=4; queueLengthMEst=28; densityIndex=8;  avgSpeedKmh=25},
    @{approach="south"; volume=25; queueLengthVeh=10; queueLengthMEst=70; densityIndex=16; avgSpeedKmh=15},
    @{approach="west";  volume=9;  queueLengthVeh=2; queueLengthMEst=14; densityIndex=6;  avgSpeedKmh=30}
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/recommendation/engine-test" `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 8
```

Hasil siap harus memiliki `recommendation.source="ppo"` dan
`cyclePlan.source="ppo"`.

Endpoint dashboard tetap `POST /recommendation`. Endpoint itu mengambil traffic
dari Supabase. Jika tidak ada data terbaru, hasilnya sengaja `source="fallback"`
dan alasan `Tidak ada data trafik terbaru`; kondisi tersebut bukan kegagalan
checkpoint PPO. Gunakan `engine-status` untuk kesiapan model dan `engine-test`
untuk membuktikan inferensi model secara terpisah.

### Menguji fallback tanpa mengubah `.env`

Buka terminal backend kedua pada port uji:

```powershell
$env:SMARTTWIN_DECISION_ENGINE = "ppo"
$env:SMARTTWIN_PPO_MODEL_PATH = "decision_engine/models/checkpoint-sengaja-hilang.zip"
python -m uvicorn app.main:app --port 8013
```

Panggil `engine-status` dan `engine-test` pada port 8013. Status harus menunjukkan
`ppoAvailable=false`, sedangkan engine-test harus tetap HTTP 200 dengan
`source="ppo-fallback-rule-based"`. Hentikan server uji dengan `Ctrl+C`. Variabel
tersebut hanya berlaku pada terminal itu dan tidak mengubah `backend/.env`.

## 12. Hubungan checkpoint training dan inference

Training dan inference harus memiliki kontrak yang identik:

- observation shape `(25,)`;
- urutan lengan N,E,S,W;
- urutan fitur volume, queue veh, queue m, density, speed;
- action `MultiDiscrete([4,10,10,10,10])`;
- mapping green index 15–60 step 5.

Kontrak tersebut diimplementasikan satu kali di `ppo_features.py`. Environment
training dan `PPOEngine` inference sama-sama memanggil fungsi itu. Di SUMO,
`volume` dihitung dari kendaraan yang masuk selama window 5 detik terakhir,
sedangkan `densityIndex` dihitung dari kendaraan yang sedang hadir di edge.
Keduanya bukan lagi salinan besaran yang sama.

Mengubah salah satu setelah training membuat checkpoint secara semantik salah,
meskipun kadang masih dapat dimuat. Jika observation ditambah forecast sebagai
20 fitur terpisah, misalnya, shape berubah dan model wajib dilatih ulang. Versi
sekarang memilih fusion 70/30 supaya shape inference tetap 25.

## 13. Keterbatasan yang harus dijelaskan jujur

- Flow CV berasal dari crossing line, bukan jumlah kendaraan yang sedang hadir;
  konversi ×12 dari window 5 detik tetap merupakan pendekatan arrival rate.
- Semua kendaraan training sementara memakai tipe mobil; komposisi motor/bus/
  truk belum masuk reward dinamika.
- Reward belum dikalibrasi terhadap survei waktu tempuh lapangan.
- Evaluation split berdasarkan urutan waktu, tetapi belum mencakup banyak hari,
  cuaca, kecelakaan, atau event khusus.
- Action menentukan empat durasi, tetapi hanya 30 detik disimulasikan sebelum
  keputusan berikutnya. Ini kontrol rolling-horizon, bukan evaluasi satu siklus
  penuh per action.
- PPO belum boleh diklaim mengungguli rule-based sebelum laporan evaluation
  beberapa seed membuktikannya.

Keterbatasan ini adalah alasan fallback dipertahankan. Untuk pengembangan lanjut:
kalibrasi arrival rate, masukkan jenis kendaraan, tambah data beberapa hari,
uji reward ablation, parallel environment, dan evaluasi lapangan/safety sebelum
kontrol nyata.

## 14. Troubleshooting

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| `sumo.exe tidak ditemukan` | SUMO tidak di PATH/lokasi venv berubah | instal SUMO atau berikan path pada environment |
| warning `SUMO_HOME` | tools XML SUMO tidak dikonfigurasi | tidak fatal untuk run lokal; set `SUMO_HOME` bila perlu |
| `No module named app` | perintah dijalankan bukan dari root/kode lama | jalankan persis `python -m decision_engine...` dari root |
| TensorBoard tidak ada | paket opsional belum terpasang | training tetap jalan tanpa TensorBoard |
| shape mismatch 25 | checkpoint kontrak lama | hapus checkpoint eksperimen dan retrain |
| reward datar | demand terlalu kecil/reward tersaturasi | periksa monitor dan metrik info, lalu kalibrasi |
| kendaraan tidak bergerak | route/TLS/config tidak cocok | jalankan `--check-env`, cek TraCI exception |
| endpoint fallback | model/path/dependency gagal | cek log dan `SMARTTWIN_PPO_MODEL_PATH` |

## 15. Checklist praktis sebelum tanggal 30

```text
[ ] dependency terpasang
[ ] --check-env lolos
[ ] smoke 2.048 selesai dan ZIP terbentuk
[ ] kandidat 50k/100k selesai
[ ] evaluation ≥10 episode pada ≥3 seed
[ ] PPO dibandingkan rule-based, bukan hanya reward training
[ ] checkpoint final disalin ke decision_engine/models/smarttwin_ppo.zip
[ ] endpoint menghasilkan source=ppo pada uji normal
[ ] checkpoint sementara dipindah/rename dan fallback tetap 200 OK
[ ] mode demo dipilih berdasarkan hasil evaluation, bukan harapan
```

Rujukan utama: paper asli PPO oleh Schulman dkk. (2017), dokumentasi PPO
Stable-Baselines3, dan konsep reward perubahan waiting time pada SUMO-RL. Tautan
dan pembahasan studi lebih luas tersedia di `README-PPO.md`.

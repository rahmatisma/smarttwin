# PPO SmartTwin — Panduan dari Nol

Dokumen ini ditulis untuk anggota tim yang belum pernah melatih reinforcement
learning. Baca berurutan dan jangan langsung mengaktifkan PPO pada demo.

> Tahapan operasional lengkap dari instalasi, smoke test, training, evaluasi,
> sampai pemasangan endpoint terdapat di `README-PPO-UNTUK-TIM.md`. Panduan itu
> juga menyediakan perintah berbeda untuk eksekusi dari root proyek dan langsung
> dari folder `decision_engine`.

## 1. Perbedaan LSTM, PPO, Rule-Based, dan Scenario Generator

```text
TrafficState saat ini + prediksi LSTM 60 detik
                         |
                         v
              PPO atau RuleBasedEngine
             memilih fase + empat durasi
                         |
                         v
               Scenario Generator + SUMO
          mengukur delay, queue, waiting, throughput
                         |
                         v
                  rekomendasi endpoint
```

- **LSTM** menjawab: “kondisi tiap lengan 60 detik lagi seperti apa?” Outputnya
  prediksi volume, antrean, panjang antrean, dan density. LSTM tidak memilih
  lampu dan tidak menghasilkan tiga skenario.
- **RuleBasedEngine** menjawab: “berdasarkan state aktual dan forecast, fase dan
  durasi baseline apa yang masuk akal?” Engine ini deterministik.
- **PPO** mempelajari jawaban tindakan melalui interaksi dan reward, bukan rumus
  demand buatan manusia.
- **Scenario Generator** menguji alternatif baseline/aggressive/balanced di SUMO
  dan memilih hasil simulasi terbaik.

PPO tidak menggantikan LSTM. PPO dapat memakai keluaran LSTM sebagai bagian dari
observation. PPO juga tidak boleh menghapus RuleBasedEngine karena rule-based
menjadi baseline, fallback, dan kontrol pembanding.

## 2. Cara PPO belajar

LSTM adalah supervised learning: ada masukan dan target. PPO tidak mempunyai
label “durasi benar”. Prosesnya:

1. environment memberi **observation** kondisi simpang;
2. policy memilih **action** fase dan durasi;
3. SUMO menjalankan action;
4. environment memberi **reward** berdasarkan dampaknya;
5. PPO mengumpulkan banyak transisi lalu memperbarui policy;
6. proses diulang sampai policy stabil atau budget habis.

Satu action dan satu reward bukan training. PPO mengumpulkan rollout, menghitung
advantage, lalu melakukan beberapa epoch update memakai clipped objective agar
policy tidak berubah terlalu jauh sekaligus. Rujukan algoritma asli:
[Schulman dkk., 2017](https://arxiv.org/abs/1707.06347).

## 3. Status implementasi sekarang

Sudah tersedia:

- `PPOEngine` terpisah dari `RuleBasedEngine`;
- factory pemilih engine dengan default rule-based;
- fallback otomatis jika checkpoint/dependency/action PPO bermasalah;
- observation dan action contract untuk training dan inference;
- integrasi opt-in ke RecommendationService dan SignalService;
- unit test inferensi, invalid action, missing checkpoint, dan factory;
- dependency PPO yang terpisah dari dependency utama.
- `SmartTwinSumoEnv` berbasis Gymnasium dan TraCI headless;
- loader/agregator demand dari rekaman CV;
- script training dan penyimpanan checkpoint;
- script evaluasi PPO melawan baseline pada seed sama.

Checkpoint final belum disertakan karena harus dilatih dan lolos evaluasi pada
mesin tim. Panduan operasional paling lengkap ada di
`README-PPO-UNTUK-TIM.md`.

## 4. Observation dan action contract

### Observation: 25 nilai

Untuk setiap lengan north/east/south/west terdapat lima fitur ternormalisasi:

1. volume;
2. queue kendaraan;
3. queue meter;
4. density;
5. speed.

Total traffic: `4 x 5 = 20`, ditambah one-hot fase aktif `4`, dan green-time
aktif `1`, sehingga total `25`.

Jika forecast tersedia, state diproyeksikan memakai 70% state aktual dan 30%
forecast LSTM sebelum dibentuk menjadi observation. Kontrak ini ada di
`PPOEngine.build_observation()` dan tidak boleh diubah setelah checkpoint
dilatih tanpa retraining.

### Action: fase + empat green-time

```text
MultiDiscrete([4, 10, 10, 10, 10])
```

- item pertama memilih approach prioritas;
- empat item berikut memilih green-time north/east/south/west;
- opsi durasi: 15, 20, 25, ..., 60 detik;
- kuning tetap 4 detik;
- rotasi fisik tetap north-east-south-west.

Diskretisasi mengurangi ruang pencarian sehingga lebih realistis untuk deadline
pendek dan mencegah output durasi sembarang.

## 5. Logika fallback ke RuleBasedEngine

Factory membaca `SMARTTWIN_DECISION_ENGINE` sekali saat backend start:

```text
mode rule-based
    -> RuleBasedEngine

mode ppo
    -> PPOEngine mencoba load checkpoint
    -> validasi observation dan action
    -> bila gagal, panggil RuleBasedEngine
```

Fallback berlaku untuk:

- `recommend()` — fase prioritas dan satu durasi;
- `recommend_cycle()` — durasi empat lengan.

Sumber hasil dapat diaudit:

| `source` | Engine yang benar-benar digunakan |
|---|---|
| `rule-based` | Rule-based dengan state aktual |
| `rule-based+forecast` | Rule-based dengan state dan LSTM |
| `ppo` | Checkpoint PPO menghasilkan action valid |
| `ppo-fallback-rule-based` | Mode PPO aktif, tetapi rule-based menyelamatkan request |
| `scenario-generator` | Cache segar berasal dari kandidat yang diuji SUMO |

Fallback bisa terjadi karena checkpoint hilang, Stable-Baselines3 belum terpasang,
versi checkpoint tidak kompatibel, shape observation berubah, atau action PPO di
luar rentang. Sistem tidak boleh 500 hanya karena eksperimen PPO gagal.

## 6. Konfigurasi `.env`

Ya, konfigurasi harus ditambahkan ke `backend/.env` yang asli. `.env.example`
hanya template dan tidak menyimpan konfigurasi runtime.

### Mode aman sekarang

```env
SMARTTWIN_DECISION_ENGINE=rule-based
```

`SMARTTWIN_PPO_MODEL_PATH` belum wajib. Setelah mengubah `.env`, restart backend
karena instance engine dibuat ketika service di-import.

### Menguji handling sebelum ada model

```env
SMARTTWIN_DECISION_ENGINE=ppo
SMARTTWIN_PPO_MODEL_PATH=decision_engine/models/smarttwin_ppo.zip
```

Karena checkpoint belum ada, response semestinya tetap berhasil dengan
`source="ppo-fallback-rule-based"`. Ini mengetes fallback, bukan kualitas PPO.

### Mengaktifkan checkpoint yang sudah lolos evaluasi

Gunakan konfigurasi yang sama setelah file
`decision_engine/models/smarttwin_ppo.zip` benar-benar tersedia. Untuk kembali
ke mode aman, ubah mode menjadi `rule-based` lalu restart backend.

## 7. Instalasi dependency

Gunakan environment backend agar inference dan endpoint memakai versi sama:

```powershell
cd D:\LOMBA\kmipn\smarttwin
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r decision_engine\requirements-rl.txt
python -c "import gymnasium, stable_baselines3; print('PPO dependency OK')"
```

Dependency dipisahkan agar demo rule-based tidak rusak jika instalasi RL gagal.

## 8. Environment training yang sudah tersedia

Training tidak dilakukan lewat endpoint dashboard. Implementasi
`SmartTwinSumoEnv` mengontrol SUMO headless secara langsung:

```python
class SmartTwinSumoEnv(gymnasium.Env):
    observation_space = Box(low=0.0, high=1.0, shape=(25,))
    action_space = MultiDiscrete([4, 10, 10, 10, 10])

    def reset(self, seed=None, options=None):
        # start/reload SUMO dan pilih snapshot demand
        return observation, info

    def step(self, action):
        # action -> CyclePlan -> jalankan decision interval -> metrik
        return observation, reward, terminated, truncated, info
```

Ketentuan penting:

- gunakan `sumo`, bukan `sumo-gui`, saat training;
- satu process SUMO dipertahankan selama episode, jangan restart setiap step;
- reset memilih TrafficState dan seed yang dapat diulang;
- pisahkan snapshot train dan evaluation;
- satu episode sebaiknya 5–10 siklus agar starvation dapat terlihat;
- log setiap komponen reward, bukan hanya reward total.

## 9. Reward: apa yang dihargai dan dihukum?

Reward awal yang sederhana:

```text
reward = -(
    0.45 * normalized_delay
  + 0.35 * normalized_queue
  + 0.15 * normalized_waiting_time
  + 0.05 * phase_change_penalty
) + 0.10 * normalized_throughput
```

Tambahkan penalti besar untuk action invalid dan starvation. Semua metrik harus
dinormalisasi terhadap run rule-based dengan snapshot/seed sama:

```text
normalized_delay      = ppo_delay / max(rule_delay, 1)
normalized_queue      = ppo_queue / max(rule_queue, 1)
normalized_waiting    = ppo_waiting / max(rule_waiting, 1)
normalized_throughput = ppo_throughput / max(rule_throughput, 1)
```

Reward ini titik awal, bukan formula optimum. SUMO-RL memakai perubahan total
delay/waiting time antarlangkah sebagai reward default, dan studi traffic-light
RL juga memakai perbedaan cumulative waiting time antarsiklus:

- [SUMO-RL reward](https://lucasalegre.github.io/sumo-rl/mdp/reward/)
- [Deep Reinforcement Learning for Traffic Light Control](https://arxiv.org/abs/1803.11115)

## 10. Mengapa 50 reward/interaksi tidak cukup?

Yang dihitung adalah **environment timesteps**, bukan “berapa kali diberi
reward/punishment”. Stable-Baselines3 PPO secara default mengumpulkan rollout
`n_steps=2048` per environment sebelum update. Budget 50 timestep bahkan belum
menjadi satu batch default. `total_timesteps` juga batas bawah karena PPO
mengumpulkan kelipatan `n_steps x n_envs`. Rujukan:
[Stable-Baselines3 algorithms guide](https://stable-baselines3.readthedocs.io/en/master/guide/algos.html).

Tahapan realistis:

| Tahap | Timesteps | Tujuan | Siap demo? |
|---|---:|---|---|
| Smoke | 2.048–10.000 | Memastikan env/reward/save-load berjalan | Tidak |
| Awal | 50.000 | Melihat reward dan action mulai terarah | Belum |
| Kandidat | 100.000–300.000 | Evaluasi terhadap rule-based | Mungkin jika lolos gerbang |
| Lebih kuat | 500.000+ dengan minimal 3 seed | Menilai stabilitas | Lebih meyakinkan |

Jumlah bukan jaminan. Policy 100.000 timestep yang menang pada evaluation set
lebih baik daripada 500.000 timestep yang overfit satu snapshot.

## 11. Estimasi waktu training

Waktu tergantung kecepatan SUMO, panjang decision interval, jumlah environment,
dan CPU. GPU hanya membantu MLP kecil; bottleneck utama biasanya SUMO/CPU.

Benchmark dahulu 2.048 atau 10.000 timestep:

```text
steps_per_second = timestep / durasi_detik
estimasi_jam = target_timestep / steps_per_second / 3600
```

Contoh jika benchmark mencapai 20 step/detik:

| Target | Perkiraan waktu |
|---:|---:|
| 10.000 | 8 menit |
| 50.000 | 42 menit |
| 100.000 | 1,4 jam |
| 300.000 | 4,2 jam |

Jika environment hanya 1 step/detik, 100.000 timestep membutuhkan sekitar 27,8
jam. Jadi jawaban “berapa lama” baru valid setelah environment selesai dan
benchmark lokal dijalankan.

## 12. Bentuk training script

Setelah `SmartTwinSumoEnv` tersedia dan lolos `check_env`:

```python
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import EvalCallback
from stable_baselines3.common.env_checker import check_env

train_env = SmartTwinSumoEnv(split="train")
eval_env = SmartTwinSumoEnv(split="eval")
check_env(train_env)

model = PPO(
    "MlpPolicy",
    train_env,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    ent_coef=0.01,
    seed=42,
    verbose=1,
    tensorboard_log="outputs/ppo/tensorboard",
)

model.learn(
    total_timesteps=100_000,
    callback=EvalCallback(
        eval_env,
        best_model_save_path="decision_engine/models",
        eval_freq=10_000,
        n_eval_episodes=10,
        deterministic=True,
    ),
)
model.save("decision_engine/models/smarttwin_ppo")
```

Stable-Baselines3 PPO mendukung action `MultiDiscrete`. Hyperparameter di atas
adalah starting point, bukan hasil tuning SmartTwin. Rujukan:
[Stable-Baselines3 PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html).

## 13. Evaluasi melawan rule-based

Jalankan kedua engine dengan snapshot, seed, dan horizon sama. Simpan:

- average delay;
- average/maximum queue;
- accumulated waiting time;
- throughput;
- jumlah pergantian fase;
- waktu tidak terlayani terlama per approach;
- action invalid dan fallback count.

Evaluation data tidak boleh sama dengan training data. Jalankan minimal 10
episode per seed dan beberapa seed. Laporkan median dan sebaran, bukan hanya run
terbaik.

## 14. Menjalankan endpoint

### Rule-based

Isi `backend/.env`, restart backend, lalu:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/recommendation `
  -ContentType application/json `
  -Body '{"intersectionId":"simpang4-pingit"}'
```

### PPO

Setelah checkpoint lolos evaluasi, isi mode/path PPO, restart backend, lalu
panggil endpoint yang sama. Hasil PPO murni memiliki `source="ppo"`.

Catatan: RecommendationService memprioritaskan cache Scenario Generator yang
segar. Response dapat bertuliskan `scenario-generator` walaupun baseline engine
PPO aktif. Untuk evaluasi PPO murni, hentikan worker/tunggu cache basi atau buat
runner evaluasi terpisah.

## 15. Troubleshooting

| Gejala | Penyebab | Tindakan |
|---|---|---|
| `ppo-fallback-rule-based` | Model/dependency/action bermasalah | Periksa path dan log backend |
| Observation shape mismatch | Kontrak checkpoint berbeda | Retrain dengan 25 fitur |
| Reward tidak naik | Reward salah skala/episode pendek | Log komponen dan bandingkan random/rule |
| Satu arah terus dipilih | Starvation tidak dipenalti | Tambah starvation penalty dan variasi demand |
| Training lambat | SUMO restart atau GUI aktif | Gunakan headless persistent |
| Endpoint tetap rule-based | `.env` belum disalin atau backend belum restart | Periksa `backend/.env` dan restart |

## 16. Gerbang sebelum PPO dipakai demo

PPO hanya boleh aktif jika:

1. nol action invalid pada evaluation;
2. median delay tidak lebih buruk daripada rule-based;
3. queue maksimum tidak memburuk material;
4. tidak ada approach starvation;
5. hasil konsisten pada beberapa seed;
6. fallback tetap lolos ketika checkpoint dihapus/dirusak.

Dengan deadline tanggal 30, selesaikan environment dan smoke training dahulu.
Aktifkan checkpoint pada endpoint demo hanya jika lolos gerbang. Jika belum,
presentasikan PPO sebagai eksperimen yang sudah terintegrasi dan memiliki fallback,
sementara demo utama tetap memakai rule-based yang stabil.

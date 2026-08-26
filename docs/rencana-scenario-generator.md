# Rencana Serah Terima — Scenario Generator + Traffic Simulator + Performance Analysis

**Status per 27 Agustus 2026:** bagian ini (kotak 7-9 di diagram arsitektur — lihat `docs/data-contract.md`) sebelumnya dipegang Rahmat sendiri sebagai bagian dari item 1.5 di `pembagian-tugas-tahap-akhir.md`, **sudah selesai dan terverifikasi jalan** untuk versi dasarnya. Rahmat sekarang tidak bisa lanjut pegang bagian ini, jadi ditulis ulang di sini sebagai dokumen serah terima — supaya tim yang mengambil alih tidak perlu reverse-engineer dari kode dari nol, dan tahu persis batas antara "sudah beres" vs "belum, dan ini rencananya".

Dokumen ini ditulis dengan pola yang sama seperti `rencana-lstm-forecast.md` (dokumen desain Yuli untuk LSTM) — status apa adanya, bukan laporan yang dipoles.

---

## 1. Apa sebenarnya kotak 7-9 ini

Dari `docs/data-contract.md` bagian 4 (`ScenarioResult`, kontrak resmi antar-modul):

```python
class SignalPhase(BaseModel):
    phase_name: str
    green_duration_s: int

class ScenarioResult(BaseModel):
    scenario_id: str
    phases: list[SignalPhase]
    cycle_length_s: int
    avg_delay_s: float
    avg_queue_length_m: float
    throughput_veh: int
```

Tugasnya, secara berurutan:

- **Kotak 7 — Scenario Generator:** dari satu rekomendasi baseline (lengan mana yang perlu hijau + estimasi durasi), buat BEBERAPA kandidat durasi alternatif untuk dibandingkan.
- **Kotak 8 — Traffic Simulator:** jalankan tiap kandidat lewat SUMO (simulasi mikro lalu lintas), ukur delay/antrean/throughput sungguhan dari hasil simulasi — bukan estimasi kasar.
- **Kotak 9 — Performance Analysis:** ubah delay rata-rata jadi Level of Service (LOS, standar HCM 2000), dan bandingkan semua kandidat pada metrik yang sama.

Hasil akhirnya dikonsumsi kotak 10 (Decision Engine) untuk memutuskan skenario mana yang dipakai.

---

## 2. Yang SUDAH ada dan terverifikasi jalan

Semua di bawah ini **sudah ada di kode, sudah dites, sudah pernah dijalankan sungguhan** — bukan rencana, ini modal yang bisa langsung dipakai tim baru.

### 2.1 Kode

| Kotak | Fungsi | File |
|---|---|---|
| 7 | `generate_candidate_plans(baseline: Recommendation) -> list[dict]` | `simulation/scenario_generator.py` |
| 8 | `simulate_candidate(candidate, *, sumo_binary, sumo_config, tls_id, sumo_phase, run_simulation_fn, step_limit) -> dict` | `simulation/scenario_generator.py` |
| 9 | `calculate_los(avg_delay_s: float) -> str` | `simulation/scenario_generator.py` |
| 9 | `select_best_scenario(results: list[dict]) -> dict` (pengganti kotak 10/PPO untuk sekarang) | `simulation/scenario_generator.py` |
| 7-10 gabungan | `class ScenarioEngine` — orkestrator, method `.recommend(state, currentGreenSeconds, currentPhase, forecast=None, forecastWeight=0.5) -> Recommendation` | `simulation/scenario_generator.py` |

`ScenarioEngine.recommend()` **bentuknya PERSIS sama** dengan `RuleBasedEngine.recommend()` (`decision_engine/rule_based_engine.py`) — jadi dari sudut pandang pemanggil, dua-duanya bisa saling tukar tanpa ubah kode lain. Ini penting dipahami tim baru: kalau nanti PPO (item 1.6) jadi, tinggal ganti kelas ini, bukan tulis ulang alur.

### 2.2 Cara kerjanya, langkah demi langkah

```
RuleBasedEngine.recommend()          -- baseline: lengan mana + estimasi durasi
      |
generate_candidate_plans()           -- KOTAK 7: 3 kandidat durasi
      |  (a) baseline apa adanya
      |  (b) agresif ke lengan tersibuk (+20%, dijepit ke MAX_GREEN_SECONDS)
      |  (c) merata (ditarik ke arah MIN_GREEN_SECONDS)
      |
simulate_candidate() x3              -- KOTAK 8: tiap kandidat = 1 sesi TraCI baru
      |  - traci.start() sesi baru
      |  - traci.trafficlight.setProgram(tlsId, "safe-yellow")
      |  - traci.trafficlight.setPhase() + setPhaseDuration() sesuai kandidat
      |  - run_simulation_fn() -- ini DI-SUNTIK dari run_tls_simulation.py,
      |    fungsi runSimulation() yang sama dipakai run penuh, TIDAK
      |    diduplikasi. step_limit=90 (SHORT_SIM_STEPS, pendek, bukan 300
      |    seperti run penuh)
      |  - traci.close()
      |
calculate_los() per kandidat         -- KOTAK 9: HCM 2000 (A <=10s ... F >80s)
      |
select_best_scenario()               -- KOTAK 10 (sementara, ganti PPO):
                                         skor gabungan 50% delay + 50% antrean,
                                         dinormalisasi ke kandidat terburuk di
                                         batch itu, pilih skor terendah.
                                         Deterministik.
```

Dipanggil dari `simulation/run_tls_simulation.py::createDecision()` (baris ~747), yang dipanggil dari `main()`. Jalankan manual:

```powershell
cd simulation
.\.venv\Scripts\Activate.ps1
$env:SUMO_HOME = "$PWD\.venv\Lib\site-packages\sumo"
python run_tls_simulation.py
```

(Prasyarat `SUMO_HOME` ini WAJIB — lihat `CLAUDE.md` bagian "SUMO / TraCI setup". Kalau `backend/.venv` yang dipakai untuk test Python murni tanpa TraCI beneran jalan, itu juga bisa karena sudah ada `eclipse-sumo`/`traci`/`sumolib` di sana juga — lihat catatan lingkungan di bagian 5.)

### 2.3 Program TLS (traffic light) yang dipakai

Bukan program *actuated* bawaan network file lagi — sekarang ada program eksplisit `simulation/network/tls_safe.add.xml` (`programID="safe-yellow"`, diaktifkan lewat `traci.trafficlight.setProgram(tlsId, "safe-yellow")` di `startSumo()`):

```
8 fase: south(hijau 39s, index 0) -> kuning 4s -> east(hijau 39s, index 2)
        -> kuning 4s -> north(hijau 39s, index 4) -> kuning 4s
        -> west(hijau 39s, index 6) -> kuning 4s
```

`approachToPhase` di `run_tls_simulation.py` (baris ~337) sudah dicocokkan ke index ini. **Ini penting bagi tim baru:** kalau mau ubah urutan/jumlah fase di masa depan, dua tempat ini (`tls_safe.add.xml` dan `approachToPhase`) harus diubah BARENGAN, index-nya harus tetap kelipatan 2 (hijau selalu di index genap, kuning di index ganjil).

### 2.4 Sudah tersambung ke forecast (dikerjakan Yuli, 26 Agustus malam)

`ScenarioEngine.recommend()` sekarang terima parameter opsional `forecast`/`forecastWeight`, diteruskan ke `RuleBasedEngine` internalnya sebelum generate 3 kandidat — jadi baseline yang dibandingkan sudah mempertimbangkan prediksi 60 detik ke depan, bukan cuma kondisi sesaat. Detail penuh ada di `pembagian-tugas-tahap-akhir.md` item 2.4. Tim baru **tidak perlu mengerjakan ulang bagian ini** — sudah selesai, tinggal dipakai.

### 2.5 Verifikasi yang sudah ada

- Run end-to-end sungguhan: `simulations` id 9, `STATUS: SUCCESS`. Contoh hasil nyata: baseline & agresif sama-sama kejepit `MAX_GREEN_SECONDS`, kandidat `balanced` (38s) menang karena antrean jauh lebih pendek (35m vs 42m) walau delay sedikit lebih tinggi (14.05s vs 13.58s) — `select_best_scenario()` bekerja sesuai desain (skor gabungan, bukan cuma delay).
- 8 unit test murni Python (tanpa SUMO beneran jalan) di `backend/tests/test_scenario_generator.py` — semua lolos.
- Hasil disimpan ke tabel `simulationMetrics` di Supabase lewat `SimulationResultWriter.saveMetrics()`/`saveSimulationResult()`, termasuk field forecast (`forecastApplied`/`forecastWeight`/`forecastFallbackUsed`/`forecastSource`, lihat 2.4).

---

## 3. Batasan yang SENGAJA ada (bukan kelupaan, jangan "diperbaiki" tanpa didiskusikan dulu)

- **Cuma 3 kandidat, bukan grid pencarian besar.** Keputusan tim 25 Agustus: Scenario Generator versi RINGAN, bukan versi penuh. Kalau tim baru mau menambah jumlah kandidat, itu perubahan scope, bukan bug fix — diskusikan dulu, jangan langsung ubah.
- **`SHORT_SIM_STEPS = 90`** — sengaja pendek (bandingkan simulasi 300 langkah di run penuh), supaya 3 simulasi per keputusan tidak terlalu lama. Angka ini di tengah rentang 60-120 detik yang diminta dokumen tugas awal, bukan hasil kalibrasi presisi.
- **Kandidat "agresif" pakai +20% ke lengan tersibuk** — **ini yang PALING PENTING dipahami tim baru:** angka 20% ini ILUSTRATIF, bukan hasil formula lalu lintas (mis. Webster's formula) yang dikalibrasi untuk Simpang Pingit. Kalau laporan teknis menyebut angka ini, harus jujur ditulis "skenario pembanding demo", BUKAN "terkalibrasi/optimal".

---

## 4. Yang BELUM ada — ini kerjaan buat tim yang mengambil alih

### 4.1 [Prioritas tertinggi] Kotak 7-9 belum nyambung ke dashboard live

Ini yang paling substansial. Sekarang `ScenarioEngine` **cuma jalan di jalur batch** (`run_tls_simulation.py`, dijalankan manual dari terminal). Dashboard live (`/recommendation`, `/signal/status`, dipoll tiap 5 detik oleh frontend) masih pakai `RuleBasedEngine` polos, TIDAK lewat Scenario Generator sama sekali.

**Kenapa belum disambungkan dari awal:** menjalankan 3 sesi simulasi SUMO penuh per HTTP request itu terlalu berat untuk endpoint yang dipoll tiap 5 detik — bisa berujung timeout / server macet kalau 2 user buka dashboard bersamaan.

**Opsi desain buat tim baru pertimbangkan** (pola sama seperti keputusan 6.2 untuk LSTM→Decision Engine dulu):

- **Opsi A — Cache dengan interval lebih longgar.** `ScenarioEngine` dijalankan di BACKGROUND (bukan tiap request), misal tiap kali fase berganti (setiap ~40 detik, bukan tiap 5 detik poll), hasilnya di-cache, endpoint live baca cache itu. Mirip pola `SignalService._cycle_plan` yang sudah ada (lihat `signal_service.py`) — tapi ScenarioEngine butuh proses SUMO terpisah, jadi perlu dipikirkan apakah dijalankan di thread terpisah/proses terpisah dari backend API (SUMO/TraCI itu blocking dan berat, tidak boleh jalan di request-handling thread FastAPI utama).
- **Opsi B — Simulasi lebih ringan/cepat khusus live** (`step_limit` lebih kecil dari 90, atau ganti ke model delay analitik non-SUMO untuk keputusan cepat, SUMO cuma untuk validasi periodik). Lebih cepat tapi butuh kalibrasi ulang supaya hasilnya tetap representatif.
- **Opsi C — Biarkan tetap batch-only untuk demo ini**, dokumentasikan jujur bahwa Scenario Generator adalah komponen "siap pakai, terverifikasi, tapi belum live" — kalau waktu tim terbatas, ini pilihan yang sah dan sudah pernah diambil sebelumnya (bukan berarti gagal).

**Rekomendasi:** mulai dari Opsi C dulu (dokumentasikan apa adanya) kalau waktu mepet; kalau ada slot waktu, Opsi A paling realistis karena infrastrukturnya (pola cache) sudah ada presedennya di `SignalService`.

### 4.2 Siklus 4-lengan penuh belum diterapkan ke SUMO live

Terkait tapi beda dari 4.1: `run_tls_simulation.py` masih memanggil `RuleBasedEngine.recommend()` (satu lengan pemenang per run) lewat `ScenarioEngine`, BUKAN `recommend_cycle()` (yang menghitung ke-4 lengan sekaligus, sudah dipakai dashboard live sejak item 1.7). Untuk menerapkan rotasi 4-lengan penuh ke SUMO, butuh `traci.trafficlight.setProgramLogic()` (API beda dari `setPhase()`/`setPhaseDuration()` yang dipakai sekarang) untuk membuat program TLS custom yang durasinya dinamis sesuai `CyclePlan`.

### 4.3 Kalibrasi kandidat "agresif" (+20%)

Kalau ada anggota tim yang punya waktu/minat riset — ganti angka 20% ilustratif ini dengan sesuatu yang berdasar (Webster's formula atau kalibrasi dari data delay simulasi yang sudah ada). Ini P2, bukan blocker demo.

---

## 5. Setup & verifikasi untuk tim baru

1. **Environment:** ikuti `CLAUDE.md` bagian "SUMO / TraCI setup" — `SUMO_HOME` **wajib** di-export sebelum jalankan apa pun yang impor `traci`. Ada 2 venv terpisah (`simulation/.venv` dan `backend/.venv`) — `simulation/.venv` **tidak punya `supabase`**, jadi kalau mau jalankan test yang mengimpor `run_tls_simulation.py` (yang menyentuh Supabase), pakai `backend/.venv`. Ini quirk lingkungan yang sudah diketahui, bukan bug.
2. **Test yang harus tetap lolos setelah perubahan apa pun:**
   - `backend/tests/test_scenario_generator.py` (8 test, murni Python, tanpa SUMO)
   - `simulation/tests/test_forecast_client.py` (8 test, jalankan pakai `backend/.venv`)
   - Full suite backend: `pytest -q` di `backend/` — per 27 Agustus, **52 passed**, jadi patokan baseline
3. **Verifikasi end-to-end (butuh SUMO beneran jalan):** `python run_tls_simulation.py` dari `simulation/`, harus keluar `STATUS: SUCCESS` dan baris baru tersimpan ke tabel `simulations`/`simulationMetrics` di Supabase.

---

## 6. Rujukan cepat — file mana ngapain

| Perlu ngapain | Buka file ini |
|---|---|
| Ubah logika 3 kandidat / tambah kandidat baru | `simulation/scenario_generator.py::generate_candidate_plans()` |
| Ubah cara skor/pemilihan pemenang | `simulation/scenario_generator.py::select_best_scenario()` |
| Ubah ambang LOS | `simulation/scenario_generator.py::_LOS_THRESHOLDS` |
| Ubah durasi/urutan fase TLS | `simulation/network/tls_safe.add.xml` **DAN** `simulation/run_tls_simulation.py::approachToPhase` (dua-duanya, barengan) |
| Sambungkan ke dashboard live | Baca bagian 4.1 di atas dulu — ini bukan perubahan kecil |
| Ganti metrik yang diukur dari SUMO | `simulation/run_tls_simulation.py::runSimulation()` |
| Cek kontrak resmi `ScenarioResult` | `docs/data-contract.md` bagian 4 |
| Status tugas tim lengkap (semua orang, bukan cuma bagian ini) | `docs/pembagian-tugas-tahap-akhir.md` item 1.5, 1.7, dan bagian 6 |

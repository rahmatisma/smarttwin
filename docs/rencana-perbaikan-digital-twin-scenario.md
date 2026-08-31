# Rencana Perbaikan — Panel Skenario & Statistik di Halaman Digital Twin

**Ditulis: 30 Agustus 2026, oleh Rahmat (mengambil alih dari Melpi).** Dokumen ini
bukan status tracker — `docs/STATUS-DAN-SISA-KERJA.md` tetap satu-satunya itu.
Ini catatan teknis khusus 1 fitur: kenapa dropdown skenario (Baseline/Aggressive/
Balanced) di halaman `/digitaltwin` kelihatan nyangkut, dan kenapa 3 kartu
statistik di bawahnya selalu kosong.

Ditemukan dari screenshot: dropdown di-set ke "Balanced", status simulasi
"Running", tapi panel Rekomendasi nyangkut di "Loading... Fetching simulation
recommendation" selamanya, dan kartu "Average Speed"/"Queue Length"/"Traffic
Flow" selalu nampilin `"-"` / `"Data belum tersedia"`.

---

## Ringkasan: 3 masalah, bukan 1

| # | Masalah | Lokasi | Tingkat |
|---|---|---|---|
| 1 | Ganti skenario sambil simulasi jalan **tidak mengubah simulasi sama sekali** | Backend (`simulation_service.py`) | 🔴 Akar masalah sebenarnya |
| 2 | Panel Rekomendasi nyangkut "Loading..." tanpa cara jelas keluar dari situ | Frontend (`digitaltwinview.tsx`) | 🟡 Akibat dari #1 + UX |
| 3 | Average Speed / Queue Length / Traffic Flow selalu `"-"` | Frontend (hardcode) + Backend (belum dihitung/diekspos) | 🟡 Belum pernah dikerjakan |

Masalah #2 yang kelihatan di screenshot itu **gejala**, bukan akar masalahnya. Kalau cuma benerin tombolnya doang tanpa benerin #1, tombolnya akan kelihatan jalan tapi simulasi di baliknya tetap gak berubah.

---

## Masalah 1 — Backend reuse controller tanpa cek skenario berubah

### Akar masalah

`backend/app/services/simulation_service.py`, method `_ensure_sumo()` (baris ±352-416):

```python
if (
    self.controller is not None
    and self.controller.is_running()
    and self.controller.is_gui != request.gui
):
    self.controller.close()
    self.controller = None

if (
    self.controller is not None
    and self.controller.is_running()
):
    # ... cek intersection cocok ...
    print("Menggunakan instance SUMO yang sama.")
    return self.controller          # <-- BERHENTI DI SINI

# Baru di bawah ini controller BARU dibuat dengan request.scenario baru:
controller = SumoController(
    config_file=config_file,
    seed=request.seed,
    scenario=request.scenario,
)
```

Restart cuma dipicu kalau **mode GUI berubah** (`is_gui != request.gui`). Kalau GUI-nya sama tapi `request.scenario` beda dari skenario yang lagi jalan, kode langsung `return self.controller` yang LAMA — `SumoController(..., scenario=request.scenario)` yang baru **tidak pernah dibuat**. Jadi walau frontend berhasil manggil `/api/v1/simulation/run` dengan `scenario: "Balanced"`, backend diam-diam tetap pakai skenario yang pertama kali dipilih waktu simulasi mulai jalan.

Bukti pendukung: `SumoController` beneran nyimpen skenarionya sendiri di `self.scenario` (`sumo_controller.py:291`) — jadi ada nilai buat dibandingkan, cuma belum dipakai buat keputusan restart.

### Solusi

Tambahkan pengecekan skenario, persis pola yang sudah ada buat `is_gui`:

```python
if (
    self.controller is not None
    and self.controller.is_running()
    and (
        self.controller.is_gui != request.gui
        or self.controller.scenario != request.scenario
    )
):
    self.controller.close()
    self.controller = None
```

### Rancangan detail

1. `backend/app/services/simulation_service.py` — ubah kondisi restart di `_ensure_sumo()` (baris ±361-367) supaya juga bandingkan `self.controller.scenario != request.scenario`, bukan cuma `is_gui`.
2. Pastikan `SumoController.scenario` (`sumo_controller.py:291`) memang di-set ulang dengan benar tiap kali constructor baru dipanggil — sudah beres dari kode yang ada, tinggal diverifikasi lewat test.
3. **Test baru**: panggil `/api/v1/simulation/run` dua kali berturut-turut dengan `scenario` beda (mis. "Baseline" lalu "Balanced"), `gui` sama — assert controller kedua BEDA instance dari yang pertama (atau minimal `close()` kepanggil di antaranya), dan `cyclePlan`/`active_cycle_plan` yang dihasilkan benar-benar beda sesuai skenario baru.
4. **Efek samping yang harus diverifikasi**: karena sekarang restart lebih sering terjadi (tiap ganti skenario, bukan cuma tiap ganti mode GUI), pastikan `self.controller.close()` benar-benar membersihkan proses SUMO lama (tidak nyisa proses `sumo-gui` zombie seperti yang pernah ditemukan sebelum ini — lihat riwayat pembersihan proses 30 Agustus). Cek manual: jalankan run→run→run dengan skenario beda 3x, lalu cek `Get-Process sumo-gui` cuma ada 1 instance yang hidup.

---

## Masalah 2 — Panel Rekomendasi nyangkut di "Loading..."

### Akar masalah

`frontend/src/components/digitaltwin/digitaltwinview.tsx`:

- Baris ±707-722: `onChange` dropdown skenario cuma `setRecommendationLoading(true)` kalau skenario baru beda dari yang lagi jalan — **tidak** memanggil `handleStartSimulation()`.
- Baris ±765-774: tombol **"Start Simulation"** (yang manggil `handleStartSimulation()`, satu-satunya jalan `setRecommendationLoading(false)` lewat baris 228) **cuma dirender kalau `status !== "running"` dan `status !== "paused"`**. Kalau simulasi lagi "running", tombol ini gak ada — cuma ada "Pause Simulation".

Jadi urutan yang bikin nyangkut: user ganti dropdown ke "Balanced" → `recommendationLoading = true` → tapi gak ada tombol yang kepencet buat manggil `/api/v1/simulation/run` lagi → loading selamanya.

### Solusi

Ganti dropdown **langsung memicu re-run** kalau simulasi sedang jalan, bukan nunggu user cari tombol yang gak ada. Dua opsi desain:

**Opsi A (disarankan, paling sedikit perubahan):** di `onChange` dropdown, kalau `status === "running"` dan skenario benar-benar berubah, langsung panggil `handleStartSimulation()` (yang sekarang, dengan perbaikan Masalah 1, akan memicu restart controller dengan skenario baru).

**Opsi B (lebih eksplisit buat user):** tampilkan tombol kecil "Terapkan Skenario" di sebelah dropdown, cuma muncul kalau skenario yang dipilih beda dari yang lagi jalan. User klik manual — lebih jelas kapan permintaan restart dikirim (SUMO restart makan waktu ~1-2 detik, GUI-nya sempat kedip), tapi butuh 1 komponen UI baru.

Rekomendasi: **Opsi A dulu** (cepat, konsisten dengan filosofi auto-refresh yang sudah dipakai di tempat lain di dashboard), Opsi B bisa nyusul kalau ternyata auto-restart kerasa mengganggu pas demo.

### Rancangan detail

1. `digitaltwinview.tsx` baris ±709-722, di `onChange`:
   ```tsx
   onChange={(e) => {
       const newScenario = e.target.value as ScenarioType;
       setScenario(newScenario);

       if (newScenario === "Traffic Realtime") {
           setRecommendationLoading(false);
           setRunningScenario("Traffic Realtime");
       } else if (newScenario !== runningScenario) {
           setRecommendationLoading(true);
           if (status === "running") {
               // Simulasi sudah jalan -- langsung terapkan skenario baru,
               // jangan nunggu tombol "Start Simulation" yang gak
               // dirender pas status === "running".
               handleStartSimulation();
           }
           // Kalau status === "idle", biarkan tombol "Start Simulation"
           // yang memicu (perilaku lama, sudah benar).
       } else {
           setRecommendationLoading(false);
       }
   }}
   ```
2. Cek `handleStartSimulation()` (baris ±199-235) aman dipanggil dari `onChange` (bukan cuma dari `onClick` tombol) — sepertinya aman karena cuma `async function` biasa, tapi perlu dites `loading` state-nya gak bentrok (dropdown gak boleh keklik dobel pas lagi proses restart).
3. **Test manual**: mulai simulasi dengan "Traffic Realtime", tunggu jalan, ganti dropdown ke "Balanced" — panel Rekomendasi harus keluar dari "Loading..." dalam beberapa detik dan nampilin data skenario "Balanced" (delay 22.84s, LOS C, sesuai data yang sudah diverifikasi ada di backend).

---

## Masalah 3 — 3 kartu statistik gak pernah diisi

### Akar masalah

`digitaltwinview.tsx` baris ±642-661 — nilainya **hardcode**, bukan bug runtime:

```tsx
<StatCard label="Average Speed" value="-" change="Data belum tersedia" ... />
<StatCard label="Queue Length" value="-" change="Data belum tersedia" ... />
<StatCard label="Traffic Flow" value="-" change="Data belum tersedia" ... />
```

Beda dari "Current Vehicles" yang beneran hidup (`value={vehicles.length}`), 3 kartu ini memang belum pernah disambungkan ke data apa pun.

**Masalah tambahan di sisi backend:** datanya juga belum semuanya ada.

- `GET /api/v1/simulation/state` (yang dipoll frontend tiap 500ms — lihat `digitaltwinview.tsx:187-197`) cuma balikin `vehicles, signals, simulationTimeSeconds, detectedVehicleCount, trafficTimestamp, cyclePlan`. Tidak ada waiting time, queue, throughput, ATAU speed.
- `SimulationService.status()` (`simulation_service.py:823`) **sudah menghitung** `averageWaitingTimeSeconds`, `activeVehicles`, `departedVehicles`/`arrivedVehicles` (≈ throughput) lewat `SumoController.get_metrics()` — **tapi endpoint ini gak pernah didaftarkan** ke router (`backend/app/api/routes/simulation.py` cuma punya `/run`, `/stop`, `/pause`, `/resume`, `/state`, `/stream`, `/frame` — tidak ada `/status`). Kode-nya nganggur, gak keakses dari mana pun.
- **Average Speed sama sekali belum pernah dihitung di mana pun** saat simulasi live — `active_vehicles_data` (`sumo_controller.py:1313-1331`, sumber data `vehicles` di `/state`) cuma nyimpen `id, x, y, angle, type`, tidak ada `speed`. Perlu ditambah `self.traci.vehicle.getSpeed(vehicle_id)` di loop yang sama.
- **Queue Length juga belum ada** untuk simulasi live (beda dari queue length yang dihitung `traffic_state_builder.py` dari CSV CV — itu jalur terpisah, offline). Tapi `SumoController.EDGE_MASUK` (`sumo_controller.py:123`) sudah ada — dict approach → edge masuk — tinggal panggil `self.traci.edge.getLastStepHaltingNumber(edge)` per approach di loop yang sama dengan `active_vehicles_data`.

### Solusi

**Backend** — tambah field baru ke `get_simulation_state()` (bukan lewat `/status` yang terpisah, biar frontend cuma perlu 1 sumber poll yang sudah ada):

1. Di loop `current_vehicles_data` (`sumo_controller.py:1313-1331`), tambah `"speed": self.traci.vehicle.getSpeed(vehicle_id)` per kendaraan.
2. Tambah method baru `_compute_live_traffic_metrics()` di `SumoController` yang, sekali per step, hitung:
   - `averageSpeedKmh` = rata-rata speed semua `active_vehicles_data` (konversi m/s → km/h, ×3.6)
   - `queueLengthVeh` = jumlah dari `getLastStepHaltingNumber(edge)` untuk semua edge di `EDGE_MASUK`
   - `throughputVehPerMin` = `arrived_total` (sudah ada, dipakai di `get_metrics()`) dibagi `simulationTimeSeconds` lalu ×60
3. `SimulationService.get_simulation_state()` (`simulation_service.py:890-909`) — tambahkan 3 field ini ke dict yang dikembalikan, ambil dari `self.controller` punya method/attribute baru di atas.

**Frontend** — `digitaltwinview.tsx`:

4. Tambah state baru (atau perluas state simulasi yang sudah ada dari polling `/state`) buat nangkep `averageSpeedKmh`, `queueLengthVeh`, `throughputVehPerMin` dari response.
5. Ganti 3 `StatCard` yang hardcode (baris ±642-661) supaya pakai state itu, dengan fallback `"-"` / `"Data belum tersedia"` cuma kalau `status === "idle"` (belum ada simulasi jalan) — bukan selalu, sama seperti pola `"Current Vehicles"` yang sudah benar di baris 637.

### Rancangan detail — urutan kerja

1. `sumo_controller.py`: tambah `speed` ke `active_vehicles_data`, tambah method hitung 3 metrik baru
2. `simulation_service.py`: expose 3 field baru itu di `get_simulation_state()`
3. **Test baru**: `test_simulation_service.py` (atau file test yang relevan) — assert `get_simulation_state()` punya key `averageSpeedKmh`/`queueLengthVeh`/`throughputVehPerMin`, bertipe angka, `0` (bukan `None`/error) kalau belum ada kendaraan
4. `digitaltwinview.tsx`: sambungkan ke 3 `StatCard`
5. Test manual: jalankan simulasi, tunggu beberapa kendaraan muncul, pastikan angka di 3 kartu itu berubah-ubah (bukan statis di 0) sepanjang simulasi jalan

---

## Urutan pengerjaan disarankan

1. **Masalah 1 dulu** (backend, `_ensure_sumo`) — ini akar masalah, dan paling kecil scope-nya (~5 baris)
2. **Masalah 2** (frontend, `onChange`) — bisa langsung dites begitu #1 beres, karena saling bergantung
3. **Masalah 3** (backend + frontend, lebih besar) — independen dari #1/#2, bisa dikerjakan kapan saja, tapi taruh belakangan karena bukan yang bikin panel nyangkut

**Estimasi kasar:** Masalah 1 ±30 menit, Masalah 2 ±30 menit, Masalah 3 ±2 jam (karena nambah komputasi baru + field baru di 2 layer + wiring frontend).

## Cara verifikasi semuanya beres

- Buka `/digitaltwin`, pilih "Traffic Realtime", klik "Start Simulation"
- Tunggu jalan, ganti dropdown ke "Balanced" — panel Rekomendasi harus keluar dari Loading dalam <5 detik, nampilin LOS/delay yang beda dari sebelumnya
- Ganti lagi ke "Aggressive" — harus berubah lagi, bukan angka yang sama diulang
- Perhatikan 3 kartu statistik — Average Speed/Queue Length/Traffic Flow harus nampilin angka yang berubah-ubah, bukan `"-"` terus
- `pytest backend/tests/` tetap hijau (kecuali 1 kegagalan checkpoint PPO yang sudah diketahui, tidak terkait ini)

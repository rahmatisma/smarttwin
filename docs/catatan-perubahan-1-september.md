# Catatan Perubahan — 1 September 2026

**Ini BUKAN dokumen status.** Status tunggal tetap [`STATUS-DAN-SISA-KERJA.md`](STATUS-DAN-SISA-KERJA.md). Dokumen ini cuma **catatan satu sesi kerja**: apa yang diubah, kenapa, dan bagaimana cara membuktikannya. Dibuat supaya tim tidak perlu membaca 1.200 baris diff untuk tahu apa yang terjadi.

**Fokus sesi ini: halaman `/digitaltwin` + isolasi SUMO + 5 bug yang ketemu sambil jalan.**

> ⚠️ **Semua perubahan masih di working tree, BELUM di-commit.** Jalankan `git status` untuk melihatnya. Silakan review dulu sebelum commit.

---

## 0. Ringkasan buat yang buru-buru

| # | Yang berubah | Kenapa penting |
|---|---|---|
| 1 | Kartu statistik Digital Twin (Queue Length, Traffic Flow) **hidup** | Sebelumnya hardcode `"-"`, belum pernah disambungkan |
| 2 | Dashboard & `/digitaltwin` jadi **2 instance SUMO terpisah** | Sebelumnya berbagi satu instance, saling ganggu |
| 3 | Skenario "Traffic Realtime" **nempel** ke instance dashboard | Supaya SUMO tidak kebuka dobel untuk hal yang sama |
| 4 | Dropdown skenario **beneran diterapkan** saat simulasi jalan | Sebelumnya cuma nyangkut loading, tidak ada efek |
| 5 | Panel "Signal Recommendation" **diganti** panel "Hasil Simulasi" | Ternyata panel lama baca cache produksi, bukan simulasi yang ditonton |
| 6 | Kartu **"Durasi Sinyal Per Lengan"** + **3 grafik tren** | Supaya beda antar skenario kelihatan, bukan cuma tersirat |
| 7 | 5 bug diperbaiki (lihat bagian 3) | Termasuk `Server disconnected` dan jendela SUMO yang tidak nutup |

**Bukti eksekusi (dijalankan langsung, bukan klaim):**
- `pytest backend/tests simulation/tests -q` → **112 passed, 0 failed**
- `npm run build` (frontend) → **sukses, 13/13 route, 0 error TypeScript**

---

## 1. File yang berubah

12 file dimodifikasi, 2 dokumen baru.

| File | Baris | Inti perubahan |
|---|---:|---|
| `backend/app/simulation/sumo/sumo_controller.py` | +187 | Metrik live baru, `context` per instance, `--quit-on-end`, pencatatan gagal-sisip |
| `backend/app/services/simulation_service.py` | +261 | **Multi-instance** (`controllers` dict), expose metrik baru, perbaikan injeksi demand |
| `backend/tests/test_simulation_service.py` | +111 | 1 test baru + perluasan assertion |
| `backend/app/api/routes/simulation.py` | +27 | Parameter `context` di semua endpoint |
| `backend/app/schemas/simulation.py` | +11 | Field `context` di request schema |
| `backend/app/services/supabase_client.py` | +43 | **Paksa HTTP/1.1** (perbaikan `Server disconnected`) |
| `backend/app/services/simulation_stream_service.py` | +7 | Stream per-context |
| `backend/app/main.py` | +2 | `stop_all()` saat shutdown |
| `frontend/src/components/digitaltwin/digitaltwinview.tsx` | +828 | Panel baru, grafik, isolasi context, tata letak |
| `frontend/src/components/DigitalTwinPanel.tsx` | +24 | Context dashboard, hitungan kendaraan terlihat |
| `frontend/src/app/page.tsx` | +4 | Context dashboard di polling & sync-clock |
| `docs/rencana-perbaikan-digital-twin-scenario.md` | +45 | Tandai Masalah 3 selesai + koreksi |
| `docs/audit_final_31agustus.md` | baru | Audit menyeluruh (dokumen terpisah) |
| `docs/catatan-perubahan-1-september.md` | baru | Dokumen ini |

---

## 2. Perubahan fitur

### 2.1 Kartu statistik yang tadinya mati

**Masalah:** kartu "Queue Length" dan "Traffic Flow" di `/digitaltwin` isinya `value="-"` — hardcode, memang belum pernah disambungkan ke data apa pun (cuma "Current Vehicles" yang hidup).

**Perbaikan:** dihitung tiap step di loop SUMO, bukan panggilan TraCI baru dari endpoint (mengikuti pola yang sudah ada — endpoint `/state` sengaja dijaga murah supaya polling dashboard tidak tertahan).

| Metrik | Dihitung dari |
|---|---|
| Queue Length | `getLastStepHaltingNumber()` di 4 edge `EDGE_MASUK` |
| Traffic Flow | Jumlah kendaraan `arrived` dalam **60 detik simulasi terakhir** |

**2 koreksi cara hitung setelah dicoba user:**

1. **Traffic Flow awalnya salah konsep** — dihitung `total arrived ÷ total waktu × 60`, yaitu **rata-rata sejak simulasi mulai**. Di simulasi yang sudah jalan 15 menit angkanya nyaris berhenti bergerak, jadi tidak terasa "live". Diganti jadi jendela bergerak 60 detik terakhir (`deque` `_arrival_timeline`).

2. **Queue Length awalnya menjumlahkan 4 lengan** jadi satu angka (mis. "7 kendaraan") — tidak actionable, dan user wajar bingung karena mengira itu satu antrean. Diganti jadi **lengan terpadat + namanya** (mis. "Utara: 4"), konsisten dengan panel lain di halaman itu yang juga per-lengan.

---

### 2.2 Isolasi SUMO: dashboard vs `/digitaltwin`

> **Ini perubahan arsitektur terbesar di sesi ini.**

**Masalah:** backend cuma punya **satu slot SUMO global** (`SimulationService.controller`). Akibatnya:
- Buka `/digitaltwin` → langsung "mewarisi" simulasi dashboard yang sudah jalan, padahal user belum klik Start.
- Pause di `/digitaltwin` → ikut mem-pause tampilan live di dashboard.

**Perbaikan:** `self.controller` (satu) → `self.controllers: dict[str, SumoController]` (satu per **context**).

```
context "dashboard"    → simulasi live realtime, auto-jalan, umur panjang (ikut durasi video)
context "digitaltwin"  → sandbox skenario, idle sampai user klik Start
```

Yang ikut berubah supaya konsisten:
- Semua endpoint (`/run`, `/state`, `/pause`, `/resume`, `/stop`, `/stream`, `/frame`, `/sync-clock`, `/scenario`) terima parameter `context`.
- File screenshot dipisah per context (`frame_dashboard.jpg`, `frame_digitaltwin.jpg`) — kalau tidak, 2 instance akan saling menimpa gambar.
- `stop_all()` dipanggil saat backend shutdown, supaya **semua** instance ditutup, bukan cuma satu.

**Bukti:** test baru `test_contexts_are_fully_isolated` — pause & stop di context `"digitaltwin"` tidak mengubah state controller `"dashboard"` sama sekali.

#### Koreksi penting setelah masukan user

Desain awal saya salah: **"Traffic Realtime" ikut bikin instance terpisah**, jadi SUMO kebuka 2 padahal isinya hal yang sama. Diperbaiki:

| Skenario dipilih | Context yang dipakai | Efek |
|---|---|---|
| **Traffic Realtime** | `dashboard` | **Nempel** ke instance dashboard, tidak bikin SUMO baru |
| Baseline / Aggressive / Balanced | `digitaltwin` | Sandbox terpisah, tidak menyentuh dashboard |

Aturan tambahan yang ikut dipasang:
- Ganti **sesama sandbox** (Aggressive → Baseline): SUMO **tidak restart**, cuma program TLS-nya diganti lewat TraCI. Tidak ada window baru berkedip.
- Ganti **sandbox → Traffic Realtime** (beda context): sandbox lama **di-stop otomatis** supaya tidak nganggur nyala.
- Instance `"dashboard"` **tidak pernah** dimatikan dari halaman `/digitaltwin` — apa pun yang user lakukan di sana.
- Tombol Pause/Stop **disembunyikan** saat skenario Traffic Realtime, diganti keterangan *"Live dari dashboard — kendalikan dari halaman Dashboard"*. Alasannya: instance-nya memang sama, jadi Pause dari sini akan ikut mem-pause tampilan live yang mungkin sedang dilihat orang lain. Ini pengaman yang disengaja, bukan keterbatasan.

---

### 2.3 Dropdown skenario akhirnya berfungsi

**Masalah (temuan audit, sudah lama ada):** ganti dropdown skenario **sambil simulasi jalan** tidak ada efeknya — `onChange` cuma menyalakan flag loading, tidak pernah memanggil `handleStartSimulation()`. Karena tombol "Start Simulation" tidak dirender saat status `running`, panel Rekomendasi nyangkut *"Menerapkan skenario…"* selamanya, dan SUMO tetap pakai skenario lama.

**Perbaikan:** `onChange` sekarang benar-benar menerapkan skenario baru (stop sandbox lama kalau pindah context, lalu jalankan yang baru).

**Catatan teknis buat yang mau baca kodenya:** `handleStartSimulation()` sekarang menerima parameter skenario opsional. Ini **wajib** dipakai saat dipanggil tepat setelah `setScenario()`, karena `setState` React itu asinkron — kalau baca `scenario` dari closure, nilainya masih yang lama.

---

### 2.4 Panel "Signal Recommendation" → "Hasil Simulasi"

**Temuan yang memicu perubahan ini:** user merasa panel itu tidak nyambung dengan simulasi yang ditonton. Setelah dicek ke kode (`digital_twin.py` + `digitaltwinview.tsx`), ternyata **benar**:

> Panel "Signal Recommendation" membaca **`liveScenarioCache`** — cache yang sama dipakai sistem produksi (dashboard, `scenario_worker.py` yang jalan tiap 60 detik). Ganti dropdown ke "Aggressive" **tidak** memicu simulasi baru untuk menghitung delay/queue/LOS-nya; itu cuma **memfilter** salah satu dari 3 kandidat yang sudah dihitung worker produksi, terlepas dari apa yang SUMO di layar sedang lakukan.

Lebih parah lagi: ada jalur fallback (saat cache kosong/basi) yang cuma menghitung durasi lampu **tanpa menjalankan SUMO** — jadi angka delay/queue/LOS di kondisi itu tidak akurat.

**Perbaikan:** panel lama dicopot dari `/digitaltwin`, diganti panel **"Hasil Simulasi"** yang isinya dihitung **langsung dari instance SUMO yang sedang ditonton**:

| Yang ditampilkan | Sumber |
|---|---|
| Avg Delay | Rata-rata `getAccumulatedWaitingTime()` semua kendaraan aktif |
| Avg Queue | Total antrean 4 lengan × `METERS_PER_QUEUED_VEHICLE` (7 m — **estimasi, bukan kalibrasi lapangan**) |
| LOS | `calculate_los()` yang sudah ada (ambang HCM 2000) — bukan logika baru |
| Throughput | Laju 60 detik terakhir |
| Fase Aktif | Parsing `rawState` TLS dari SUMO |

Semua data pendukung panel lama yang jadi tidak terpakai (`dbRecRaw`, `scenarioData`, `fetchRecommendation`, `fetchDigitalTwinScenarios`) ikut dibersihkan supaya tidak jadi kode mati.

---

### 2.5 Kartu "Durasi Sinyal Per Lengan" + 3 grafik tren

**Latar belakang:** user bertanya *"skenario ini yang beda cuma bagian lampu merahnya kan? gimana biar kerasa berubah?"* — pertanyaan yang tepat, karena memang:

| Skenario | Rumus durasi hijau |
|---|---|
| Traffic Realtime | Tidak dihitung ulang — ikut jadwal lampu asli hasil observasi CCTV |
| **Baseline** | Proporsional ke kepadatan tiap lengan (dasar untuk 2 kandidat lain) |
| **Aggressive** | Sama seperti Baseline, **kecuali lengan terpadat dapat +1 detik** |
| **Balanced** | Semua lengan ditarik ke arah minimum: `(hijau + minimum) / 2` |

Bedanya cuma **1–3 detik per lengan** — mustahil dibedakan hanya dengan menonton video. Karena itu ditambah:

**a) Kartu "Durasi Sinyal Per Lengan"** — detik Hijau/Kuning/Merah per lengan + total siklus. Ganti skenario → angka di kartu ini langsung berubah.

> 🐛 **Bug ketemu saat mengerjakan ini:** `apply_scenario_logic()` (jalur skenario sandbox) cuma menyuntik TraCI tapi **tidak pernah mencatat** `active_cycle_plan` — beda dari `apply_cycle_plan()` yang dipakai jalur dashboard. Akibatnya kartu ini akan kosong/basi untuk Baseline/Aggressive/Balanced. Sudah diperbaiki di `simulation_service.py`.

**b) 3 grafik tren** (Delay / Queue / Throughput) memakai `recharts` — library yang **sudah** dipakai `ForecastChart.tsx`, tidak menambah dependency baru.

Keputusan desainnya:
- **3 grafik terpisah, bukan 1 grafik gabungan.** Menggabungkan 3 satuan berbeda (detik, meter, kendaraan/menit) di satu grafik butuh 2 sumbu-Y, dan itu bikin salah baca.
- **Grafik direset tiap skenario baru diterapkan** — jadi yang tampil selalu "sejak skenario ini mulai", bukan riwayat campur-aduk beberapa skenario.
- Titik data di-dedup kalau waktu simulasi belum maju (polling 500 ms vs step SUMO 1 detik), supaya jendela 120 titik tidak habis kepakai duplikat.
- Warna diambil dari palet yang sudah lolos uji keterbacaan buta warna & kontras untuk mode gelap — biru/oranye/aqua.

---

### 2.6 Tata letak

| Perubahan | Sebelum | Sesudah |
|---|---|---|
| Panel "Simulation Controls" | Bawah-kiri, sejajar panel rekomendasi | Kolom kanan, di bawah panel "Phase" |
| Grid kartu statistik | 4 kolom, 1 slot kosong menganga | 3 kolom, pas |
| Rasio canvas SUMO | Tinggi tetap `460px` (gepeng di layar lebar) | `aspect-[16/11]`, sama dengan dashboard |

---

## 3. Bug yang ditemukan & diperbaiki

Lima bug ditemukan sambil mengerjakan hal lain. Semuanya **dibuktikan dengan pengukuran**, bukan dugaan.

### 3.1 🔴 `Gagal membangun TrafficState dari database: Server disconnected`

**Gejala:** klik "Start Simulation" kadang gagal dengan pesan ini.

**Yang SALAH dari dugaan awal saya:** saya sempat 2 kali menduga ini masalah koneksi basi/jaringan dan menambahkan retry — ternyata bukan itu akar masalahnya.

**Akar masalah sebenarnya:** `postgrest-py` (dipakai `supabase-py`) **hardcode `http2=True`** saat membuat sesi HTTP-nya (`postgrest/_sync/client.py`, tidak ada opsi resmi mematikannya). HTTP/2 memultipleks semua request lewat **satu koneksi TCP**, dan implementasi httpx+HTTP/2 tidak aman diakses banyak thread bersamaan. Backend ini punya banyak polling paralel (traffic state, signal status, dll, semuanya tiap ~0,5–1 detik) yang semuanya berbagi **satu** client Supabase (`get_supabase()` di-`@lru_cache`).

**Dibuktikan** dengan 4 thread × 4 request paralel ke Supabase yang sama:

| Konfigurasi | Hasil |
|---|---|
| `http2=True` (bawaan) | **14 dari 16 request GAGAL** `RemoteProtocolError: Server disconnected` |
| `http2=False` | **0 dari 16 gagal** — dan 3–5× lebih cepat (0,18–0,35 dtk vs 1+ dtk) |

**Perbaikan:** `_force_http1()` di `supabase_client.py` — sesi httpx-nya diganti dengan konfigurasi identik kecuali `http2=False`. **Ini memperbaiki seluruh backend**, bukan cuma simulasi.

Retry + jeda 0,5 detik yang saya tambahkan sebelumnya tetap dibiarkan sebagai pengaman untuk gangguan jaringan sungguhan.

---

### 3.2 🔴 Jendela SUMO tidak menutup sendiri

**Gejala:** backend mencetak `[SUMO LOOP] Background simulation loop berhenti` tapi jendela SUMO tetap hidup — harus dicari lewat Alt+Tab lalu ditutup manual.

**Akar masalah:** `sumo-gui` diluncurkan **tanpa flag `--quit-on-end`**. Tanpa flag itu, SUMO-GUI tidak otomatis keluar saat koneksi TraCI ditutup — dia cuma berhenti melangkah dan jendelanya menunggu diklik X. Diperparah karena jendelanya memang sengaja ditaruh **di luar layar** (`--window-pos -32000,-32000`, sebab yang dipakai dashboard itu screenshot-nya, bukan jendela aslinya).

**Perbaikan:** tambah `--quit-on-end`.

**Bukti:** PID proses anak dilacak langsung dari objek Python — setelah `close()`, proses **exit bersih (kode 0) dalam 1 detik**, tidak ada zombie.

---

### 3.3 🔴 Simulasi dashboard "ngulang" saat `/digitaltwin` dijalankan

**Gejala:** user melaporkan simulasi dashboard seperti restart/ngulang padahal saya sudah menjamin dashboard tidak akan diganggu.

**Akar masalah:** ada 2 cara memasukkan kendaraan ke SUMO, dan yang salah yang kepakai.

| Metode | Perilaku |
|---|---|
| `sync_demand()` | **Rekonsiliasi** — hapus kendaraan kelebihan, tambah yang kurang. Aman dipanggil berkali-kali |
| `inject_demand()` | **Selalu menambah** kendaraan baru di atas yang sudah ada, tanpa cek apa pun |

Dashboard selalu pakai `sync_demand()`. Tapi jalur `/digitaltwin` (termasuk "Traffic Realtime" yang nempel ke instance dashboard) lewat `inject_demand()` — jadi tiap kali dipanggil, **segerombolan kendaraan baru ditumpuk** ke simulasi yang sudah jalan. Itu yang terlihat seperti "ngulang".

**Perbaikan:** jalur itu sekarang pakai `sync_demand()` juga (dengan pemetaan field `volume` → `targetVehicleCount`).

---

### 3.4 🟡 Jumlah kendaraan tidak cocok dengan yang terlihat di video

**Gejala:** kartu menampilkan 20–25 kendaraan, tapi di video SUMO cuma kelihatan ~5.

**Akar masalah: video cuma menampilkan sekitar 1% luas network.** Bukan salah hitung.

| | Ukuran |
|---|---|
| Seluruh network SUMO | **633 m × 1020 m** |
| Crop kamera yang di-stream | **140 m × 79 m** |
| Ruas hulu lengan Selatan | **515 m** (jauh di luar crop) |
| Ruas hulu lengan Barat | **282 m** (jauh di luar crop) |

Jadi kendaraan yang masih melaju jauh di jalan pendekat tetap dihitung, tapi memang tidak mungkin terlihat.

**Perbaikan:** tambah hitungan `visibleVehicleCount` — posisi tiap kendaraan dicek terhadap batas crop yang **sama persis** dipakai untuk membuat gambar video. Kartu sekarang menampilkan **"Kendaraan Terlihat"** sebagai angka utama, dengan total jaringan sebagai keterangan. Berlaku di `/digitaltwin` **dan** dashboard.

---

### 3.5 🟡 Selisih "Deteksi" vs "Total jaringan" tidak bisa dijelaskan

**Gejala:** overlay dashboard menunjukkan `Deteksi: 24 · Total jaringan: 20` — kenapa beda 4?

**Dua penyebab yang sah (bukan bug):**
1. Sinkronisasi tidak kontinu — di antara 2 sinkronisasi, kendaraan yang sampai tujuan keluar dari network, jadi angkanya turun sampai sinkronisasi berikutnya mengisi ulang.
2. **Penyisipan kendaraan bisa gagal diam-diam** — `add_vehicle()` menelan `TraCIException` (`return False`) tanpa log apa pun. Kalau ruas masuk sudah padat (ingat: ruas `EDGE_MASUK` cuma **6,7–12,5 meter**), SUMO menolak menyisipkan kendaraan baru.

**Masalahnya:** penyebab nomor 2 **tidak tercatat di mana pun**, jadi tidak ada cara membedakan "wajar" vs "ada yang salah".

**Perbaikan:** `sync_demand()` sekarang mencatat berapa kendaraan gagal disisipkan (total + per lengan), diekspos lewat `/state`, dan **ditampilkan di UI hanya kalau > 0** (`· Gagal sisip: N` warna kuning) supaya tidak berisik saat normal.

Sekarang kalau selisih itu muncul lagi, penyebabnya bisa **dibuktikan**, bukan ditebak.

---

## 3b. Riwayat Keputusan — sesi lanjutan (1 September, sore)

Dipicu pertanyaan dosen pembimbing: *"apa output sistem ini, dan bagaimana menunjukkannya?"*

**Temuan yang memicu pekerjaan ini:** output sistem (rekomendasi durasi lampu) **tidak pernah tersimpan sama sekali** dari jalur produksi. Satu-satunya penulis tabel `recommendations` adalah skrip batch sekali jalan (`decision_engine/feed_to_supabase.py`) yang membaca CSV rule-based. Jalur hidup (`scenario_worker.py` → `liveScenarioCache` → dashboard) cuma menulis **1 baris cache yang ditimpa tiap 60 detik**.

> Artinya: sistem berjalan sejam pun, **nol jejak** yang tertinggal. Output terbaik (yang sudah diuji lewat SUMO) justru yang paling tidak terdokumentasi.

**Yang dikerjakan:**

| Bagian | Perubahan |
|---|---|
| `simulation/scenario_worker.py` | `write_history()` — tiap siklus menyimpan 4 baris `recommendations` + `simulations` per kandidat + `simulationMetrics`. Kegagalannya **tidak mematikan worker** (cache dashboard tetap prioritas) |
| `backend/app/services/history_service.py` | **Baru** — mengelompokkan baris jadi siklus, melampirkan kandidat + kondisi lalu lintas pemicu, paginasi eksplisit |
| `backend/app/api/routes/history.py` | **Diisi** (sebelumnya file 0 baris) + didaftarkan di `main.py` |
| `frontend/src/app/history/page.tsx` | Ditulis ulang — dari data contoh jadi data asli, tabel + detail bertingkat, paginasi 20/halaman |
| Test | +10 (`test_scenario_worker_history.py`, `test_history_service.py`) |

**Keputusan desain (hasil diskusi):**

- **Simpan tiap siklus**, bukan hanya saat berubah — data yang tidak ditulis tidak bisa dipulihkan, sedangkan cara menampilkan selalu bisa diubah.
- **Penanda "berubah" dihitung di frontend**, bukan disimpan — ambangnya (ganti kandidat ATAU ada lengan bergeser ≥2 detik) bisa diubah kapan saja tanpa menyentuh data.
- **LOS tidak disimpan** — murni turunan dari delay, dihitung ulang saat ditampilkan supaya tidak ada dua angka yang bisa saling bertentangan.
- **Fallback dicatat apa adanya** (`source` dari engine, mis. `rule-based+forecast`). Riwayat yang menyembunyikan fallback berbahaya: alur terlihat mulus padahal kotak 7/8/9 sempat terlewat.
- **Kondisi lalu lintas pemicu disambungkan lewat relasi** (`simulations.trafficStateId`), tidak disalin ulang.
- **Nama lengan tetap Inggris** di database (kontrak `data-contract.md`), diterjemahkan ke Indonesia **hanya di lapisan tampilan**. Mengubah kontrak ke Indonesia akan menyentuh CV, SUMO, PPO (harus latih ulang!), dan seluruh test — risikonya tidak sebanding.

**Bukti dijalankan sungguhan** (bukan hanya test): `scenario_worker.py --once --full-cycle` dijalankan, lalu diverifikasi lewat endpoint:

```
timestamp : 2026-09-01T04:03:39+00:00
source    : scenario-generator
fase      : west 20s · south 28s · east 17s · north 20s

KANDIDAT DIUJI:
  aggressive   delay=14.52s  antrean=56m  throughput=10  LOS=B
  balanced     delay=13.42s  antrean=70m  throughput=10  LOS=B
  baseline     delay=14.46s  antrean=56m  throughput=10  LOS=B  <-- TERPILIH

KONDISI PEMICU:
  north volume=0 antrean=0 · south volume=0 antrean=5 · west volume=0 antrean=2
```

**Visualisasi + penanda kejujuran (ditambahkan setelah data pertama masuk):**

Halaman Riwayat diberi **dua grafik bertumpuk dengan sumbu waktu sejajar** — antrean per lengan (masukan) di atas, durasi hijau per lengan (keluaran) di bawah. Ditumpuk, bukan digabung, karena satuannya beda (kendaraan vs detik) dan menggabungkannya butuh dua sumbu-Y yang gampang salah dibaca. Warna 4 lengan divalidasi lolos uji buta warna & kontras mode gelap.

> ⚠️ **Temuan saat grafik pertama kali diisi: garisnya datar sempurna.** Ditelusuri ke database — **16 siklus berturut-turut memakai `trafficStateId` yang SAMA (13784)**, yaitu window terakhir rekaman 15 Agustus. Sebabnya `loadTrafficState()` selalu mengambil kondisi *terbaru*, dan karena CV tidak berjalan, "terbaru" itu tidak pernah berganti.
>
> **Ini bukan bug** — masukan sama + sistem deterministik = keluaran sama (diverifikasi: ketiga kandidat menghasilkan delay identik sampai 2 desimal di 11 siklus berturut-turut, yang justru membuktikan hasilnya reproducible).
>
> **Tapi tampilannya berbahaya:** 16 baris identik terlihat seperti 16 keputusan berbeda. Kalau diklaim *"sistem menghasilkan 60 keputusan"* lalu penguji bertanya *"dari berapa kondisi berbeda?"* dan jawabannya **satu**, klaimnya runtuh.
>
> **Diperbaiki dengan menampilkan identitas masukan**, bukan menyembunyikannya:
> - Kolom baru **"Kondisi Dievaluasi"** — `baru · #13784` (hijau) vs `sama · #13784` (kuning)
> - Kartu ringkasan **"Kondisi Unik"** — mis. *"1 dari 16 siklus"*, dengan peringatan otomatis saat semua siklus mengevaluasi kondisi yang sama
>
> Supaya grafiknya benar-benar bercerita, CV harus berjalan memasok TrafficState baru (tiap 5 detik lewat `process_uploaded_video.py`). Tanpa itu worker hanya menghitung ulang kondisi beku yang sama.

**Catatan untuk sidang — pertanyaan yang mungkin muncul:** `balanced` punya delay terendah (13,42s) tapi yang menang `baseline` (14,46s). Ini benar, bukan salah pilih: pemilihan menimbang delay **dan** antrean 50:50, dan antrean `balanced` jauh lebih panjang (70m vs 56m) sehingga kalah di skor gabungan.

> ⚠️ **Satu langkah belum selesai — penghapusan data lama.** 2.153 baris lama (`rule_based_engine`) sudah **di-backup** ke `docs/arsip/recommendations-backup-2026-09-01.json`, tapi perintah `DELETE`-nya **diblokir sistem keamanan** dan harus dijalankan manual. Lihat bagian 4.

---

## 3c. Mode Replay + Panel Dampak Before/After

Dipicu dua hal: (1) grafik "Apakah Sistem Merespons" datar karena CV tidak berjalan, worker terus mengevaluasi kondisi yang sama; (2) dosen ingin tampilan yang menunjukkan **dampak** program, bukan cuma angka rekomendasi.

**Mode Replay** (`simulation/scenario_worker.py --replay`): worker memutar maju melalui 538 kondisi lalu lintas yang sudah terekam (49 menit, 15 Agustus), bukan selalu mengambil kondisi terbaru. Kelas `ReplaySource` — posisi maju `--replay-step` jendela per siklus (default 12 ≈ 1 menit rekaman), melingkar (modulo) di akhir daftar, **posisi tidak disimpan ke disk** (disengaja — tiap restart worker mengulang urutan yang sama persis, cocok untuk latihan presentasi berkali-kali dengan hasil reproducible). Ditandai jujur: `source` dapat akhiran `+replay` (mis. `scenario-generator+replay`), tidak menyamar sebagai data realtime.

**Diverifikasi lewat data asli** (bukan cuma test): 5 siklus replay menghasilkan 5 `trafficStateId` berbeda dengan volume per lengan yang benar-benar bervariasi (mis. Timur 0→8→1→1→5 kendaraan) — bukti grafik "Apakah Sistem Merespons" akhirnya punya cerita untuk ditampilkan.

**Panel Dampak Before/After** (`history_service.py::_compute_before_after()`): membandingkan kandidat `baseline` (before) vs pemenang (after) — **keduanya benar-benar disimulasikan di SUMO**, bukan diperkirakan. Field baru `beforeAfter` per siklus, tampil di halaman Riwayat sebagai tabel Metrik/Before/After/Change dengan ikon naik-turun berwarna.

> Diverifikasi lewat endpoint sungguhan (bukan hanya unit test): satu siklus replay menghasilkan **waktu tunggu −19,8%, antrean −44,4%, throughput +47,4%** — semua dihitung dari simulasi SUMO nyata.

**Keputusan desain:** saat `baseline` sendiri yang menang (`changed: false`), panel menampilkan keterangan eksplisit *"sistem menyimpulkan pengaturan baseline sudah paling baik — bukan kegagalan sistem"*, bukan ditampilkan seolah selalu ada perbaikan. Ini sengaja jujur mengantisipasi kasus 0% dampak, yang memang terjadi di data awal sebelum replay diaktifkan.

**Yang SENGAJA tidak ditiru dari mockup desain awal** (dicek dulu sebelum diimplementasikan, bukan diasumsikan aman):
- ~~"Model: PPO v1.0 + LSTM v1.2"~~ — PPO **tidak aktif** di sistem ini (default rule-based); mencantumkannya adalah klaim yang tidak benar
- ~~"Overall Performance +12.4%"~~ — angka komposit tanpa rumus jelas, tidak bisa dipertanggungjawabkan kalau ditanya
- ~~Multi-simpang (Simpang 1/2)~~ — sistem cuma punya satu simpang (Pingit)

Test: +5 (`test_scenario_worker_replay.py`) +3 assertion baru di `test_history_service.py`. **130 test lolos** (naik dari 122).

---

## 4. Yang BELUM dikerjakan

Supaya tidak ada yang mengira ini sudah beres semua.

### 4.1 Belum diverifikasi manual di browser

**Ini yang paling penting.** Semua perubahan lolos `pytest` dan `npm run build`, tapi **belum ada yang membuka browser dan memastikan angkanya bergerak benar dengan SUMO sungguhan jalan.** Yang perlu dicek:
- Kartu Durasi Sinyal berubah saat ganti skenario.
- 3 grafik terisi dan direset saat ganti skenario.
- Buka dashboard + `/digitaltwin` bersamaan → SUMO **tidak** kebuka dobel saat "Traffic Realtime".
- Pause di sandbox `/digitaltwin` → dashboard tidak terpengaruh.

### 4.2 Regresi dari revert 31 Agustus yang masih tersisa

Audit ([`audit_final_31agustus.md`](audit_final_31agustus.md)) menemukan 2 commit revert dini hari 31 Agustus yang menghapus beberapa perbaikan. **Yang belum dipulihkan** (file-filenya tidak saya sentuh sesi ini — cek `git status`):

| Yang hilang | Dampak |
|---|---|
| `CameraFeedPanel.tsx` — waktu per-kamera | Geser scrubber 1 CCTV menarik semua kamera lain |
| `RecommendationPanel.tsx` — state "Rekomendasi belum tersedia" | Bisa nyangkut loading tanpa batas **(di dashboard; di `/digitaltwin` panelnya sudah diganti)** |
| `SharedSignalPanels.tsx` — grace period 2,5 detik | — |
| `traffic.py` — kasus `simpang4-pingit` tanpa histori | Bisa memicu 404 yang merembet ke fallback forecast |
| `DigitalTwinPanel.tsx` — pakai `/stream` (10 fps) | Masih polling `/frame` 500 ms → video patah-patah |

> **Catatan status berubah:** audit sempat menandai *auto-start SUMO di dashboard* sebagai regresi. Setelah isolasi context di sesi ini, perilaku itu justru **yang diinginkan** (dashboard memang harus jalan sendiri selama video berjalan). Jadi itu tidak lagi dihitung regresi.

### 4.2b Penghapusan 2.153 baris riwayat lama — perlu dijalankan manual

Sudah disepakati untuk dihapus (mulai bersih dari nol), backup sudah dibuat, tapi perintahnya **diblokir sistem keamanan** karena `DELETE` ke database produksi. Perlu dijalankan sendiri lewat SQL Editor Supabase:

```sql
-- Backup ada di docs/arsip/recommendations-backup-2026-09-01.json (2.153 baris)
delete from recommendations
where source in ('rule_based_engine', 'ruleBased');
```

Sudah diverifikasi aman sebelum diblokir:

| Cek | Hasil |
|---|---|
| Baris terhapus | 2.153 (semuanya data batch 15 Agustus) |
| Baris tersimpan | 4 (hasil `scenario-generator` yang baru) |
| Simulasi yang bergantung pada baris terhapus | **0** |
| Bisa dipulihkan? | Ya — dari backup JSON, atau jalankan ulang `feed_to_supabase.py` |

### 4.3 Lain-lain

- **Belum di-commit.** Semua masih di working tree.
- Halaman `/history` masih placeholder (backend route-nya file kosong, tidak terdaftar) — di luar scope, sesuai keputusan tim.
- `add_vehicle()` masih menelan exception diam-diam; sekarang **dihitung** tapi belum di-log detail alasannya.
- Belum ada unit test khusus untuk penghitungan gagal-sisip di dalam `sync_demand()` (butuh mock TraCI; belum ada pola mocking TraCI di repo ini).

---

## 5. Cara memverifikasi sendiri

```powershell
# 1. Test backend + simulation (harus 112 passed)
.\.venv\Scripts\Activate.ps1
$env:SUMO_HOME = "$PWD\.venv\Lib\site-packages\sumo"
.venv\Scripts\python.exe -m pytest backend/tests simulation/tests -q

# 2. Build frontend (harus 13/13 route, 0 error)
cd frontend
npm run build
```

Untuk uji manual, ikuti [`sop-demo-end-to-end.md`](sop-demo-end-to-end.md) seperti biasa — **restart backend dulu**, karena banyak perubahan ada di sisi Python dan tidak ikut ter-reload sendiri kecuali dijalankan dengan `--reload`.

---

## 6. Catatan jujur soal proses

Beberapa hal di sesi ini saya **salah duga dulu sebelum benar**, dan itu terekam di dokumen ini dengan sengaja supaya tidak diulang:

1. **`Server disconnected`** — saya 2 kali menduga masalah koneksi basi dan menambal dengan retry, sebelum akhirnya mereproduksi dengan 4 thread dan menemukan HTTP/2 sebagai akar masalahnya. Pelajaran: reproduksi terkontrol > menebak dari pesan error.
2. **Isolasi context** — desain pertama saya membuat "Traffic Realtime" jadi instance terpisah, padahal seharusnya nempel ke dashboard. Ketahuan dari masukan user, bukan dari test.
3. **Panel rekomendasi** — user merasa "ada yang salah" sebelum saya bisa menunjukkan apa. Setelah ditelusuri ke kode, kecurigaannya tepat: panel itu memang membaca cache produksi, bukan simulasi yang ditonton.

Pola yang berulang: **keluhan user yang terasa samar ("kok kayak aneh ya") hampir selalu menunjuk bug nyata** — cuma butuh ditelusuri ke kode dulu sebelum bisa dijelaskan.

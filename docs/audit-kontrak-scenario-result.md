# Audit Kontrak ScenarioResult

Tanggal audit: 27 Agustus 2026

## Kesimpulan

Rantai runtime `ScenarioEngine -> scenario_worker -> liveScenarioCache ->
/recommendation` sudah kompatibel dan teruji. Namun, bentuk referensi
`ScenarioResult` di `docs/data-contract.md` bagian 4 belum identik dengan
payload runtime. Perbedaannya adalah perbedaan penamaan dan perluasan kontrak,
bukan data yang hilang pada runtime.

Dokumen ini mencatat adapter yang berlaku. `data-contract.md` tidak diubah agar
kontrak resmi lama tetap dapat diaudit oleh pemiliknya.

## Pemetaan field

| Kontrak referensi | Hasil simulasi/worker | Cache Supabase | Respons `/recommendation` | Status |
|---|---|---|---|---|
| `scenario_id` | `candidateId` | `candidateId` | `candidateId` | Sama makna, beda nama |
| `phases[].phase_name` | `cyclePlan.phases[].approach` | di dalam `recommendation.cyclePlan` | `cyclePlan.phases[].approach` | Ada pada mode full-cycle |
| `phases[].green_duration_s` | `cyclePlan.phases[].greenSeconds` | di dalam `recommendation.cyclePlan` | `cyclePlan.phases[].greenSeconds` | Ada pada mode full-cycle |
| `cycle_length_s` | `cyclePlan.cycleLengthSeconds` | di dalam `recommendation.cyclePlan` | `cyclePlan.cycleLengthSeconds` | Ada pada mode full-cycle |
| `avg_delay_s` | `avgDelaySeconds` | `avgDelaySeconds` | `avgDelaySeconds` | Lengkap |
| `avg_queue_length_m` | `avgQueueLengthM` | `avgQueueLengthM` | `avgQueueLengthM` | Lengkap; nilai estimasi |
| `throughput_veh` | `throughputVeh` | `throughputVeh` | belum diekspos pada schema respons | Ada di cache, tidak dibutuhkan frontend |
| belum tercantum | `los` | `los` | `los` | Perluasan runtime |
| belum tercantum | `queueLengthVeh` | tidak disimpan | melalui `metrics.queueLength` dari state live | Metrik pendukung |

## Kontrak cache minimum yang sekarang divalidasi backend

Baris cache hanya diterima jika:

- `intersectionId` cocok dengan request;
- `updatedAt` valid dan berumur maksimal 120 detik;
- `recommendation` mempunyai phase, green time, current green, dan current phase;
- delay, antrean meter, dan throughput berupa angka non-negatif;
- LOS berada pada A-F;
- `candidateId` tidak kosong; dan
- bila `cyclePlan` ada, ia mempunyai empat phase yang valid.

Cache kosong, basi, rusak, atau gagal dibaca diperlakukan sebagai cache miss dan
endpoint kembali ke Rule-Based Engine. Validasi ini berada di
`backend/app/services/live_scenario_cache_service.py`.

## Catatan satuan dan interpretasi

- `avgDelaySeconds` berasal dari rata-rata accumulated waiting time kendaraan
  aktif selama simulasi pendek. Ini proxy delay simulasi, bukan pengukuran
  control delay lapangan yang sudah dikalibrasi.
- `avgQueueLengthM` dihitung dari `queueLengthVeh x 7 meter`. Angka 7 meter
  adalah asumsi panjang efektif kendaraan campuran beserta headway, bukan hasil
  kalibrasi lapangan Simpang Pingit; karena itu harus disebut estimasi panjang
  antrean.
- Pemilihan kandidat memberi bobot 50% pada delay dan 50% pada antrean setelah
  keduanya dinormalisasi terhadap nilai terburuk dalam batch. Bobot setara
  dipakai sebagai kompromi netral karena belum ada bukti lokal untuk
  memprioritaskan salah satunya; ini heuristik SmartTwin, bukan formula HCM.
- `throughputVeh` adalah kendaraan yang tiba selama horizon simulasi.
- LOS dipetakan dari delay menggunakan ambang HCM yang dipakai proyek.

## Rekomendasi kontrak berikutnya

Jika pemilik `data-contract.md` melakukan revisi resmi, gunakan field camelCase
runtime sebagai kontrak API dan pertahankan alias snake_case hanya untuk
dokumentasi analitis. Jangan mengubah payload frontend yang sudah stabil hanya
untuk menyamakan gaya nama.

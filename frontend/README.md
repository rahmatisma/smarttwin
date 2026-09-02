# SmartTwin Frontend

Dashboard Next.js untuk monitoring CCTV, kondisi lalu lintas, forecast,
rekomendasi lampu, dan visualisasi SUMO Digital Twin.

## Environment

Buat `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

`SUPABASE_SERVICE_ROLE_KEY` hanya digunakan Route Handler server-side dan tidak
boleh diberi prefix `NEXT_PUBLIC_`.

## Menjalankan

```powershell
npm install
npm run dev
```

Buka `http://localhost:3000`. Backend default berada di
`http://127.0.0.1:8000`.

## Pemeriksaan kualitas

```powershell
npm run lint
npm test
npm run build
```

Test menggunakan runner bawaan Node.js sehingga tidak menambah framework test
baru. Production build tidak mengambil Google Fonts dan dapat dilakukan tanpa
akses ke `fonts.googleapis.com`.

## Struktur penting

| Lokasi | Fungsi |
|---|---|
| `src/app/` | Route dan halaman App Router |
| `src/components/` | Komponen dashboard |
| `src/context/` | State skenario lintas halaman |
| `src/lib/` | Integrasi API/Supabase dan helper kontrak |
| `src/types/` | Kontrak TypeScript |
| `tests/` | Unit test helper murni |

Perubahan field traffic atau recommendation harus diperiksa juga terhadap
schema backend dan [`../docs/data-contract.md`](../docs/data-contract.md).

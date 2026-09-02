# Deployment Docker SmartTwin

Konfigurasi ini menjalankan backend FastAPI dan frontend Next.js. SUMO headless
tersedia melalui dependency backend. CV GPU tetap dijalankan terpisah karena
passthrough CUDA pada Windows/WSL membutuhkan konfigurasi host khusus.

## Persiapan

1. Isi `.env` di root untuk backend.
2. Sediakan variabel berikut pada shell atau file `docker/.env` untuk build
   frontend:

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

3. Pastikan user Supabase yang mengontrol simulasi mempunyai
   `app_metadata.role=operator` atau `admin`. Compose mengaktifkan
   `AUTH_REQUIRED=true` pada backend.

## Build dan run

```powershell
Set-Location docker
docker compose up --build
```

- Dashboard: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Detailed health: `http://localhost:8000/api/v1/health/details`

## Batasan

- Container frontend menerima `NEXT_PUBLIC_*` ketika build; rebuild jika URL
  publik berubah.
- SUMO GUI tidak diekspos dari container. Gunakan `gui=false` untuk deployment.
- Worker skenario dan CV GPU belum menjadi service compose agar tidak otomatis
  menjalankan pekerjaan berat tanpa sumber data yang disiapkan operator.
- Secret tidak boleh ditulis di `compose.yaml` atau di-commit.

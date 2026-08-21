// src/lib/supabaseAdmin.ts
//
// Supabase client dengan service_role key.
//
// SERVER-ONLY. Bypass RLS sepenuhnya, jadi hanya boleh
// diimpor dari Route Handler (src/app/api/**/route.ts),
// TIDAK PERNAH dari Client Component ("use client").
//
// import "server-only" membuat build gagal kalau file ini
// ketarik ke bundle browser.

import "server-only";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !serviceRoleKey) {
  throw new Error(
    "NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY belum diset di .env.local"
  );
}

export const supabaseAdmin = createClient(supabaseUrl, serviceRoleKey, {
  auth: {
    autoRefreshToken: false,
    persistSession: false,
  },
});

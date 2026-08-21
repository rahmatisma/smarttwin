// src/lib/supabaseClient.ts
//
// Supabase client untuk browser (Client Components).
//
// Menggunakan anon/publishable key (aman di browser).
// Dibuat lewat @supabase/ssr supaya session auth (cookie)
// konsisten dengan middleware.ts dan bisa dibaca ulang saat
// navigasi / refresh.
//
// Akses data dibatasi lewat RLS: SELECT-only untuk role anon,
// lihat migration "anon_read_policies_for_frontend" di Supabase.

import { createBrowserClient } from "@supabase/ssr";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY belum diset di .env.local"
  );
}

export const supabase = createBrowserClient(supabaseUrl, supabaseAnonKey);

-- Jalankan sekali di Supabase SQL Editor sebelum scenario_worker.py --once.
-- Worker melakukan upsert satu baris per simpang; backend hanya membaca.
create table if not exists public."liveScenarioCache" (
  "intersectionId" text primary key,
  "updatedAt" timestamptz not null,
  recommendation jsonb not null,
  "avgDelaySeconds" double precision not null check ("avgDelaySeconds" >= 0),
  "avgQueueLengthM" double precision not null check ("avgQueueLengthM" >= 0),
  los text not null,
  "candidateId" text not null,
  "throughputVeh" integer not null check ("throughputVeh" >= 0),
  candidates jsonb not null default '[]'::jsonb
);

-- Aman dijalankan ulang pada tabel yang sudah dibuat sebelum kolom candidates.
alter table public."liveScenarioCache"
  add column if not exists candidates jsonb not null default '[]'::jsonb;

comment on table public."liveScenarioCache" is
  'Cache terbaru dari simulation/scenario_worker.py untuk endpoint live. Baris basi diabaikan backend dan fallback ke rule-based.';

-- Memastikan PostgREST/Supabase segera mengenali tabel baru.
notify pgrst, 'reload schema';

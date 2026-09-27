-- Pattern Map, Supabase schema
--
-- The rule this schema enforces: message bodies never leave the device. What
-- lands here is the shape of the record, not the record. Every row is scoped to
-- auth.uid() and readable by nobody else.
--
-- If you ever add a body column, the line in the import consent and the Vault
-- copy about HerProof not being able to read it both stop being true. Don't.

create extension if not exists "pgcrypto";

create table if not exists imports (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  source        text not null default 'whatsapp',
  file_sha256   text not null,
  file_name     text,
  other_name    text not null,
  tz            text not null,
  date_order    text,
  ai_consent    boolean not null default false,
  message_count int  not null default 0,
  first_ts      timestamptz,
  last_ts       timestamptz,
  status        text not null default 'ready',
  created_at    timestamptz not null default now()
);

-- No body column. On purpose. line_no is the pointer back into the file on the
-- user's own device, which is the only place the text exists.
create table if not exists tags (
  id          uuid primary key default gen_random_uuid(),
  import_id   uuid not null references imports(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  line_no     int  not null,
  ts          timestamptz,
  category    text not null,
  reasons     text[] not null default '{}',
  confidence  real,
  model       text,
  status      text not null default 'shown',
  created_at  timestamptz not null default now()
);

create table if not exists flags (
  id         uuid primary key default gen_random_uuid(),
  import_id  uuid not null references imports(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  line_no    int,
  type       text not null,
  source     text not null check (source in ('ai','keyword','computed')),
  created_at timestamptz not null default now()
);

create table if not exists exports (
  id         uuid primary key default gen_random_uuid(),
  import_id  uuid not null references imports(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  audience   text not null check (audience in ('lawyer','police','me')),
  options    jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists tags_import_idx  on tags(import_id);
create index if not exists flags_import_idx on flags(import_id);

alter table imports enable row level security;
alter table tags    enable row level security;
alter table flags   enable row level security;
alter table exports enable row level security;

do $$
declare t text;
begin
  foreach t in array array['imports','tags','flags','exports'] loop
    execute format('drop policy if exists own_rows on %I', t);
    execute format(
      'create policy own_rows on %I for all using (user_id = auth.uid()) with check (user_id = auth.uid())', t);
  end loop;
end $$;

-- Delete import removes everything derived from it, by cascade. One call:
--   delete from imports where id = :import_id;

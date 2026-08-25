-- TorchAir issue board cloud data model.
-- Run this once in the Supabase SQL editor.

create table if not exists public.duty_schedules (
  duty_date date primary key,
  person_name text not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.duty_members (
  person_name text primary key,
  gitcode_account text not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.issues (
  issue_key text primary key,
  issue_number text not null,
  title text not null,
  state text not null,
  owner text,
  first_label text not null default '未标记',
  created_at timestamptz,
  issue_url text,
  raw_payload jsonb not null default '{}'::jsonb,
  synced_at timestamptz not null default now()
);

create table if not exists public.dashboard_snapshots (
  id smallint primary key default 1 check (id = 1),
  payload jsonb not null,
  generated_at timestamptz not null default now()
);

create table if not exists public.issue_sync (
  issue_key text primary key,
  first_seen_at timestamptz not null,
  assignment_status text not null default 'pending',
  assigned_at timestamptz,
  assigned_to text
);

-- Public refresh requests are rate-limited by the Supabase Edge Function.
create table if not exists public.sync_control (
  id smallint primary key default 1 check (id = 1),
  last_requested_at timestamptz
);
insert into public.sync_control (id) values (1)
on conflict (id) do nothing;

create index if not exists issues_created_at_idx on public.issues (created_at);
create index if not exists issues_state_idx on public.issues (state);

-- Public dashboard reads are safe because the snapshot contains display data only.
alter table public.dashboard_snapshots enable row level security;
create policy "dashboard snapshots are publicly readable"
  on public.dashboard_snapshots for select
  using (true);

-- The management page will use authenticated Supabase users before these policies
-- are enabled. Do not expose write policies to anonymous visitors.
alter table public.duty_schedules enable row level security;
alter table public.duty_members enable row level security;
alter table public.issues enable row level security;
alter table public.issue_sync enable row level security;
alter table public.sync_control enable row level security;

create policy "duty schedules are publicly readable"
  on public.duty_schedules for select
  using (true);
create policy "duty members are publicly readable"
  on public.duty_members for select
  using (true);
create policy "issues are publicly readable"
  on public.issues for select
  using (true);

-- Only signed-in management users may change schedules and member mappings.
drop policy if exists "authenticated users can insert duty schedules" on public.duty_schedules;
drop policy if exists "authenticated users can update duty schedules" on public.duty_schedules;
drop policy if exists "authenticated users can delete duty schedules" on public.duty_schedules;
create policy "authenticated users can insert duty schedules"
  on public.duty_schedules for insert to authenticated with check (true);
create policy "authenticated users can update duty schedules"
  on public.duty_schedules for update to authenticated using (true) with check (true);
create policy "authenticated users can delete duty schedules"
  on public.duty_schedules for delete to authenticated using (true);

drop policy if exists "authenticated users can insert duty members" on public.duty_members;
drop policy if exists "authenticated users can update duty members" on public.duty_members;
drop policy if exists "authenticated users can delete duty members" on public.duty_members;
create policy "authenticated users can insert duty members"
  on public.duty_members for insert to authenticated with check (true);
create policy "authenticated users can update duty members"
  on public.duty_members for update to authenticated using (true) with check (true);
create policy "authenticated users can delete duty members"
  on public.duty_members for delete to authenticated using (true);

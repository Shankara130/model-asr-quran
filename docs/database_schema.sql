-- Sobat Ngaji PostgreSQL schema.
-- Target: FastAPI backend used by Flutter app contract under /v1.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null unique,
  password_hash text not null,
  avatar_url text,
  learning_level text not null default 'beginner',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint users_email_not_blank check (length(trim(email)) > 0),
  constraint users_name_not_blank check (length(trim(name)) > 0),
  constraint users_learning_level_valid check (
    learning_level in ('beginner', 'intermediate', 'advanced')
  )
);

drop trigger if exists users_set_updated_at on users;
create trigger users_set_updated_at
before update on users
for each row execute function set_updated_at();

create table if not exists auth_refresh_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null unique,
  user_agent text,
  ip_address inet,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  constraint auth_refresh_tokens_expiry_valid check (expires_at > created_at)
);

create index if not exists auth_refresh_tokens_user_id_idx
  on auth_refresh_tokens(user_id);

create index if not exists auth_refresh_tokens_active_idx
  on auth_refresh_tokens(user_id, expires_at)
  where revoked_at is null;

create table if not exists user_preferences (
  user_id uuid primary key references users(id) on delete cascade,
  practice_level text not null default 'beginner',
  practice_mode text not null default 'phrases',
  audio_feedback_enabled boolean not null default true,
  daily_report_frequency text not null default 'weekly_sunday',
  reminder_enabled boolean not null default false,
  reminder_time time,
  updated_at timestamptz not null default now(),
  constraint user_preferences_practice_level_valid check (
    practice_level in ('beginner', 'intermediate', 'advanced')
  ),
  constraint user_preferences_practice_mode_valid check (
    practice_mode in ('phrases', 'ayah', 'surah')
  )
);

drop trigger if exists user_preferences_set_updated_at on user_preferences;
create trigger user_preferences_set_updated_at
before update on user_preferences
for each row execute function set_updated_at();

create table if not exists practice_items (
  id text primary key,
  surah_name text not null,
  surah_number int not null,
  ayah_label text not null,
  ayah_number_start int not null,
  ayah_number_end int not null,
  arabic_name text not null,
  arabic_text text not null,
  translation text not null,
  latin_hint text,
  focus text not null,
  level text not null default 'beginner',
  estimated_minutes int not null default 5,
  reference_audio_url text,
  reference_audio_key text,
  reciter text,
  is_daily boolean not null default false,
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint practice_items_id_not_blank check (length(trim(id)) > 0),
  constraint practice_items_surah_number_valid check (surah_number between 1 and 114),
  constraint practice_items_ayah_range_valid check (
    ayah_number_start > 0 and ayah_number_end >= ayah_number_start
  ),
  constraint practice_items_level_valid check (
    level in ('beginner', 'intermediate', 'advanced')
  ),
  constraint practice_items_estimated_minutes_valid check (estimated_minutes > 0)
);

drop trigger if exists practice_items_set_updated_at on practice_items;
create trigger practice_items_set_updated_at
before update on practice_items
for each row execute function set_updated_at();

create index if not exists practice_items_level_idx
  on practice_items(level);

create index if not exists practice_items_daily_idx
  on practice_items(is_daily)
  where is_daily = true;

create index if not exists practice_items_tags_idx
  on practice_items using gin(tags);

create table if not exists practice_item_segments (
  id uuid primary key default gen_random_uuid(),
  practice_item_id text not null references practice_items(id) on delete cascade,
  segment_index int not null,
  text text not null,
  start_char int not null,
  end_char int not null,
  created_at timestamptz not null default now(),
  constraint practice_item_segments_index_valid check (segment_index >= 0),
  constraint practice_item_segments_range_valid check (
    start_char >= 0 and end_char > start_char
  ),
  unique (practice_item_id, segment_index)
);

create table if not exists practice_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  practice_item_id text not null references practice_items(id),
  status text not null default 'started',
  client_session_id text,
  device_platform text,
  device_model text,
  app_version text,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  cancelled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint practice_sessions_status_valid check (
    status in (
      'started',
      'recording',
      'uploading',
      'processing',
      'completed',
      'failed',
      'cancelled'
    )
  ),
  constraint practice_sessions_completed_after_start check (
    completed_at is null or completed_at >= started_at
  ),
  unique (user_id, client_session_id)
);

drop trigger if exists practice_sessions_set_updated_at on practice_sessions;
create trigger practice_sessions_set_updated_at
before update on practice_sessions
for each row execute function set_updated_at();

create index if not exists practice_sessions_user_created_idx
  on practice_sessions(user_id, created_at desc);

create index if not exists practice_sessions_user_status_idx
  on practice_sessions(user_id, status);

create index if not exists practice_sessions_practice_item_idx
  on practice_sessions(practice_item_id);

create table if not exists practice_session_realtime_tokens (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references practice_sessions(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  constraint practice_session_realtime_tokens_expiry_valid check (expires_at > created_at)
);

create index if not exists practice_session_realtime_tokens_session_idx
  on practice_session_realtime_tokens(session_id);

create table if not exists audio_uploads (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references practice_sessions(id) on delete cascade,
  upload_id text unique,
  audio_url text,
  storage_key text,
  mime_type text not null,
  codec text,
  duration_ms int,
  sample_rate int,
  channels int,
  size_bytes bigint,
  status text not null default 'initialized',
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint audio_uploads_mime_type_valid check (
    mime_type in ('audio/webm', 'audio/mp4', 'audio/m4a', 'audio/wav')
  ),
  constraint audio_uploads_status_valid check (
    status in ('initialized', 'uploading', 'uploaded', 'failed', 'aborted')
  ),
  constraint audio_uploads_duration_valid check (
    duration_ms is null or (duration_ms > 0 and duration_ms <= 120000)
  ),
  constraint audio_uploads_sample_rate_valid check (
    sample_rate is null or sample_rate > 0
  ),
  constraint audio_uploads_channels_valid check (
    channels is null or channels in (1, 2)
  ),
  constraint audio_uploads_size_valid check (
    size_bytes is null or size_bytes > 0
  )
);

create index if not exists audio_uploads_session_created_idx
  on audio_uploads(session_id, created_at desc);

create index if not exists audio_uploads_status_idx
  on audio_uploads(status);

create table if not exists audio_chunks (
  id uuid primary key default gen_random_uuid(),
  audio_upload_id uuid not null references audio_uploads(id) on delete cascade,
  chunk_index int not null,
  start_ms int not null,
  end_ms int not null,
  size_bytes int not null,
  checksum_sha256 text,
  storage_key text,
  received_at timestamptz not null default now(),
  constraint audio_chunks_index_valid check (chunk_index >= 0),
  constraint audio_chunks_time_range_valid check (
    start_ms >= 0 and end_ms > start_ms
  ),
  constraint audio_chunks_size_valid check (size_bytes > 0),
  unique (audio_upload_id, chunk_index)
);

create index if not exists audio_chunks_upload_idx
  on audio_chunks(audio_upload_id, chunk_index);

create table if not exists evaluation_results (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references practice_sessions(id) on delete cascade,
  practice_item_id text not null references practice_items(id),
  audio_upload_id uuid references audio_uploads(id) on delete set null,
  match_score int,
  confidence_level text,
  summary text,
  recommendation text,
  status text not null default 'queued',
  error_code text,
  model_name text,
  model_version text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint evaluation_results_status_valid check (
    status in ('queued', 'processing', 'completed', 'failed')
  ),
  constraint evaluation_results_match_score_valid check (
    match_score is null or match_score between 0 and 100
  ),
  constraint evaluation_results_confidence_valid check (
    confidence_level is null or confidence_level in ('low', 'medium', 'high')
  )
);

drop trigger if exists evaluation_results_set_updated_at on evaluation_results;
create trigger evaluation_results_set_updated_at
before update on evaluation_results
for each row execute function set_updated_at();

create index if not exists evaluation_results_session_created_idx
  on evaluation_results(session_id, created_at desc);

create index if not exists evaluation_results_status_idx
  on evaluation_results(status);

create table if not exists ayah_highlights (
  id uuid primary key default gen_random_uuid(),
  evaluation_result_id uuid not null references evaluation_results(id) on delete cascade,
  segment text not null,
  status text not null,
  note text not null,
  start_index int,
  end_index int,
  created_at timestamptz not null default now(),
  constraint ayah_highlights_status_valid check (
    status in ('read', 'current', 'needs_check', 'needs_retry')
  ),
  constraint ayah_highlights_range_valid check (
    start_index is null
    or end_index is null
    or (start_index >= 0 and end_index > start_index)
  )
);

create index if not exists ayah_highlights_result_idx
  on ayah_highlights(evaluation_result_id, start_index);

create table if not exists letter_insights (
  id uuid primary key default gen_random_uuid(),
  evaluation_result_id uuid not null references evaluation_results(id) on delete cascade,
  letter text not null,
  mastery_score int not null,
  mistake_count int not null default 0,
  created_at timestamptz not null default now(),
  constraint letter_insights_score_valid check (mastery_score between 0 and 100),
  constraint letter_insights_mistake_count_valid check (mistake_count >= 0),
  unique (evaluation_result_id, letter)
);

create index if not exists letter_insights_result_idx
  on letter_insights(evaluation_result_id);

create table if not exists letter_mastery (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  letter text not null,
  score int not null default 0,
  mistake_count int not null default 0,
  last_practiced_at timestamptz,
  updated_at timestamptz not null default now(),
  constraint letter_mastery_score_valid check (score between 0 and 100),
  constraint letter_mastery_mistake_count_valid check (mistake_count >= 0),
  unique (user_id, letter)
);

drop trigger if exists letter_mastery_set_updated_at on letter_mastery;
create trigger letter_mastery_set_updated_at
before update on letter_mastery
for each row execute function set_updated_at();

create index if not exists letter_mastery_user_score_idx
  on letter_mastery(user_id, score asc);

create table if not exists weekly_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  week_start date not null,
  week_end date not null,
  average_score int not null default 0,
  practice_count int not null default 0,
  growth_percent int not null default 0,
  focus_letter text,
  summary text not null default '',
  suggestion text not null default '',
  trend int[] not null default '{}',
  created_at timestamptz not null default now(),
  constraint weekly_reports_week_range_valid check (week_end >= week_start),
  constraint weekly_reports_average_score_valid check (average_score between 0 and 100),
  constraint weekly_reports_practice_count_valid check (practice_count >= 0),
  unique (user_id, week_start)
);

create index if not exists weekly_reports_user_week_idx
  on weekly_reports(user_id, week_start desc);

create table if not exists practice_session_events (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references practice_sessions(id) on delete cascade,
  event_id text not null,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (session_id, event_id)
);

create index if not exists practice_session_events_session_created_idx
  on practice_session_events(session_id, created_at);

create index if not exists practice_session_events_type_idx
  on practice_session_events(event_type);

create table if not exists request_logs (
  id uuid primary key default gen_random_uuid(),
  request_id text not null unique,
  user_id uuid references users(id) on delete set null,
  method text not null,
  path text not null,
  status_code int,
  error_code text,
  created_at timestamptz not null default now()
);

create index if not exists request_logs_user_created_idx
  on request_logs(user_id, created_at desc);

create index if not exists request_logs_path_created_idx
  on request_logs(path, created_at desc);

-- Application data is backend-only. Flutter authenticates through Supabase Auth,
-- then accesses these tables exclusively through FastAPI.
alter table public.users enable row level security;
revoke all on table public.users from anon, authenticated;
alter table public.auth_refresh_tokens enable row level security;
revoke all on table public.auth_refresh_tokens from anon, authenticated;
alter table public.user_preferences enable row level security;
revoke all on table public.user_preferences from anon, authenticated;
alter table public.practice_items enable row level security;
revoke all on table public.practice_items from anon, authenticated;
alter table public.practice_item_segments enable row level security;
revoke all on table public.practice_item_segments from anon, authenticated;
alter table public.practice_sessions enable row level security;
revoke all on table public.practice_sessions from anon, authenticated;
alter table public.practice_session_realtime_tokens enable row level security;
revoke all on table public.practice_session_realtime_tokens from anon, authenticated;
alter table public.audio_uploads enable row level security;
revoke all on table public.audio_uploads from anon, authenticated;
alter table public.audio_chunks enable row level security;
revoke all on table public.audio_chunks from anon, authenticated;
alter table public.evaluation_results enable row level security;
revoke all on table public.evaluation_results from anon, authenticated;
alter table public.ayah_highlights enable row level security;
revoke all on table public.ayah_highlights from anon, authenticated;
alter table public.letter_insights enable row level security;
revoke all on table public.letter_insights from anon, authenticated;
alter table public.letter_mastery enable row level security;
revoke all on table public.letter_mastery from anon, authenticated;
alter table public.weekly_reports enable row level security;
revoke all on table public.weekly_reports from anon, authenticated;
alter table public.practice_session_events enable row level security;
revoke all on table public.practice_session_events from anon, authenticated;
alter table public.request_logs enable row level security;
revoke all on table public.request_logs from anon, authenticated;

revoke execute on function public.set_updated_at() from public, anon, authenticated;

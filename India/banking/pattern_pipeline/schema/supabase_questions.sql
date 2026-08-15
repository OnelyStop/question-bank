-- Uniform banking questions table for Supabase.
-- Load rows from pattern_pipeline/out/questions.jsonl (one JSON object per line).

create extension if not exists "pgcrypto";

create table if not exists public.banking_questions (
  id uuid primary key default gen_random_uuid(),
  q_id text not null unique,
  bank text,
  role text,
  exam_type text,
  year integer,
  shift text,
  memory_based boolean,
  language text,
  section text,
  subject text,
  topic text,
  question_pattern text not null,
  secondary_patterns text[] not null default '{}',
  direction_id text,
  direction_text text,
  stem text not null,
  options jsonb not null default '{}'::jsonb,
  option_count integer not null default 0,
  answer text check (answer is null or answer in ('a', 'b', 'c', 'd', 'e')),
  explanation text,
  has_shared_directions boolean not null default false,
  is_bilingual boolean not null default false,
  has_image boolean not null default false,
  image_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists banking_questions_pattern_idx
  on public.banking_questions (question_pattern);

create index if not exists banking_questions_bank_role_year_idx
  on public.banking_questions (bank, role, year);

create index if not exists banking_questions_section_idx
  on public.banking_questions (section);

create index if not exists banking_questions_direction_idx
  on public.banking_questions (direction_id)
  where direction_id is not null;

create index if not exists banking_questions_bilingual_idx
  on public.banking_questions (is_bilingual)
  where is_bilingual = true;

create index if not exists banking_questions_image_idx
  on public.banking_questions (has_image)
  where has_image = true;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists banking_questions_set_updated_at on public.banking_questions;
create trigger banking_questions_set_updated_at
before update on public.banking_questions
for each row execute function public.set_updated_at();

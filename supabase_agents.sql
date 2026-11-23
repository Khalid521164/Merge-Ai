-- Merge AI custom Agent profiles (run once in Supabase SQL Editor)
-- The application accesses this table server-side using SUPABASE_SECRET_KEY.
-- Never expose the Supabase secret/service key in browser JavaScript.

create table if not exists public.ma2_agents (
    id uuid primary key,
    owner_sub text not null,
    name text not null check (char_length(name) between 2 and 48),
    description text not null check (char_length(description) between 1 and 180),
    instructions text not null check (char_length(instructions) between 20 and 6000),
    avatar text not null default '🤖',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ma2_agents_owner_updated_idx
    on public.ma2_agents (owner_sub, updated_at desc);

alter table public.ma2_agents enable row level security;

-- No public/anon policies are created. Merge AI accesses this table through
-- its server-side secret key, not from the browser.

-- Only the server-side service role may access custom agent profiles.
revoke all on table public.ma2_agents from anon, authenticated;
grant all on table public.ma2_agents to service_role;

-- Per-Google-account names for built-in and custom specialist agents.
-- Rows are accessed by the server with SUPABASE_SECRET_KEY only.
create table if not exists public.ma2_agent_aliases (
    owner_sub text not null,
    agent_id text not null check (char_length(agent_id) between 1 and 80),
    display_name text not null check (char_length(trim(display_name)) between 1 and 40),
    updated_at timestamptz not null default now(),
    primary key (owner_sub, agent_id)
);

alter table public.ma2_agent_aliases enable row level security;
revoke all on table public.ma2_agent_aliases from anon, authenticated;
grant all on table public.ma2_agent_aliases to service_role;

-- Merge AI Desktop Bridge relay.
-- The companion uses only the public anon key plus a per-session token;
-- the Supabase server-side secret key is never downloaded.

create table if not exists public.ma2_control_devices (
    session_id uuid primary key,
    chat_id uuid not null,
    owner_sub text not null,
    token_hash text not null check (char_length(token_hash) = 64),
    status text not null default 'pending'
        check (status in ('pending', 'active', 'stopped', 'expired')),
    pair_expires_at timestamptz not null,
    expires_at timestamptz not null,
    last_seen_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists ma2_control_devices_owner_idx
    on public.ma2_control_devices (owner_sub, created_at desc);

create table if not exists public.ma2_control_commands (
    command_id uuid primary key,
    session_id uuid not null references public.ma2_control_devices(session_id) on delete cascade,
    owner_sub text not null,
    action text not null check (
        action in ('screenshot', 'open_app', 'open_url', 'click', 'move_mouse', 'type_text', 'hotkey', 'scroll')
    ),
    arguments jsonb not null default '{}'::jsonb,
    status text not null default 'approved' check (
        status in ('approved', 'running', 'completed', 'failed', 'cancelled')
    ),
    result_text text,
    created_at timestamptz not null default now(),
    completed_at timestamptz
);

create index if not exists ma2_control_commands_queue_idx
    on public.ma2_control_commands (session_id, status, created_at);

alter table public.ma2_control_devices enable row level security;
alter table public.ma2_control_commands enable row level security;

revoke all on table public.ma2_control_devices from anon, authenticated;
revoke all on table public.ma2_control_commands from anon, authenticated;
grant all on table public.ma2_control_devices to service_role;
grant all on table public.ma2_control_commands to service_role;

create or replace function public.ma2_bridge_heartbeat(
    p_session_id uuid,
    p_token_hash text
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    update public.ma2_control_devices
       set status = case when status = 'pending' then 'active' else status end,
           last_seen_at = now()
     where session_id = p_session_id
       and token_hash = p_token_hash
       and status in ('pending', 'active')
       and expires_at > now()
       and (status = 'active' or pair_expires_at > now());

    return found;
end;
$$;

create or replace function public.ma2_bridge_claim_commands(
    p_session_id uuid,
    p_token_hash text,
    p_limit integer default 2
)
returns table (
    command_id uuid,
    action text,
    arguments jsonb,
    created_at timestamptz
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if not exists (
        select 1
          from public.ma2_control_devices d
         where d.session_id = p_session_id
           and d.token_hash = p_token_hash
           and d.status = 'active'
           and d.expires_at > now()
           and d.last_seen_at > now() - interval '30 seconds'
    ) then
        raise exception 'Bridge session is not active';
    end if;

    return query
    with picked as (
        select c.command_id
          from public.ma2_control_commands c
         where c.session_id = p_session_id
           and c.status = 'approved'
         order by c.created_at
         for update skip locked
         limit greatest(1, least(coalesce(p_limit, 2), 3))
    ),
    claimed as (
        update public.ma2_control_commands c
           set status = 'running'
          from picked p
         where c.command_id = p.command_id
        returning c.command_id, c.action, c.arguments, c.created_at
    )
    select claimed.command_id, claimed.action, claimed.arguments, claimed.created_at
      from claimed;
end;
$$;

create or replace function public.ma2_bridge_complete_command(
    p_session_id uuid,
    p_token_hash text,
    p_command_id uuid,
    p_status text,
    p_result_text text default ''
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if p_status not in ('completed', 'failed') then
        raise exception 'Invalid command result status';
    end if;

    if not exists (
        select 1
          from public.ma2_control_devices d
         where d.session_id = p_session_id
           and d.token_hash = p_token_hash
           and d.status = 'active'
           and d.expires_at > now()
    ) then
        return false;
    end if;

    update public.ma2_control_commands c
       set status = p_status,
           result_text = left(coalesce(p_result_text, ''), 500000),
           completed_at = now()
     where c.command_id = p_command_id
       and c.session_id = p_session_id
       and c.status = 'running';

    return found;
end;
$$;

revoke all on function public.ma2_bridge_heartbeat(uuid, text) from public;
revoke all on function public.ma2_bridge_claim_commands(uuid, text, integer) from public;
revoke all on function public.ma2_bridge_complete_command(uuid, text, uuid, text, text) from public;
grant execute on function public.ma2_bridge_heartbeat(uuid, text) to anon, authenticated;
grant execute on function public.ma2_bridge_claim_commands(uuid, text, integer) to anon, authenticated;
grant execute on function public.ma2_bridge_complete_command(uuid, text, uuid, text, text) to anon, authenticated;


-- Allow the visible Windows companion to revoke its own session immediately
-- when the local STOP control is pressed.
create or replace function public.ma2_bridge_stop(
    p_session_id uuid,
    p_token_hash text
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    update public.ma2_control_devices
       set status = 'stopped'
     where session_id = p_session_id
       and token_hash = p_token_hash
       and status in ('pending', 'active');

    if not found then
        return false;
    end if;

    update public.ma2_control_commands
       set status = 'cancelled'
     where session_id = p_session_id
       and status in ('approved', 'running');

    return true;
end;
$$;

revoke all on function public.ma2_bridge_stop(uuid, text) from public;
grant execute on function public.ma2_bridge_stop(uuid, text) to anon, authenticated;

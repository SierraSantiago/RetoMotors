create table if not exists app.help_knowledge (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    title text not null,
    section text not null,
    content text not null,
    search_vector tsvector generated always as (
        to_tsvector('spanish', coalesce(title, '') || ' ' || coalesce(section, '') || ' ' || content)
    ) stored,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists help_knowledge_search_idx
    on app.help_knowledge using gin (search_vector);

revoke all on table app.help_knowledge from public, anon, authenticated;
revoke usage on schema app from anon, authenticated;

drop function if exists public.search_help_knowledge(text, integer);
create function public.search_help_knowledge(
    p_query text,
    p_limit integer default 5
)
returns table(id uuid, title text, section text, content text, rank real)
language plpgsql
security definer
set search_path = pg_catalog, app
as $$
declare
    v_uid uuid := auth.uid();
    v_limit integer := least(greatest(coalesce(p_limit, 5), 1), 5);
begin
    if v_uid is null or not exists (
        select 1 from app.user_access ua where ua.user_id = v_uid and ua.active
    ) or nullif(trim(p_query), '') is null then
        return;
    end if;

    return query
    select hk.id, hk.title, hk.section, hk.content,
           ts_rank(hk.search_vector, websearch_to_tsquery('spanish', p_query))::real
    from app.help_knowledge hk
    where hk.search_vector @@ websearch_to_tsquery('spanish', p_query)
    order by ts_rank(hk.search_vector, websearch_to_tsquery('spanish', p_query)) desc, hk.slug
    limit v_limit;

    if not found then
        return query
        select hk.id, hk.title, hk.section, hk.content, 0::real
        from app.help_knowledge hk
        where lower(hk.title || ' ' || hk.section || ' ' || hk.content) like
              '%' || lower(trim(p_query)) || '%'
        order by hk.slug
        limit v_limit;
    end if;
end;
$$;

revoke all on function public.search_help_knowledge(text, integer) from public, anon, authenticated;
grant execute on function public.search_help_knowledge(text, integer) to authenticated;

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
    v_count integer := 0;
    v_added integer := 0;
begin
    if v_uid is null or not exists (
        select 1 from app.user_access ua where ua.user_id = v_uid and ua.active
    ) or nullif(trim(p_query), '') is null then
        return;
    end if;

    -- First preserve the precise AND-style search for queries with an exact match.
    return query
    select hk.id, hk.title, hk.section, hk.content,
           ts_rank(hk.search_vector, websearch_to_tsquery('spanish', p_query))::real
    from app.help_knowledge hk
    where hk.search_vector @@ websearch_to_tsquery('spanish', p_query)
    order by ts_rank(hk.search_vector, websearch_to_tsquery('spanish', p_query)) desc, hk.slug
    limit v_limit;
    get diagnostics v_count = row_count;
    if v_count >= v_limit then
        return;
    end if;

    -- Then use OR over lexemes produced by PostgreSQL, never raw user SQL.
    return query
    with lexemes as (
        select tsvector_to_array(to_tsvector('spanish', p_query)) as terms
    ), relaxed as (
        select array_to_string(terms, ' | ') as query_text
        from lexemes
        where cardinality(terms) > 0
    ), weighted as (
        select hk.*, setweight(to_tsvector('spanish', coalesce(hk.title, '')), 'A')
             || setweight(to_tsvector('spanish', coalesce(hk.section, '')), 'B')
             || setweight(to_tsvector('spanish', coalesce(hk.content, '')), 'C') as vector
        from app.help_knowledge hk
    )
    select w.id, w.title, w.section, w.content,
           ts_rank(w.vector, to_tsquery('spanish', relaxed.query_text))::real
    from weighted w cross join relaxed
    where w.search_vector @@ to_tsquery('spanish', relaxed.query_text)
      and w.id not in (
          select hk.id from app.help_knowledge hk
          where hk.search_vector @@ websearch_to_tsquery('spanish', p_query)
      )
    order by ts_rank(w.vector, to_tsquery('spanish', relaxed.query_text)) desc, w.title, w.id
    limit greatest(v_limit - v_count, 0);
    get diagnostics v_added = row_count;
    v_count := v_count + v_added;
    if v_count >= v_limit then
        return;
    end if;

    -- Finally match significant normalized terms individually for conversational phrasing.
    return query
    with lexemes as (
        select tsvector_to_array(to_tsvector('spanish', p_query)) as terms
    ), candidates as (
        select hk.*, lexemes.terms,
               setweight(to_tsvector('spanish', coalesce(hk.title, '')), 'A')
               || setweight(to_tsvector('spanish', coalesce(hk.section, '')), 'B')
               || setweight(to_tsvector('spanish', coalesce(hk.content, '')), 'C') as vector
        from app.help_knowledge hk cross join lexemes
    )
    select c.id, c.title, c.section, c.content,
           (cardinality(array(
               select term from unnest(c.terms) term
               where lower(c.title || ' ' || c.section || ' ' || c.content) like '%' || term || '%'
           ))::real + ts_rank(c.vector, plainto_tsquery('spanish', p_query)))
    from candidates c
    where exists (
        select 1 from unnest(c.terms) term
        where lower(c.title || ' ' || c.section || ' ' || c.content) like '%' || term || '%'
    )
      and c.id not in (
          select hk.id from app.help_knowledge hk
          where hk.search_vector @@ websearch_to_tsquery('spanish', p_query)
             or hk.search_vector @@ to_tsquery('spanish', array_to_string(c.terms, ' | '))
      )
    order by 5 desc, c.title, c.id
    limit greatest(v_limit - v_count, 0);
end;
$$;

revoke all on function public.search_help_knowledge(text, integer) from public, anon, authenticated;
grant execute on function public.search_help_knowledge(text, integer) to authenticated;

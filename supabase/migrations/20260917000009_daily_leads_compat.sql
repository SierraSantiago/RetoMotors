create or replace function public.get_daily_leads(
    p_assignment_date date,
    p_temperature text default null,
    p_assignment_status text default null,
    p_canal text default null,
    p_availability boolean default null,
    p_advisor_id text default null,
    p_search text default null
)
returns table(
    raw_row_id uuid, lead_id text, empresa_id text, punto_venta_id text,
    nombre_cliente text, telefono text, email text, canal text, fecha_registro date,
    modelo text, is_available_at_store boolean, priority_score numeric,
    global_priority_rank integer, temperature text, priority_reasons jsonb,
    advisor_id text, assignment_status text, lead_age_hours numeric
)
language sql security definer set search_path = pg_catalog, app
as $$
    select raw_row_id, lead_id, empresa_id, punto_venta_id, nombre_cliente, telefono,
        email, canal, fecha_registro, modelo, is_available_at_store, priority_score,
        global_priority_rank, temperature, priority_reasons, advisor_id,
        assignment_status, lead_age_hours
    from public.get_daily_leads(
        p_assignment_date, p_temperature, p_assignment_status, p_canal,
        p_availability, p_advisor_id, null, p_search
    );
$$;
revoke all on function public.get_daily_leads(date,text,text,text,boolean,text,text)
    from public, anon, authenticated;
grant execute on function public.get_daily_leads(date,text,text,text,boolean,text,text)
    to authenticated;

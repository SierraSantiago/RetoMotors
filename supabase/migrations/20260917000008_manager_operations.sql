-- Manager operational views through SECURITY DEFINER RPCs only.
drop function if exists public.get_daily_leads(date,text,text,text,boolean,text,text);
create function public.get_daily_leads(
    p_assignment_date date, p_temperature text default null,
    p_assignment_status text default null, p_canal text default null,
    p_availability boolean default null, p_advisor_id text default null,
    p_punto_venta_id text default null, p_search text default null
)
returns table(
    raw_row_id uuid, lead_id text, empresa_id text, punto_venta_id text,
    nombre_cliente text, telefono text, email text, canal text, fecha_registro date,
    modelo text, is_available_at_store boolean, priority_score numeric,
    global_priority_rank integer, company_priority_rank integer, temperature text,
    priority_reasons jsonb, advisor_id text, assignment_status text, lead_age_hours numeric
)
language plpgsql security definer set search_path = pg_catalog, app
as $$
declare v_empresa text; v_advisor text; v_role text;
begin
    select u.empresa_id, u.advisor_id, u.role into v_empresa, v_advisor, v_role
    from app.user_access u where u.user_id = auth.uid() and u.active;
    if not found then return; end if;
    return query
    with scoped as (
        select d.*, l.nombre_cliente, l.telefono_raw, l.email_raw,
            l.canal_normalizado, l.fecha_registro,
            coalesce(l.modelo_canonico, l.modelo_interes_normalizado) as display_model,
            l.is_available_at_store,
            row_number() over (
                partition by d.empresa_id
                order by d.priority_score desc, l.fecha_registro asc nulls last, d.raw_row_id
            )::integer as scoped_rank
        from ops.daily_lead_assignments d
        join marts.mart_leads_ai_enriched l on l.raw_row_id = d.raw_row_id
        where d.assignment_date = p_assignment_date and d.empresa_id = v_empresa
          and (v_role = 'manager' or d.advisor_id = v_advisor)
    )
    select s.raw_row_id, s.lead_id, s.empresa_id, s.punto_venta_id,
        s.nombre_cliente, s.telefono_raw, s.email_raw, s.canal_normalizado, s.fecha_registro,
        s.display_model, s.is_available_at_store, s.priority_score,
        s.global_priority_rank, s.scoped_rank, s.temperature, s.priority_reasons,
        s.advisor_id, s.assignment_status, s.lead_age_hours
    from scoped s
    where (p_temperature is null or s.temperature = p_temperature)
      and (p_assignment_status is null or s.assignment_status = p_assignment_status)
      and (p_canal is null or s.canal_normalizado = p_canal)
      and (p_availability is null or s.is_available_at_store is not distinct from p_availability)
      and (v_role <> 'manager' or p_advisor_id is null or s.advisor_id = p_advisor_id)
      and (p_punto_venta_id is null or s.punto_venta_id = p_punto_venta_id)
      and (p_search is null or p_search = '' or s.nombre_cliente ilike '%' || p_search || '%'
           or s.lead_id ilike '%' || p_search || '%'
           or s.telefono_raw ilike '%' || p_search || '%'
           or s.display_model ilike '%' || p_search || '%')
    order by s.scoped_rank;
end; $$;

drop function if exists public.get_manager_summary(date);
create function public.get_manager_summary(p_assignment_date date)
returns table(total_leads bigint, assigned bigint, backlog bigint, no_eligible bigint,
    hot bigint, warm bigint, cold bigint, hot_backlog bigint, capacity_total bigint, capacity_used bigint)
language plpgsql security definer set search_path = pg_catalog, app
as $$
declare v_empresa text; v_role text;
begin
    select u.empresa_id, u.role into v_empresa, v_role from app.user_access u
    where u.user_id = auth.uid() and u.active;
    if not found or v_role <> 'manager' then return; end if;
    return query select count(*)::bigint,
        count(*) filter(where d.assignment_status='ASSIGNED')::bigint,
        count(*) filter(where d.assignment_status='UNASSIGNED_CAPACITY')::bigint,
        count(*) filter(where d.assignment_status='NO_ELIGIBLE_ADVISOR')::bigint,
        count(*) filter(where d.temperature='HOT')::bigint,
        count(*) filter(where d.temperature='WARM')::bigint,
        count(*) filter(where d.temperature='COLD')::bigint,
        count(*) filter(where d.temperature='HOT' and d.assignment_status='UNASSIGNED_CAPACITY')::bigint,
        (select coalesce(sum(s.capacidad_diaria_leads),0)::bigint from staging.stg_asesores s
         where s.empresa_id=v_empresa and s.activo),
        count(*) filter(where d.assignment_status='ASSIGNED')::bigint
    from ops.daily_lead_assignments d where d.assignment_date=p_assignment_date and d.empresa_id=v_empresa;
end; $$;

drop function if exists public.get_advisor_capacity(date);
create function public.get_advisor_capacity(p_assignment_date date)
returns table(asesor_id text, nombre text, punto_venta_id text, capacidad bigint, asignados bigint, load_ratio numeric)
language plpgsql security definer set search_path = pg_catalog, app
as $$
declare v_empresa text; v_role text;
begin
    select u.empresa_id, u.role into v_empresa, v_role from app.user_access u
    where u.user_id = auth.uid() and u.active;
    if not found or v_role <> 'manager' then return; end if;
    return query select s.asesor_id, s.nombre, s.punto_venta_id, s.capacidad_diaria_leads::bigint,
        count(d.raw_row_id)::bigint,
        count(d.raw_row_id)::numeric / nullif(s.capacidad_diaria_leads,0)
    from staging.stg_asesores s
    left join ops.daily_lead_assignments d on d.advisor_id=s.asesor_id
        and d.assignment_date=p_assignment_date and d.assignment_status='ASSIGNED'
    where s.empresa_id=v_empresa and s.activo
    group by s.asesor_id, s.nombre, s.punto_venta_id, s.capacidad_diaria_leads
    order by s.asesor_id;
end; $$;

create or replace function public.get_manager_store_summary(p_assignment_date date)
returns table(punto_venta_id text, leads bigint, asignados bigint, backlog bigint, hot bigint, capacidad bigint)
language plpgsql security definer set search_path = pg_catalog, app
as $$
declare v_empresa text; v_role text;
begin
    select u.empresa_id, u.role into v_empresa, v_role from app.user_access u
    where u.user_id = auth.uid() and u.active;
    if not found or v_role <> 'manager' then return; end if;
    return query select d.punto_venta_id, count(*)::bigint,
        count(*) filter(where d.assignment_status='ASSIGNED')::bigint,
        count(*) filter(where d.assignment_status='UNASSIGNED_CAPACITY')::bigint,
        count(*) filter(where d.temperature='HOT')::bigint,
        (select coalesce(sum(s.capacidad_diaria_leads),0)::bigint from staging.stg_asesores s
         where s.empresa_id=v_empresa and s.activo and s.punto_venta_id=d.punto_venta_id)
    from ops.daily_lead_assignments d
    where d.assignment_date=p_assignment_date and d.empresa_id=v_empresa
    group by d.punto_venta_id order by d.punto_venta_id;
end; $$;

create or replace function public.get_manager_filter_options(p_assignment_date date)
returns table(punto_venta_id text, advisor_id text, advisor_name text, canal text)
language plpgsql security definer set search_path = pg_catalog, app
as $$
declare v_empresa text; v_role text;
begin
    select u.empresa_id, u.role into v_empresa, v_role from app.user_access u
    where u.user_id = auth.uid() and u.active;
    if not found or v_role <> 'manager' then return; end if;
    return query
    select distinct d.punto_venta_id, d.advisor_id, s.nombre, l.canal_normalizado
    from ops.daily_lead_assignments d
    join marts.mart_leads_ai_enriched l on l.raw_row_id=d.raw_row_id
    left join staging.stg_asesores s on s.asesor_id=d.advisor_id and s.empresa_id=v_empresa
    where d.assignment_date=p_assignment_date and d.empresa_id=v_empresa
    order by d.punto_venta_id, d.advisor_id, l.canal_normalizado;
end; $$;

revoke all on function public.get_daily_leads(date,text,text,text,boolean,text,text,text) from public, anon, authenticated;
revoke all on function public.get_manager_summary(date) from public, anon, authenticated;
revoke all on function public.get_advisor_capacity(date) from public, anon, authenticated;
revoke all on function public.get_manager_store_summary(date) from public, anon, authenticated;
revoke all on function public.get_manager_filter_options(date) from public, anon, authenticated;
grant execute on function public.get_daily_leads(date,text,text,text,boolean,text,text,text) to authenticated;
grant execute on function public.get_manager_summary(date) to authenticated;
grant execute on function public.get_advisor_capacity(date) to authenticated;
grant execute on function public.get_manager_store_summary(date) to authenticated;
grant execute on function public.get_manager_filter_options(date) to authenticated;

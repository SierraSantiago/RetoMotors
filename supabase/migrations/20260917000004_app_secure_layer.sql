create schema if not exists app;

create table if not exists app.user_access (
    user_id uuid primary key references auth.users(id) on delete cascade,
    empresa_id text not null,
    advisor_id text,
    role text not null check (role in ('advisor', 'manager')),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

revoke usage on schema app from anon, authenticated;
revoke all on all tables in schema app from anon, authenticated;
revoke all on all sequences in schema app from anon, authenticated;
alter default privileges in schema app revoke all on tables from anon, authenticated;
alter default privileges in schema app revoke all on sequences from anon, authenticated;

create or replace function public.get_current_profile()
returns table(user_id uuid, empresa_id text, advisor_id text, role text)
language plpgsql security definer
set search_path = pg_catalog, app
as $$
begin
    return query
    select u.user_id, u.empresa_id, u.advisor_id, u.role
    from app.user_access u
    where u.user_id = auth.uid() and u.active;
end;
$$;

create or replace function public.get_available_assignment_dates()
returns table(assignment_date date)
language plpgsql security definer
set search_path = pg_catalog, app
as $$
begin
    if not exists (select 1 from app.user_access u where u.user_id = auth.uid() and u.active) then
        return;
    end if;
    return query select distinct d.assignment_date
    from ops.daily_lead_assignments d
    order by d.assignment_date desc;
end;
$$;

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
language plpgsql security definer
set search_path = pg_catalog, app
as $$
declare
    v_empresa text;
    v_advisor text;
    v_role text;
begin
    select u.empresa_id, u.advisor_id, u.role into v_empresa, v_advisor, v_role
    from app.user_access u where u.user_id = auth.uid() and u.active;
    if not found then return; end if;
    return query
    select d.raw_row_id, d.lead_id, d.empresa_id, d.punto_venta_id,
        l.nombre_cliente, l.telefono_raw, l.email_raw, l.canal_normalizado, l.fecha_registro,
        coalesce(l.modelo_canonico, l.modelo_interes_normalizado), l.is_available_at_store,
        d.priority_score, d.global_priority_rank, d.temperature, d.priority_reasons,
        d.advisor_id, d.assignment_status, d.lead_age_hours
    from ops.daily_lead_assignments d
    join marts.mart_leads_ai_enriched l on l.raw_row_id = d.raw_row_id
    where d.assignment_date = p_assignment_date
      and d.empresa_id = v_empresa
      and (v_role = 'manager' or d.advisor_id = v_advisor)
      and (p_temperature is null or d.temperature = p_temperature)
      and (p_assignment_status is null or d.assignment_status = p_assignment_status)
      and (p_canal is null or l.canal_normalizado = p_canal)
      and (p_availability is null or l.is_available_at_store is not distinct from p_availability)
      and (v_role <> 'manager' or p_advisor_id is null or d.advisor_id = p_advisor_id)
      and (p_search is null or p_search = '' or
           l.nombre_cliente ilike '%' || p_search || '%' or
           l.lead_id ilike '%' || p_search || '%' or
           l.telefono_raw ilike '%' || p_search || '%' or
           coalesce(l.modelo_canonico, l.modelo_interes_normalizado) ilike '%' || p_search || '%')
    order by d.global_priority_rank;
end;
$$;

create or replace function public.get_lead_detail(p_assignment_date date, p_raw_row_id uuid)
returns table(
    raw_row_id uuid, lead_id text, empresa_id text, punto_venta_id text,
    nombre_cliente text, telefono text, email text, canal text, fecha_registro date,
    modelo_solicitado text, modelo_canonico text, precio_lista numeric,
    is_available_at_store boolean, intencion text, presupuesto numeric,
    cuota_inicial numeric, forma_pago text, objecion_principal text,
    pidio_cita boolean, pidio_cotizacion boolean, priority_score numeric,
    temperature text, priority_reasons jsonb, conversation_component numeric,
    sla_component numeric, availability_component numeric, propensity_component numeric,
    propensity_score numeric, propensity_percentile numeric, advisor_id text,
    assignment_status text, assignment_date date, lead_age_hours numeric,
    conversation_count bigint, conversation_ids text[]
)
language plpgsql security definer
set search_path = pg_catalog, app
as $$
declare
    v_empresa text;
    v_advisor text;
    v_role text;
begin
    select u.empresa_id, u.advisor_id, u.role into v_empresa, v_advisor, v_role
    from app.user_access u where u.user_id = auth.uid() and u.active;
    if not found then return; end if;
    return query
    select d.raw_row_id, d.lead_id, d.empresa_id, d.punto_venta_id,
        l.nombre_cliente, l.telefono_raw, l.email_raw, l.canal_normalizado, l.fecha_registro,
        l.modelo_interes_raw, l.modelo_canonico, l.precio_lista, l.is_available_at_store,
        l.conversation_intencion, l.conversation_presupuesto, l.conversation_cuota_inicial,
        l.conversation_forma_pago, l.conversation_objecion_principal,
        l.conversation_pidio_cita, l.conversation_pidio_cotizacion,
        d.priority_score, d.temperature, d.priority_reasons,
        d.conversation_component, d.sla_component, d.availability_component,
        d.propensity_component, d.propensity_score, d.propensity_percentile,
        d.advisor_id, d.assignment_status, d.assignment_date, d.lead_age_hours,
        l.conversation_count, l.conversation_ids
    from ops.daily_lead_assignments d
    join marts.mart_leads_ai_enriched l on l.raw_row_id = d.raw_row_id
    where d.assignment_date = p_assignment_date and d.raw_row_id = p_raw_row_id
      and d.empresa_id = v_empresa and (v_role = 'manager' or d.advisor_id = v_advisor);
end;
$$;

create or replace function public.get_manager_summary(p_assignment_date date)
returns table(
    total_leads bigint, assigned bigint, backlog bigint, no_eligible bigint,
    hot bigint, warm bigint, cold bigint, capacity_total bigint, capacity_used bigint
)
language plpgsql security definer
set search_path = pg_catalog, app
as $$
declare v_empresa text; v_role text;
begin
    select u.empresa_id, u.role into v_empresa, v_role from app.user_access u
    where u.user_id = auth.uid() and u.active;
    if not found or v_role <> 'manager' then return; end if;
    return query
    select count(*)::bigint,
        count(*) filter(where d.assignment_status='ASSIGNED')::bigint,
        count(*) filter(where d.assignment_status='UNASSIGNED_CAPACITY')::bigint,
        count(*) filter(where d.assignment_status='NO_ELIGIBLE_ADVISOR')::bigint,
        count(*) filter(where d.temperature='HOT')::bigint,
        count(*) filter(where d.temperature='WARM')::bigint,
        count(*) filter(where d.temperature='COLD')::bigint,
        (select coalesce(sum(s.capacidad_diaria_leads),0)::bigint from staging.stg_asesores s where s.empresa_id=v_empresa and s.activo),
        count(*) filter(where d.assignment_status='ASSIGNED')::bigint
    from ops.daily_lead_assignments d where d.assignment_date=p_assignment_date and d.empresa_id=v_empresa;
end;
$$;

create or replace function public.get_advisor_capacity(p_assignment_date date)
returns table(asesor_id text, punto_venta_id text, capacidad bigint, asignados bigint, load_ratio numeric)
language plpgsql security definer
set search_path = pg_catalog, app
as $$
declare v_empresa text; v_role text;
begin
    select u.empresa_id, u.role into v_empresa, v_role from app.user_access u
    where u.user_id = auth.uid() and u.active;
    if not found or v_role <> 'manager' then return; end if;
    return query
    select s.asesor_id, s.punto_venta_id, s.capacidad_diaria_leads::bigint,
        count(d.raw_row_id)::bigint,
        count(d.raw_row_id)::numeric / nullif(s.capacidad_diaria_leads,0)
    from staging.stg_asesores s
    left join ops.daily_lead_assignments d on d.advisor_id=s.asesor_id
        and d.assignment_date=p_assignment_date and d.assignment_status='ASSIGNED'
    where s.empresa_id=v_empresa and s.activo
    group by s.asesor_id, s.punto_venta_id, s.capacidad_diaria_leads
    order by s.asesor_id;
end;
$$;

revoke all on function public.get_current_profile() from public, anon, authenticated;
revoke all on function public.get_available_assignment_dates() from public, anon, authenticated;
revoke all on function public.get_daily_leads(date,text,text,text,boolean,text,text) from public, anon, authenticated;
revoke all on function public.get_lead_detail(date,uuid) from public, anon, authenticated;
revoke all on function public.get_manager_summary(date) from public, anon, authenticated;
revoke all on function public.get_advisor_capacity(date) from public, anon, authenticated;
grant execute on function public.get_current_profile() to authenticated;
grant execute on function public.get_available_assignment_dates() to authenticated;
grant execute on function public.get_daily_leads(date,text,text,text,boolean,text,text) to authenticated;
grant execute on function public.get_lead_detail(date,uuid) to authenticated;
grant execute on function public.get_manager_summary(date) to authenticated;
grant execute on function public.get_advisor_capacity(date) to authenticated;

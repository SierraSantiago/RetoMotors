alter table ops.daily_lead_assignments
    add column if not exists responded_at timestamptz,
    add column if not exists responded_by uuid references auth.users(id);

drop function if exists public.get_daily_leads(date,text,text,text,boolean,text,text,text);
drop function if exists public.get_daily_leads(date,text,text,text,boolean,text,text);

create function public.get_daily_leads(
    p_assignment_date date,
    p_temperature text default null,
    p_assignment_status text default null,
    p_canal text default null,
    p_availability boolean default null,
    p_advisor_id text default null,
    p_punto_venta_id text default null,
    p_search text default null,
    p_management_status text default null
)
returns table(
    raw_row_id uuid, lead_id text, empresa_id text, punto_venta_id text,
    nombre_cliente text, telefono text, email text, canal text, fecha_registro date,
    modelo text, is_available_at_store boolean, priority_score numeric,
    global_priority_rank integer, company_priority_rank integer, temperature text,
    priority_reasons jsonb, advisor_id text, assignment_status text, lead_age_hours numeric,
    responded_at timestamptz, responded_by uuid
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
        s.advisor_id, s.assignment_status, s.lead_age_hours,
        s.responded_at, s.responded_by
    from scoped s
    where (p_temperature is null or s.temperature = p_temperature)
      and (p_assignment_status is null or s.assignment_status = p_assignment_status)
      and (p_canal is null or s.canal_normalizado = p_canal)
      and (p_availability is null or s.is_available_at_store is not distinct from p_availability)
      and (v_role <> 'manager' or p_advisor_id is null or s.advisor_id = p_advisor_id)
      and (p_punto_venta_id is null or s.punto_venta_id = p_punto_venta_id)
      and (p_management_status is null
           or (p_management_status = 'RESPONDED' and s.responded_at is not null)
           or (p_management_status = 'PENDING' and s.responded_at is null))
      and (p_search is null or p_search = '' or s.nombre_cliente ilike '%' || p_search || '%'
           or s.lead_id ilike '%' || p_search || '%'
           or s.telefono_raw ilike '%' || p_search || '%'
           or s.display_model ilike '%' || p_search || '%')
    order by s.scoped_rank;
end; $$;

drop function if exists public.get_lead_detail(date, uuid);
create function public.get_lead_detail(p_assignment_date date, p_raw_row_id uuid)
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
    conversation_count bigint, conversation_ids text[], responded_at timestamptz,
    responded_by uuid
)
language plpgsql security definer set search_path = pg_catalog, app
as $$
declare v_empresa text; v_advisor text; v_role text;
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
        l.conversation_count, l.conversation_ids, d.responded_at, d.responded_by
    from ops.daily_lead_assignments d
    join marts.mart_leads_ai_enriched l on l.raw_row_id = d.raw_row_id
    where d.assignment_date = p_assignment_date and d.raw_row_id = p_raw_row_id
      and d.empresa_id = v_empresa and (v_role = 'manager' or d.advisor_id = v_advisor);
end; $$;

drop function if exists public.get_manager_summary(date);
create function public.get_manager_summary(p_assignment_date date)
returns table(
    total_leads bigint, assigned bigint, backlog bigint, no_eligible bigint,
    hot bigint, warm bigint, cold bigint, hot_backlog bigint, capacity_total bigint,
    capacity_used bigint, responded bigint, pending_response bigint, managed_pct numeric
)
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
        count(*) filter(where d.assignment_status='ASSIGNED')::bigint,
        count(*) filter(where d.assignment_status='ASSIGNED' and d.responded_at is not null)::bigint,
        count(*) filter(where d.assignment_status='ASSIGNED' and d.responded_at is null)::bigint,
        coalesce(round(100.0 * count(*) filter(where d.assignment_status='ASSIGNED' and d.responded_at is not null)
            / nullif(count(*) filter(where d.assignment_status='ASSIGNED'),0), 2), 0)
    from ops.daily_lead_assignments d where d.assignment_date=p_assignment_date and d.empresa_id=v_empresa;
end; $$;

drop function if exists public.get_advisor_capacity(date);
create function public.get_advisor_capacity(p_assignment_date date)
returns table(asesor_id text, nombre text, punto_venta_id text, capacidad bigint, asignados bigint,
    responded bigint, pending_response bigint, load_ratio numeric)
language plpgsql security definer set search_path = pg_catalog, app
as $$
declare v_empresa text; v_role text;
begin
    select u.empresa_id, u.role into v_empresa, v_role from app.user_access u
    where u.user_id = auth.uid() and u.active;
    if not found or v_role <> 'manager' then return; end if;
    return query select s.asesor_id, s.nombre, s.punto_venta_id, s.capacidad_diaria_leads::bigint,
        count(d.raw_row_id) filter(where d.assignment_status='ASSIGNED')::bigint,
        count(d.raw_row_id) filter(where d.assignment_status='ASSIGNED' and d.responded_at is not null)::bigint,
        count(d.raw_row_id) filter(where d.assignment_status='ASSIGNED' and d.responded_at is null)::bigint,
        count(d.raw_row_id) filter(where d.assignment_status='ASSIGNED')::numeric / nullif(s.capacidad_diaria_leads,0)
    from staging.stg_asesores s
    left join ops.daily_lead_assignments d on d.advisor_id=s.asesor_id
        and d.assignment_date=p_assignment_date
    where s.empresa_id=v_empresa and s.activo
    group by s.asesor_id, s.nombre, s.punto_venta_id, s.capacidad_diaria_leads
    order by s.asesor_id;
end; $$;

create or replace function public.set_lead_responded(
    p_assignment_date date,
    p_raw_row_id uuid,
    p_responded boolean
)
returns table(responded_at timestamptz, responded_by uuid)
language plpgsql security definer set search_path = pg_catalog, app
as $$
declare v_empresa text; v_advisor text; v_role text;
begin
    select u.empresa_id, u.advisor_id, u.role into v_empresa, v_advisor, v_role
    from app.user_access u where u.user_id = auth.uid() and u.active;
    if not found or v_role <> 'advisor' then
        raise exception 'No autorizado' using errcode = '42501';
    end if;
    update ops.daily_lead_assignments d
    set responded_at = case when p_responded then now() else null end,
        responded_by = case when p_responded then auth.uid() else null end,
        updated_at = now()
    where d.assignment_date = p_assignment_date
      and d.raw_row_id = p_raw_row_id
      and d.empresa_id = v_empresa
      and d.advisor_id = v_advisor
      and d.assignment_status = 'ASSIGNED';
    if not found then
        raise exception 'Lead no autorizado o no asignado' using errcode = '42501';
    end if;
    return query select d.responded_at, d.responded_by
        from ops.daily_lead_assignments d
        where d.assignment_date=p_assignment_date and d.raw_row_id=p_raw_row_id;
end; $$;

revoke all on function public.get_daily_leads(date,text,text,text,boolean,text,text,text,text) from public, anon, authenticated;
revoke all on function public.get_lead_detail(date,uuid) from public, anon, authenticated;
revoke all on function public.get_manager_summary(date) from public, anon, authenticated;
revoke all on function public.get_advisor_capacity(date) from public, anon, authenticated;
revoke all on function public.set_lead_responded(date,uuid,boolean) from public, anon, authenticated;
grant execute on function public.get_daily_leads(date,text,text,text,boolean,text,text,text,text) to authenticated;
grant execute on function public.get_lead_detail(date,uuid) to authenticated;
grant execute on function public.get_manager_summary(date) to authenticated;
grant execute on function public.get_advisor_capacity(date) to authenticated;
grant execute on function public.set_lead_responded(date,uuid,boolean) to authenticated;

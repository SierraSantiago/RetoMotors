create or replace function public.get_lead_conversation_history(
    p_assignment_date date,
    p_raw_row_id uuid
)
returns table(
    conversation_id text,
    conversation_started_at date,
    message_order integer,
    message_time text,
    speaker text,
    message_text text
)
language plpgsql
security definer
set search_path = pg_catalog, app
as $$
declare
    v_empresa text;
    v_advisor text;
    v_role text;
    v_lead_id text;
begin
    select u.empresa_id, u.advisor_id, u.role
    into v_empresa, v_advisor, v_role
    from app.user_access u
    where u.user_id = auth.uid() and u.active;

    if not found then
        return;
    end if;

    select d.lead_id
    into v_lead_id
    from ops.daily_lead_assignments d
    where d.assignment_date = p_assignment_date
      and d.raw_row_id = p_raw_row_id
      and d.empresa_id = v_empresa
      and (v_role = 'manager' or d.advisor_id = v_advisor);

    if not found then
        return;
    end if;

    return query
    select c.conversacion_id,
        c.fecha_inicio,
        messages.message_order::integer,
        nullif(messages.message_value->>'hora', ''),
        lower(nullif(messages.message_value->>'emisor', '')),
        messages.message_value->>'texto'
    from staging.stg_conversations c
    cross join lateral jsonb_array_elements(c.mensajes)
        with ordinality as messages(message_value, message_order)
    where c.lead_id = v_lead_id
    order by c.fecha_inicio asc nulls last,
        c.conversacion_id asc,
        messages.message_order asc;
end;
$$;

revoke all on function public.get_lead_conversation_history(date,uuid)
    from public, anon, authenticated;
grant execute on function public.get_lead_conversation_history(date,uuid)
    to authenticated;

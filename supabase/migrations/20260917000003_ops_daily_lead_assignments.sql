create table if not exists ops.daily_lead_assignments (
    assignment_date date not null,
    raw_row_id uuid not null,
    lead_id text,
    empresa_id text not null,
    punto_venta_id text,
    priority_score numeric not null check (priority_score >= 0 and priority_score <= 100),
    global_priority_rank integer not null,
    store_priority_rank integer not null,
    temperature text not null check (temperature in ('HOT', 'WARM', 'COLD')),
    priority_reasons jsonb not null,
    propensity_score numeric,
    propensity_percentile numeric check (propensity_percentile between 0 and 1),
    propensity_component numeric not null check (propensity_component between 0 and 5),
    conversation_component numeric not null check (conversation_component between 0 and 45),
    sla_component numeric not null check (sla_component between 0 and 30),
    availability_component numeric not null check (availability_component between 0 and 20),
    advisor_id text,
    assignment_status text not null check (assignment_status in ('ASSIGNED', 'UNASSIGNED_CAPACITY', 'NO_ELIGIBLE_ADVISOR')),
    lead_age_hours numeric not null check (lead_age_hours >= 0),
    scoring_timestamp timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (assignment_date, raw_row_id)
);

revoke usage on schema ops from anon, authenticated;
revoke all on all tables in schema ops from anon, authenticated;
revoke all on all sequences in schema ops from anon, authenticated;
alter default privileges in schema ops revoke all on tables from anon, authenticated;
alter default privileges in schema ops revoke all on sequences from anon, authenticated;

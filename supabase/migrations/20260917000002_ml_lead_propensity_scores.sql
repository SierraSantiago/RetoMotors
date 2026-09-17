create schema if not exists ml;

create table if not exists ml.lead_propensity_scores (
    score_id uuid primary key default gen_random_uuid(),
    raw_row_id uuid not null,
    lead_id text,
    propensity_score numeric not null check (propensity_score >= 0 and propensity_score <= 1),
    model_version text not null,
    training_data_hash text not null,
    scored_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_lead_propensity_score_key unique (raw_row_id, model_version)
);

revoke usage on schema ml from anon, authenticated;
revoke all on all tables in schema ml from anon, authenticated;
revoke all on all sequences in schema ml from anon, authenticated;
alter default privileges in schema ml revoke all on tables from anon, authenticated;
alter default privileges in schema ml revoke all on sequences from anon, authenticated;

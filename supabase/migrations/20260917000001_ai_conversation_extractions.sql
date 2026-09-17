create schema if not exists ai;

create table if not exists ai.conversation_extractions (
    extraction_id uuid primary key default gen_random_uuid(),
    conversation_id text not null,
    lead_id text,
    conversation_hash text not null,
    semantic_prompt_version text not null,
    semantic_prompt_hash text not null,
    batch_contract_version text not null,
    model_requested text not null,
    model_returned text,
    status text not null check (status in ('SUCCESS', 'ERROR')),
    modelo_interes text,
    presupuesto numeric,
    cuota_inicial numeric,
    forma_pago text,
    intencion text,
    objecion_principal text,
    pidio_cita boolean,
    pidio_cotizacion boolean,
    evidencia jsonb,
    evidence_grounded boolean,
    error_type text,
    error_message text,
    processed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (
        conversation_id,
        conversation_hash,
        semantic_prompt_hash,
        batch_contract_version,
        model_requested
    )
);

revoke usage on schema ai from anon, authenticated;
revoke all on all tables in schema ai from anon, authenticated;
revoke all on all sequences in schema ai from anon, authenticated;
alter default privileges in schema ai revoke all on tables from anon, authenticated;
alter default privileges in schema ai revoke all on sequences from anon, authenticated;

create schema if not exists raw;
create schema if not exists ops;

create table if not exists ops.pipeline_runs (
    run_id uuid primary key default gen_random_uuid(),
    pipeline_name text not null,
    status text not null check (status in ('RUNNING', 'SUCCEEDED', 'FAILED')),
    started_at timestamptz not null,
    finished_at timestamptz,
    files_loaded integer not null default 0,
    files_skipped integer not null default 0,
    rows_loaded integer not null default 0,
    error_message text,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists ops.ingestion_files (
    ingestion_file_id uuid primary key default gen_random_uuid(),
    first_ingested_run_id uuid not null references ops.pipeline_runs(run_id),
    source_name text not null check (source_name in (
        'leads', 'conversations', 'catalogo_motos', 'asesores', 'historico_cierres'
    )),
    source_file_name text not null,
    file_sha256 text not null,
    file_size_bytes bigint not null,
    row_count integer,
    status text not null check (status in ('LOADING', 'LOADED', 'FAILED')),
    ingested_at timestamptz,
    error_message text,
    created_at timestamptz not null default now(),
    unique (source_name, file_sha256)
);

create table if not exists raw.leads (
    lead_id text, fecha_registro text, canal text, empresa_id text,
    punto_venta_id text, nombre_cliente text, telefono text, email text,
    ciudad text, modelo_interes_texto text, estado_gestion text,
    fecha_primer_contacto text, campania text,
    raw_row_id uuid primary key default gen_random_uuid(),
    ingestion_file_id uuid not null references ops.ingestion_files(ingestion_file_id),
    source_row_number integer not null,
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now(),
    unique (ingestion_file_id, source_row_number)
);

create table if not exists raw.conversations (
    conversacion_id text, lead_id text, canal text, fecha_inicio text,
    mensajes jsonb,
    raw_row_id uuid primary key default gen_random_uuid(),
    ingestion_file_id uuid not null references ops.ingestion_files(ingestion_file_id),
    source_row_number integer not null,
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now(),
    unique (ingestion_file_id, source_row_number)
);

create table if not exists raw.catalogo_motos (
    sku text, marca text, linea text, cilindraje text, segmento text,
    precio_lista text, puntos_venta_disponibles text, unidades_disponibles text,
    raw_row_id uuid primary key default gen_random_uuid(),
    ingestion_file_id uuid not null references ops.ingestion_files(ingestion_file_id),
    source_row_number integer not null,
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now(),
    unique (ingestion_file_id, source_row_number)
);

create table if not exists raw.asesores (
    asesor_id text, nombre text, punto_venta_id text, empresa_id text,
    capacidad_diaria_leads text, activo text, fecha_ingreso text,
    raw_row_id uuid primary key default gen_random_uuid(),
    ingestion_file_id uuid not null references ops.ingestion_files(ingestion_file_id),
    source_row_number integer not null,
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now(),
    unique (ingestion_file_id, source_row_number)
);

create table if not exists raw.historico_cierres (
    lead_id text, fecha_registro text, canal text, empresa_id text,
    punto_venta_id text, modelo_cotizado text, precio_lista text,
    horas_al_primer_contacto text, numero_contactos text,
    manifesto_cuota_inicial text, forma_pago_declarada text, pidio_cita text,
    desenlace text,
    raw_row_id uuid primary key default gen_random_uuid(),
    ingestion_file_id uuid not null references ops.ingestion_files(ingestion_file_id),
    source_row_number integer not null,
    raw_payload jsonb not null,
    loaded_at timestamptz not null default now(),
    unique (ingestion_file_id, source_row_number)
);

revoke usage on schema raw, ops from anon, authenticated;
revoke all on all tables in schema raw, ops from anon, authenticated;
revoke all on all sequences in schema raw, ops from anon, authenticated;
alter default privileges in schema raw revoke all on tables from anon, authenticated;
alter default privileges in schema ops revoke all on tables from anon, authenticated;
alter default privileges in schema raw revoke all on sequences from anon, authenticated;
alter default privileges in schema ops revoke all on sequences from anon, authenticated;

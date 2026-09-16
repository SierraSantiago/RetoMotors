create schema if not exists staging;

revoke usage on schema staging from anon, authenticated;
revoke all on all tables in schema staging from anon, authenticated;
revoke all on all sequences in schema staging from anon, authenticated;
alter default privileges in schema staging revoke all on tables from anon, authenticated;
alter default privileges in schema staging revoke all on sequences from anon, authenticated;

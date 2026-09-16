create schema if not exists intermediate;

revoke usage on schema intermediate from anon, authenticated;
revoke all on all tables in schema intermediate from anon, authenticated;
revoke all on all sequences in schema intermediate from anon, authenticated;
alter default privileges in schema intermediate revoke all on tables from anon, authenticated;
alter default privileges in schema intermediate revoke all on sequences from anon, authenticated;

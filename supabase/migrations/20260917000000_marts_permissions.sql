create schema if not exists marts;

revoke usage on schema marts from anon, authenticated;
revoke all on all tables in schema marts from anon, authenticated;
revoke all on all sequences in schema marts from anon, authenticated;
alter default privileges in schema marts revoke all on tables from anon, authenticated;
alter default privileges in schema marts revoke all on sequences from anon, authenticated;

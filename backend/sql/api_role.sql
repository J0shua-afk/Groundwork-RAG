-- The read-only login the deployed API uses. Run once, in the PUBLIC project only.
-- Set the password here in the SQL editor; never commit a real one.

create role groundwork_api with login password 'replace-with-a-long-random-password';

-- stops a runaway query from tying up the function
alter role groundwork_api set statement_timeout = '10s';

-- pgvector's <=> lives in the extensions schema. Supabase puts extensions on the search path
-- for its own roles, not new ones, and without this the search fails with "operator does not
-- exist: extensions.vector <=> extensions.vector"
alter role groundwork_api set search_path = public, extensions;

-- extensions holds pgvector's type and its <=> operator
grant usage on schema public, extensions to groundwork_api;
grant select on postings, chunks to groundwork_api;

-- RLS is on with no policies, so the grants alone still show zero rows. these let exactly this
-- role read. scoped "to groundwork_api" on purpose: the default (public) would also let the
-- anon key read through Supabase's REST API
create policy "api reads postings" on postings for select to groundwork_api using (true);
create policy "api reads chunks" on chunks for select to groundwork_api using (true);

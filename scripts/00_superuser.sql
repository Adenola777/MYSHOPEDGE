-- Local QA harness only. Not production. Roles are cluster-wide.
do $$begin
  if not exists(select 1 from pg_roles where rolname='mse_owner') then create role mse_owner nologin; end if;
  if not exists(select 1 from pg_roles where rolname='mse_migrator') then create role mse_migrator login bypassrls; end if;
  if not exists(select 1 from pg_roles where rolname='mse_app') then create role mse_app login nobypassrls; end if;
  if not exists(select 1 from pg_roles where rolname='mse_analytics') then create role mse_analytics login nobypassrls; end if;
end$$;
alter role mse_migrator password 'migpw_local';
alter role mse_app password 'apppw_local';
alter role mse_analytics password 'anapw_local';
grant mse_owner to mse_migrator with admin option;
grant mse_app to mse_migrator with admin option;
grant mse_analytics to mse_migrator with admin option;

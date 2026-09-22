-- MyShopEdge v0.2 migration 0002: append-only ledger and logs.
-- LED-1 requires that no ledger row can be updated or deleted by the application.
-- v0.1 stated the rule and enforced nothing. Two layers now enforce it.

-- Layer one: privileges. The application cannot ask for an update or a delete.
revoke update, delete, truncate on ledger_entries from mse_app;
revoke update, delete, truncate on change_log    from mse_app;
revoke update, delete, truncate on audit_log     from mse_app;

-- Layer two: a trigger, which holds whatever role is connected, including the owner
-- and the migrator. Maintenance that genuinely must rewrite history sets a local
-- flag, which is visible in the logs and cannot be set by accident.
create or replace function enforce_append_only() returns trigger
language plpgsql as $$
begin
  if coalesce(current_setting('app.allow_ledger_maintenance', true), 'off') = 'on' then
    return case tg_op when 'DELETE' then old else new end;
  end if;
  raise exception
    '% is append-only: % is not permitted (LED-1). Post a correcting adjustment entry instead.',
    tg_table_name, tg_op
    using errcode = '42501';
end $$;

create or replace function enforce_append_only_stmt() returns trigger
language plpgsql as $$
begin
  if coalesce(current_setting('app.allow_ledger_maintenance', true), 'off') = 'on' then
    return null;
  end if;
  raise exception '% is append-only: TRUNCATE is not permitted (LED-1).', tg_table_name
    using errcode = '42501';
end $$;

create trigger ledger_entries_no_update before update on ledger_entries
  for each row execute function enforce_append_only();
create trigger ledger_entries_no_delete before delete on ledger_entries
  for each row execute function enforce_append_only();
create trigger ledger_entries_no_truncate before truncate on ledger_entries
  for each statement execute function enforce_append_only_stmt();

create trigger change_log_no_update before update on change_log
  for each row execute function enforce_append_only();
create trigger change_log_no_delete before delete on change_log
  for each row execute function enforce_append_only();

create trigger audit_log_no_update before update on audit_log
  for each row execute function enforce_append_only();
create trigger audit_log_no_delete before delete on audit_log
  for each row execute function enforce_append_only();

-- Retention still works. Section 4.6 purges raw_events and expired exports, neither of
-- which is append-only. Ledger retention, where it is ever needed, deletes the whole
-- account under ACC-4 rather than individual rows.

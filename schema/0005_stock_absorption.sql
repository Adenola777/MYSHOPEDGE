-- MyShopEdge v0.2 migration 0005: stock absorption (Action 4, STK-8).
-- Stops a returned unit being counted twice when the seller also restores it in TikTok.

-- The v0.1 column is movement_type, and its existing check already enforces STK-4's
-- rule that a manual adjustment carries a reason. Only the new kind is added.
alter table stock_movements drop constraint stock_movements_movement_type_check;
alter table stock_movements add constraint stock_movements_movement_type_check
  check (movement_type = any (array[
    'sale_reserved','posted','cancelled','return_resellable','write_off',
    'manual_adjustment','adjustment_absorbed']));

comment on constraint stock_movements_movement_type_check on stock_movements is
  'adjustment_absorbed records STK-8: an unexplained rise in TikTok stock taken out of '
  'the seller adjustment so the same unit is not counted twice. quantity is the number '
  'of units absorbed and on_shelf does not move.';

-- The tolerance above which a rise is treated as a restock rather than a duplicate.
alter table alert_settings
  add column absorption_tolerance_units integer not null default 20
    check (absorption_tolerance_units between 0 and 1000);

comment on column alert_settings.absorption_tolerance_units is
  'STK-8. An unexplained rise in TikTok stock above this many units is not absorbed. '
  'It raises a discrepancy under DSC-1 instead, because absorbing a large figure '
  'silently would do more damage than the duplicate it prevents.';

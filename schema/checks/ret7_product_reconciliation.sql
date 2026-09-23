-- A4 RET-7. The shop total must equal the sum of the product figures.
--
-- Run against any branch with a seeded shop. It raises if the identity breaks, so it can
-- run nightly rather than being something somebody remembers to look at.
--
-- Verified on the development branch, 23 September 2026, for July and August 2026:
--   Net Proceeds  shop 50038  products 50038
--   Return Loss   shop  5550  products  5550
--   You keep      shop 24816  products 24816
--
-- The five entries carrying no sku_id are platform_adjustment, reserve_withheld and
-- settlement. None contributes to Net Proceeds or Return Loss, which is why the product
-- table closes exactly. If a future category posts to those entry types without a SKU,
-- this check is what catches it.
do $$
declare
  shop constant uuid := '8a773a13-73b5-a382-7dd0-fda02e950369';
  d1 constant date := '2026-07-01';
  d2 constant date := '2026-08-31';
  shop_np bigint; shop_rl bigint; prod_np bigint; prod_rl bigint;
begin
  select coalesce(sum(amount_minor) filter (where entry_type in ('sale','refund','platform_deduction')),0),
         coalesce(sum(amount_minor) filter (where entry_type in ('return_cost','write_off')),0)
    into shop_np, shop_rl
    from ledger_entries where shop_id = shop and basis_day between d1 and d2;

  select coalesce(sum(amount_minor) filter (where entry_type in ('sale','refund','platform_deduction')),0),
         coalesce(sum(amount_minor) filter (where entry_type in ('return_cost','write_off')),0)
    into prod_np, prod_rl
    from ledger_entries le join skus s on s.id = le.sku_id
   where le.shop_id = shop and le.basis_day between d1 and d2;

  if shop_np <> prod_np then
    raise exception 'RET-7 broken. Net Proceeds: shop % but products %', shop_np, prod_np;
  end if;
  if shop_rl <> prod_rl then
    raise exception 'RET-7 broken. Return Loss: shop % but products %', shop_rl, prod_rl;
  end if;
  raise notice 'RET-7 holds. Net Proceeds %, Return Loss %', shop_np, -shop_rl;
end $$;

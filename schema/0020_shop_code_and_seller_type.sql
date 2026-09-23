-- 0020. Two columns the contract serves and the table never had.
--
-- Found on 23 September 2026 by reading the contract's Shop schema against
-- information_schema.columns rather than against memory. Rule 1 of A13 says the service
-- implements the contract, so a field the contract declares and the table cannot hold is a
-- defect in the table.
--
-- THE GAP
--
-- The Shop schema declares eleven properties. The shops table held eight of them.
--
--     tiktok_shop_code        declared, absent
--     seller_type             declared, absent
--     authorization_expires_at declared, absent, and deliberately left absent. See below.
--
-- `/connections/tiktok/callback` in the contract states that the handler "stores the shop
-- id, cipher, region and seller type", and goes on to say that the region and the seller
-- type are not cosmetic, because a cross-border seller returns import VAT and customs
-- fields in place of `local_vat_amount`. The handler had nowhere to put the value it was
-- documented as storing. Had it been written before this migration, it would have read the
-- field from TikTok, used it to decide `accepted`, and then dropped it, so the reason a
-- shop was refused would not have survived the request that refused it.
--
-- `tiktok_shop_code` is the code shown in Seller Center. Adenola's GB shop is GBGBLCRKQTEX
-- and the sandbox shop recorded in A19 is IDLCFNWM88. It is display only, and it is not the
-- shop id. A seller reading a support message that names their shop id recognises nothing.
--
-- WHY NEITHER COLUMN CARRIES A CHECK CONSTRAINT
--
-- The contract gives seller_type an enum of LOCAL, CROSS_BORDER and null. One live call is
-- recorded in A19 and it returned LOCAL. CROSS_BORDER has never been observed here, and
-- whether TikTok emits a third value in some market is unknown.
--
-- A CHECK constraint on a value this project has seen once would turn an unexpected TikTok
-- response into a constraint violation partway through the callback, after the code has
-- been exchanged and the token written. The seller would be locked out by the row that was
-- meant to let them in, and the authorisation code is single use, so retrying means
-- starting again.
--
-- The contract already has the right answer to an unsupported seller. ConnectionResult
-- carries `accepted: false` with `rejection_reason: seller_type_unsupported`. So the column
-- stores whatever TikTok sent, verbatim, and the handler decides. An unrecognised value
-- produces a shop that is listed, holds its tokens, and produces no figures, which is what
-- the contract says should happen. `region` is unconstrained text for the same reason and
-- this keeps the two consistent.
--
-- This is the A25 lesson applied before the fault rather than after it. Authentication
-- asserted a documented value set, met a different one, and refused everything.
--
-- WHY authorization_expires_at IS NOT ADDED
--
-- The contract serves it, and `tiktok_connections.refresh_expires_at` looks like the same
-- instant. They may well be the same instant. Nobody here has checked, no real token has
-- ever been exchanged by this project, and writing a column on the strength of two field
-- names reading alike is the mistake rule 7 exists to stop.
--
-- It is left to the handler to derive, and the question is recorded as open: does TikTok's
-- UPCOMING_AUTHORIZATION_EXPIRATION event fire against the refresh token's expiry, or
-- against a separate authorisation lifetime? One real authorisation answers it. Until then
-- no column claims to know.

alter table shops add column if not exists tiktok_shop_code text;
alter table shops add column if not exists seller_type      text;

comment on column shops.tiktok_shop_code is
  'The code shown in Seller Center, for example GBGBLCRKQTEX. Display only. It is not '
  'tiktok_shop_id and it is not usable in an API call. It exists so that a seller reading '
  'a message about their shop recognises which shop it is.';

comment on column shops.seller_type is
  'TikTok''s own value, stored verbatim and deliberately unconstrained. The contract '
  'documents LOCAL and CROSS_BORDER; only LOCAL has been observed, in A19. A cross-border '
  'seller returns import VAT and customs fields in place of local_vat_amount, so this '
  'changes the finance mapping as much as region does. An unrecognised value must produce '
  'ConnectionResult.accepted = false with rejection_reason seller_type_unsupported, and '
  'must never produce figures.';

-- The connection row already exists and already encrypts. What it does not record is which
-- key encrypted it, beyond an integer that nothing resolves.
comment on column tiktok_connections.key_version is
  'Which encryption key produced the _enc columns on this row. The key register itself '
  'does not exist. It cannot be decided until the Python service has a host, because the '
  'host decides where a key can live and how it is rotated. Until that decision is taken, '
  'no code should write a value here and treat the number as meaningful. Recorded as open '
  'in CLAUDE.md rather than resolved by inventing a default.';

do $$
declare
  missing text;
begin
  select string_agg(needed, ', ' order by needed) into missing
    from unnest(array['tiktok_shop_code', 'seller_type']) as needed
   where not exists (
     select 1 from information_schema.columns
      where table_schema = 'public' and table_name = 'shops'
        and column_name = needed
   );

  if missing is not null then
    raise exception 'shops is still missing columns the contract serves: %', missing;
  end if;
end $$;

"""Ingest a real TikTok Seller Centre order export into MyShopEdge ledger entries.

Written 23 September 2026 against the first genuine British order,
`testdata/real_payloads/order_export_gb_2026-09-23.csv`. Everything here is derived from
that file's own column labels, not from the API and not from a generated fixture.

Why this exists. The settlement API needs a settled order, and a settled order needs the
return window to pass, which is calendar time nobody can shorten. The order export is
available the moment an order is paid. So the product's central claim, that what a seller
keeps is not what TikTok's headline says, can be proved today on real British money.

What the export cannot tell us, stated rather than guessed:
  the cost of goods       the seller's own figure, uploaded separately under A15.1
  TikTok's fees           these appear only at settlement, in fee_tax_breakdown
So this produces a partial ledger and labels it as partial. A figure presented as final when
it is missing every platform fee would be worse than no figure.

    python3 testdata/ingest_order_export.py [--cost-pence N]
"""

from __future__ import annotations

import argparse, csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(HERE, "real_payloads", "order_export_gb_2026-09-23.csv")


def money(cell: str) -> int:
    """'GBP 8.00' to 800. Minor units per rule 3, and GBP is asserted rather than assumed.

    The export writes the currency into every money cell, so it can be checked instead of
    taken on trust. A20.3 records why a currency-blind conversion is a defect.
    """
    cell = (cell or "").strip()
    if not cell:
        return 0
    parts = cell.split()
    if len(parts) != 2:
        raise ValueError(f"Unexpected money format: {cell!r}")
    code, amount = parts
    if code != "GBP":
        raise ValueError(f"This ingest is GBP only. Export carries {code}.")
    return int(round(float(amount) * 100))


def p(minor: int) -> str:
    return f"£{minor / 100:,.2f}"


# Export column -> ledger category. Every entry is a seller-side effect. A column that
# records what TikTok or the buyer paid is deliberately absent, because it is not the
# seller's money and posting it would overstate both sides of the ledger.
SELLER_EFFECT = {
    "SKU Subtotal Before Discount":  ("gross_sales",     +1),
    "SKU Seller Discount":           ("seller_discount", -1),
    # The one the headline hides. A21.3.
    "Shipping Fee Seller Discount":  ("seller_shipping", -1),
}

# Recorded, and never posted to the ledger. These are TikTok's money or the buyer's.
NOT_SELLER_MONEY = [
    "SKU Platform Discount",
    "Shipping Fee Platform Discount",
    "Shipping Fee After Discount",
    "Original Shipping Fee",
    "Order Amount",
    "Taxes",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-pence", type=int, default=None,
                    help="Cost of goods for the unit, in pence. Omitted means unknown.")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(EXPORT, newline="")))
    if not rows:
        print("No rows in the export.")
        return 1
    r = rows[0]

    print(f"order      {r['Order ID']}")
    print(f"product    {r['Product Name']}, {r['Variation']}, qty {r['Quantity']}")
    print(f"status     {r['Order Status']}, {r['Order Substatus']}")
    print(f"created    {r['Created Time']}\n")

    entries = []
    for column, (category, sign) in SELLER_EFFECT.items():
        amount = money(r[column]) * sign
        if amount:
            entries.append((category, column, amount))

    print("ledger entries derived from the export")
    for category, column, amount in entries:
        print(f"   {category:18} {p(amount):>10}   from {column}")
    if not entries:
        print("   none")

    print("\nnot posted, because it is not the seller's money")
    for column in NOT_SELLER_MONEY:
        print(f"   {column:34} {r[column].strip()}")

    revenue = sum(a for c, _, a in entries if a > 0)
    costs = sum(a for c, _, a in entries if a < 0)

    print("\nwhat the export can tell us")
    print(f"   revenue                        {p(revenue):>10}")
    print(f"   seller costs in this export    {p(costs):>10}")
    print(f"   subtotal                       {p(revenue + costs):>10}")

    if args.cost_pence is not None:
        print(f"   cost of goods                  {p(-args.cost_pence):>10}")
        print(f"   after cost of goods            {p(revenue + costs - args.cost_pence):>10}")
    else:
        print("   cost of goods                     unknown, not in the export")

    print("\n   TikTok fees                       unknown until settlement")
    print(f"\nThe seller sees Order Amount of {r['Order Amount'].strip()}. Before the cost of")
    print(f"goods and before a single TikTok fee, {p(-costs)} of that is already spent.")
    print("This figure is partial by construction and must be labelled so on any screen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

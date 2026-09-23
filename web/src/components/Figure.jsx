/**
 * How a money figure is rendered, everywhere.
 *
 * This component exists for one rule, and the rule is the reason the product is worth
 * anything: **a figure the system cannot compute must never render as a zero.**
 *
 * A4.1 and the products endpoint both take this seriously. `kept` comes back as null with
 * a `kept_reason` when a SKU has no cost, because the seller's profit on that product is
 * unknown, not nil. Rendering it as "£0.00" would be a lie with a currency symbol on it,
 * and it is the kind of lie a seller would act on.
 *
 * So an absent figure renders as an em-rule with the reason attached, in a muted colour,
 * and it is announced to a screen reader as the reason rather than as a dash.
 */

import { formatMoney } from "@/lib/api";

/**
 * @typedef {import("@/lib/api-types").components["schemas"]["Money"]} Money
 *
 * @param {{
 *   amount: Money | null | undefined,
 *   reason?: string | null,
 *   className?: string,
 * }} props
 */
export function Figure({ amount, reason, className = "" }) {
  if (amount == null) {
    const why = reason || "Not known yet";
    return (
      <span className={`money money--unknown ${className}`} title={why}>
        <span aria-hidden="true">—</span>
        <span className="visually-hidden">{why}</span>
      </span>
    );
  }

  const negative = amount.amount_minor < 0;
  return (
    <span className={`money ${negative ? "money--neg" : ""} ${className}`}>
      {formatMoney(amount)}
    </span>
  );
}

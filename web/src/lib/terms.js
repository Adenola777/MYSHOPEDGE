/**
 * The words the screens use, from the A8 terminology standard.
 *
 * These are copy, not rules. Every figure and every state they describe is computed by the
 * service (A29.1), and this file only names what the service returned. TC-CLR-06 forbids
 * the withdrawn labels "Their cut", "You keep", "Left after TikTok", "Contribution" and
 * "Return Loss" on any screen, so none of them appears here.
 */

/** The statement CLR-5 requires wherever gross profit after returns is shown. */
export const BEFORE_OVERHEADS = "This is before your own running costs and your tax.";

/** @type {Record<string, string>} */
export const HERO_LABEL = {
  gross_profit_after_returns: "Gross profit after returns",
  net_proceeds: "Net proceeds",
};

/*
 * Chip tones. A7.10 keeps red, amber and green for the three payment statuses and nothing
 * else, "so that red on this product always means money that has not arrived". Every other
 * state here is navy (`critical`, `strong`) or neutral (`quiet`), and the word carries the
 * meaning. Until 24 September these used the payment colours.
 */

/** @type {Record<string, [string, string]>} label and chip tone */
export const CONFIDENCE = {
  confirmed: ["Confirmed", "quiet"],
  estimated: ["Estimated", "strong"],
  incomplete: ["Incomplete", "strong"],
};

/** @type {Record<string, [string, string]>} */
export const FRESHNESS = {
  fresh: ["Up to date", "quiet"],
  getting_old: ["Getting old", "strong"],
  stale: ["Out of date", "critical"],
};

/** @type {Record<string, string>} */
export const AWAITING = {
  waiting_delivery: "Waiting for delivery",
  waiting_return_refund: "Waiting on a return or refund",
  delivered_awaiting_settlement: "Delivered, awaiting settlement",
};

/** @type {Record<string, [string, string]>} */
export const STOCK_STATE = {
  out: ["Out of stock", "critical"],
  low: ["Low", "strong"],
  coming_back: ["Returns in transit", "quiet"],
  healthy: ["Healthy", "quiet"],
};

/** A18.8 names movements in plain English rather than by their codes. */
/** @type {Record<string, string>} */
export const MOVEMENT = {
  sale_reserved: "Sold, not yet dispatched",
  posted: "Dispatched",
  cancelled: "Order cancelled, units back in stock",
  return_resellable: "Returned, back in stock",
  write_off: "Stock written off",
  manual_adjustment: "Adjusted by you",
  adjustment_absorbed: "Your adjustment absorbed by TikTok's count",
};

/** @type {Record<string, string>} */
export const DISCREPANCY_KIND = {
  product_code: "Product code differs",
  order_reference: "Order reference differs",
  transaction_reference: "Transaction reference differs",
  amount: "Amount differs",
  return_unmatched: "Return not matched to an order",
  duplicate: "Recorded twice",
  unmapped_fee: "Fee we do not recognise",
};

/** @type {Record<string, string>} */
export const RESOLUTION = {
  accepted_tiktok: "TikTok's value accepted",
  corrected_seller: "Your record corrected",
  explained: "Marked as explained",
};

/** @type {Record<string, string>} */
export const SEVERITY_TONE = { critical: "critical", warning: "strong", info: "quiet" };

/** @param {string} tone */
export function chipClass(tone) {
  return `chip chip--${tone}`;
}

/**
 * Why gross profit after returns is not shown. The contract serves a code on Money and
 * Today, `incomplete_costs` or `no_sales`, and the product ranking serves a sentence, so a
 * value that is not a known code is shown as it came.
 *
 * @param {string | null | undefined} reason
 */
export function keptReason(reason) {
  if (!reason) return null;
  return (
    {
      incomplete_costs: "Not every product has a cost price yet, so profit cannot be worked out.",
      no_sales: "Nothing sold in this period.",
    }[reason] ?? reason
  );
}

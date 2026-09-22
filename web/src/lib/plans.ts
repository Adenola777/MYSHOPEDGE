/**
 * The three plans, and the single place they are defined.
 *
 * A plan's price is never sent from the browser. The browser sends a slug, the server
 * looks the slug up here, and the server uses the Stripe price identifier held in an
 * environment variable. A client that posts a price identifier is ignored.
 *
 * Two lists exist on purpose. `features` holds what the product does today and is the only
 * list rendered on screen. `pendingScope` holds rows from the commercial price sheet that
 * the MVP does not yet have, recorded here so they are not forgotten and not advertised.
 * Nothing moves from the second list to the first until the feature exists and is tested.
 */

export type PlanSlug = "starter" | "growth" | "pro";

export interface Plan {
  slug: PlanSlug;
  name: string;
  strapline: string;
  /** Integer minor units. Rule 3 of the client contract. */
  priceMinor: number;
  currency: "GBP";
  /** Orders per calendar month included in the plan. */
  orderLimit: number;
  /** Months of history the first sync loads and the seller can open. */
  historyMonths: number;
  features: string[];
  highlight: boolean;
  /** Read at request time so a redeploy is not needed to correct a price. */
  priceEnvVar: string;
}

export const TRIAL_DAYS = 14;

export const PLANS: Record<PlanSlug, Plan> = {
  starter: {
    slug: "starter",
    name: "Starter",
    strapline: "Know your numbers.",
    priceMinor: 999,
    currency: "GBP",
    orderLimit: 100,
    historyMonths: 12,
    highlight: false,
    priceEnvVar: "STRIPE_PRICE_STARTER",
    features: [
      "One TikTok Shop connection",
      "Sales, fees and payouts, reconciled to every statement",
      "Refunds and returns, with the stock effect of each",
      "Product costs, uploaded or typed",
      "Gross profit after returns, calculated line by line",
      "Stock levels and what runs out first",
      "VAT threshold tracking and set-aside guidance",
    ],
  },
  growth: {
    slug: "growth",
    name: "Growth",
    strapline: "Understand your business.",
    priceMinor: 2499,
    currency: "GBP",
    orderLimit: 500,
    historyMonths: 12,
    highlight: true,
    priceEnvVar: "STRIPE_PRICE_GROWTH",
    features: [
      "Everything in Starter",
      "Up to 500 orders a month",
      "Profit by product and by variant",
      "Every transaction behind any figure",
      "Exports on a sales basis or a cash basis",
      "Priority support",
    ],
  },
  pro: {
    slug: "pro",
    name: "Pro",
    strapline: "Scale with confidence.",
    priceMinor: 4999,
    currency: "GBP",
    orderLimit: 2000,
    historyMonths: 12,
    highlight: false,
    priceEnvVar: "STRIPE_PRICE_PRO",
    features: [
      "Everything in Growth",
      "Up to 2,000 orders a month",
      "Scheduled exports",
      "Priority support",
    ],
  },
};

/**
 * Rows from the commercial price sheet of 22 September 2026 that the MVP does not have.
 * None of these is rendered. Each needs a specification, a schema change and a test before
 * it can be sold.
 */
export const pendingScope = [
  "Expense tracking. The product does not collect overheads, ruled in A8. There is no table, screen or endpoint.",
  "Multiple stores and channels. PRD 6.2 excludes multi-shop and A12.7 states the interface must not expose it.",
  "Historical data tiered at 3, 12 and 24 months. The first sync loads 12 and MON-5 requires every loaded month to open and reconcile.",
  "Profit and loss reporting. It appears nowhere in the specification pack.",
  "Order limits as an enforced quota. Nothing counts orders per month, so the limits above are a commitment rather than a control.",
  "Advanced analytics. Nothing is named, so nothing can be built or tested.",
];

export const PLAN_ORDER: PlanSlug[] = ["starter", "growth", "pro"];

export function isPlanSlug(value: unknown): value is PlanSlug {
  return typeof value === "string" && value in PLANS;
}

/** Formats an integer of minor units for display. The client never does arithmetic on it. */
export function formatPrice(plan: Plan): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: plan.currency,
    minimumFractionDigits: 2,
  }).format(plan.priceMinor / 100);
}

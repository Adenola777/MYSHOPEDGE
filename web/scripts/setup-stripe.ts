/**
 * Creates the three products and the three prices, from plans.ts.
 *
 * Run it once against a sandbox, then once against live when the prices are settled.
 *
 *   STRIPE_SECRET_KEY=sk_test_... npx tsx scripts/setup-stripe.ts
 *
 * It is idempotent. Each product and price carries a lookup key derived from the plan
 * slug, so running it twice finds what it created the first time rather than making a
 * duplicate. A price in Stripe cannot be edited once created, so changing an amount
 * creates a new price, archives the old one, and prints the new identifier.
 *
 * The secret key is read from the environment and is never written to a file or printed.
 * The output is the three environment variables to set in Vercel.
 */

import Stripe from "stripe";
import { PLANS, PLAN_ORDER, TRIAL_DAYS } from "../src/lib/plans";

const key = process.env.STRIPE_SECRET_KEY;
if (!key) {
  console.error("STRIPE_SECRET_KEY is not set.");
  process.exit(1);
}

const stripe = new Stripe(key, { apiVersion: "2025-02-24.acacia" });
const live = key.startsWith("sk_live_");

async function main() {
  if (live) {
    console.log("This key is a live key. Products and prices created here are real.");
    if (process.env.I_MEAN_LIVE !== "yes") {
      console.error("Refusing to write to a live account. Set I_MEAN_LIVE=yes to proceed.");
      process.exit(1);
    }
  }

  const results: Array<{ envVar: string; priceId: string; created: boolean }> = [];

  for (const slug of PLAN_ORDER) {
    const plan = PLANS[slug];
    const lookupKey = `myshopedge_${plan.slug}_gbp_monthly`;

    const product = await findOrCreateProduct(plan.slug, plan.name, plan.strapline);
    const { price, created } = await findOrCreatePrice(
      product.id,
      lookupKey,
      plan.priceMinor,
      plan.currency,
    );

    results.push({ envVar: plan.priceEnvVar, priceId: price.id, created });
    console.log(
      `${plan.name.padEnd(8)} ${product.id}  ${price.id}  ${created ? "created" : "existing"}`,
    );
  }

  console.log(`\nTrial length is ${TRIAL_DAYS} days and it is set on the subscription, not`);
  console.log("on the price, so it does not appear here.\n");
  console.log("Set these in Vercel, for the matching environment:\n");
  for (const r of results) {
    console.log(`${r.envVar}=${r.priceId}`);
  }
  console.log(
    "\nThe VAT treatment of these prices is not settled. Until it is, set tax_behavior",
  );
  console.log("on each price in the Dashboard, because it cannot be changed afterwards.");
}

async function findOrCreateProduct(slug: string, name: string, description: string) {
  const existing = await stripe.products.search({
    query: `metadata['plan']:'${slug}'`,
    limit: 1,
  });
  const found = existing.data[0];
  if (found) return found;

  return stripe.products.create({
    name: `MyShopEdge ${name}`,
    description,
    metadata: { plan: slug },
  });
}

async function findOrCreatePrice(
  productId: string,
  lookupKey: string,
  unitAmount: number,
  currency: string,
) {
  const existing = await stripe.prices.list({
    lookup_keys: [lookupKey],
    active: true,
    limit: 1,
  });
  const found = existing.data[0];

  if (found) {
    if (found.unit_amount === unitAmount && found.currency === currency.toLowerCase()) {
      return { price: found, created: false };
    }
    // The amount has changed. A Stripe price is immutable, so the old one is archived and
    // the new one claims the lookup key through transfer_lookup_key below. Existing
    // subscriptions keep the old price until they are explicitly migrated.
    await stripe.prices.update(found.id, { active: false });
  }

  const price = await stripe.prices.create({
    product: productId,
    currency: currency.toLowerCase(),
    unit_amount: unitAmount,
    recurring: { interval: "month" },
    lookup_key: lookupKey,
    transfer_lookup_key: true,
  });
  return { price, created: true };
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});

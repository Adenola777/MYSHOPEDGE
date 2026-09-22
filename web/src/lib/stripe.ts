/**
 * The server side Stripe client. Rule 5 of the client contract: the secret key is read
 * from the environment inside server code and never reaches a browser bundle.
 */
import Stripe from "stripe";

const key = process.env.STRIPE_SECRET_KEY;
if (!key) {
  throw new Error("STRIPE_SECRET_KEY is not set. Billing cannot start without it.");
}

export const stripe = new Stripe(key, {
  // Pinned deliberately. The version is tied to the SDK major, so upgrading the stripe
  // package is a decision about API behaviour and not only about dependencies.
  apiVersion: "2025-02-24.acacia",
  appInfo: { name: "MyShopEdge", url: "https://myshopedge.com" },
});

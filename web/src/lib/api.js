/**
 * The one way this application talks to the API.
 *
 * Rule 4 of A13: the web application has no privileged path. It reaches the database only
 * through this service, under the same authentication and the same row level security as
 * any other client.
 *
 * @typedef {import("./api-types").components["schemas"]} Schemas
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/**
 * @param {string} path
 * @param {RequestInit & { idempotencyKey?: string }} [init]
 * @returns {Promise<{ ok: boolean, status: number, data: any }>}
 */
export async function api(path, init = {}) {
  const { idempotencyKey, headers: given, ...rest } = init;
  /** @type {Record<string, string>} */
  const headers = { "content-type": "application/json" };
  if (given) Object.assign(headers, given);
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  const response = await fetch(`${BASE}${path}`, {
    ...rest,
    headers,
    credentials: "include",
  });

  const data = await response.json().catch(() => null);
  return { ok: response.ok, status: response.status, data };
}

/**
 * @typedef {Object} PlansPayload
 * @property {number} trial_days
 * @property {Schemas["Plan"][]} plans
 */

/**
 * The plans, served by the API rather than held here, so a price change does not require
 * a client release. Rule 2 of A13.
 *
 * @returns {Promise<PlansPayload | null>}
 */
export async function fetchPlans() {
  const { ok, data } = await api("/billing/plans", { cache: "no-store" });
  return ok ? data : null;
}

/**
 * Formats an integer of minor units. The client never does arithmetic on it.
 *
 * @param {Schemas["Money"]} amount
 * @returns {string}
 */
export function formatMoney(amount) {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: amount.currency ?? "GBP",
    minimumFractionDigits: 2,
  }).format(amount.amount_minor / 100);
}

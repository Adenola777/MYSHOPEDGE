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
  const { idempotencyKey, headers: given, timeoutMs = 15000, ...rest } = init;
  /** @type {Record<string, string>} */
  const headers = { "content-type": "application/json" };
  if (given) Object.assign(headers, given);
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  // A network failure must become a result, not an exception.
  //
  // Until 23 September this awaited fetch() with nothing around it. fetch() rejects when
  // the service is unreachable, so with the API down every screen threw and rendered a
  // 500 instead of the error state it had been given. Proved by starting the built
  // application with no API running: /billing returned 500 while its own "we cannot show
  // the plans right now" branch sat unreachable in the same file.
  //
  // status 0 means the request never got an answer. Callers distinguish it from a 4xx or
  // 5xx, because "we could not reach us" and "we said no" are different things to tell a
  // seller.
  const timer = AbortSignal.timeout ? AbortSignal.timeout(timeoutMs) : undefined;

  /** @type {Response} */
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...rest,
      headers,
      credentials: "include",
      signal: rest.signal ?? timer,
    });
  } catch (/** @type {any} */ cause) {
    return {
      ok: false,
      status: 0,
      data: null,
      unreachable: true,
      reason: cause?.name === "TimeoutError" ? "timeout" : "network",
    };
  }

  const data = await response.json().catch(() => null);
  return { ok: response.ok, status: response.status, data, unreachable: false };
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

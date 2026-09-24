/**
 * The one way this application talks to the API.
 *
 * Rule 4 of A13: the web application has no privileged path. It reaches the database only
 * through this service, under the same authentication and the same row level security as
 * any other client.
 *
 * @typedef {import("./api-types").components["schemas"]} Schemas
 */

import { authorizationHeader } from "./stack";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/**
 * @typedef {Object} ApiResult
 * @property {boolean} ok
 * @property {number} status  0 when the request never reached the service.
 * @property {any} data
 * @property {boolean} [unreachable]  True when the service could not be reached at all.
 * @property {"timeout" | "network"} [reason]  Why, when unreachable.
 */

/**
 * @param {string} path
 * @param {RequestInit & { idempotencyKey?: string, timeoutMs?: number }} [init]
 * @returns {Promise<ApiResult>}
 */
export async function api(path, init = {}) {
  const { idempotencyKey, headers: given, timeoutMs = 15000, ...rest } = init;
  /** @type {Record<string, string>} */
  const headers = { "content-type": "application/json" };
  // Every shop route requires a bearer token, and until 24 September no request carried
  // one. The token is read here, on whichever side the request is made, so no screen can
  // forget it. A caller that passes its own Authorization header keeps it.
  const authorization = await authorizationHeader();
  if (authorization) headers.Authorization = authorization;
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
 * The product ranking for one shop.
 *
 * Returns the whole result rather than just the data, because the screen has to tell a
 * seller the difference between "we could not reach us", "you are signed out" and "this
 * shop is not yours". Collapsing those into null would make all three look like an empty
 * shop, which is the one reading that is never true.
 *
 * @param {string} shopId
 * @param {{ measure?: string, from?: string, to?: string }} [query]
 */
export async function fetchProducts(shopId, query = {}) {
  const qs = new URLSearchParams(
    Object.entries(query).filter(([, v]) => v !== undefined && v !== ""),
  ).toString();
  return api(`/shops/${encodeURIComponent(shopId)}/products${qs ? `?${qs}` : ""}`, {
    cache: "no-store",
  });
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

/**
 * Any reading endpoint under one shop, returning the whole result for the reason given on
 * `fetchProducts`. Empty query values are dropped rather than sent as blanks.
 *
 * @param {string} shopId
 * @param {string} path  The part after `/shops/{shopId}`, starting with a slash.
 * @param {Record<string, string | undefined>} [query]
 */
export async function fetchShop(shopId, path, query = {}) {
  const qs = new URLSearchParams(
    /** @type {[string, string][]} */ (
      Object.entries(query).filter(([, v]) => v !== undefined && v !== "")
    ),
  ).toString();
  return api(`/shops/${encodeURIComponent(shopId)}${path}${qs ? `?${qs}` : ""}`, {
    cache: "no-store",
  });
}

/**
 * Dates are shown in Europe/London, the business date A29.9 fixes, whatever the server's
 * own zone. This is formatting only. The date itself comes from the API.
 *
 * @param {string | null | undefined} iso
 * @param {{ time?: boolean }} [opts]
 */
export function formatDate(iso, opts = {}) {
  if (!iso) return "";
  // A bare date such as 2026-08-01 is a calendar day, not an instant, so it is read at
  // noon UTC to keep it on the same day in London.
  const value = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T12:00:00Z` : iso;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(opts.time ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(new Date(value));
}

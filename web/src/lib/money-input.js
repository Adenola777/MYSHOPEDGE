/**
 * Reads an amount a seller typed, such as "3.40" or "£1,234.5", into integer pence.
 *
 * This is input parsing, not a financial rule, and it never passes through a binary float
 * (A13 rule 3, A29.13). The digits are read as text: pounds, then at most two decimals.
 * Anything else returns null, and the form says so rather than guessing.
 *
 * @param {string} text
 * @returns {number | null}
 */
export function parsePounds(text) {
  const t = text.trim().replace(/^£\s*/, "").replace(/,/g, "");
  const m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(t);
  if (!m) return null;
  const pence = (m[2] ?? "").padEnd(2, "0");
  return Number(m[1]) * 100 + Number(pence);
}

/** A short key for an Idempotency-Key header, fresh for each attempt at an action. */
export function newKey() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

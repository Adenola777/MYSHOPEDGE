/**
 * The states a screen shows when the API does not give it figures.
 *
 * Every reading screen distinguishes four outcomes, because each tells the seller something
 * different: the service could not be reached, the session ended, the shop or record is not
 * theirs, or the service answered with an error. Rendering any of them as an empty list
 * would tell a seller their shop is empty, which is the one reading that is never true.
 *
 * The wording states only what is known. On 24 September two screens were found claiming
 * "your data is safe" when nothing had checked it, so no message here makes a claim about
 * the seller's data.
 */

/**
 * @param {import("@/lib/api").ApiResult} result
 * @param {{ what: string, notFound?: string }} copy
 *   `what` names what failed to load, such as "your stock". `notFound` replaces the 404
 *   wording where the missing thing is a record rather than the shop.
 * @returns {React.ReactElement | null}  Null when the result is usable.
 */
export function apiProblem(result, { what, notFound }) {
  if (result.unreachable) {
    return (
      <Problem
        title="MyShopEdge could not be reached."
        note={
          result.reason === "timeout"
            ? `The request for ${what} took too long, so nothing is shown rather than part of it.`
            : `The request for ${what} did not reach MyShopEdge. Try again in a moment.`
        }
        retry
      />
    );
  }
  if (result.status === 401) {
    return (
      <Problem
        title="Please sign in again."
        note="Your session has ended. Signing in again brings you back here."
      />
    );
  }
  if (result.status === 403) {
    return (
      <Problem
        title="That shop is not on your account."
        note="Check the address, or pick a shop from your connections."
      />
    );
  }
  if (result.status === 404) {
    return (
      <Problem
        title={notFound ?? "That shop is not on your account."}
        note="Check the address and try again."
      />
    );
  }
  if (!result.ok || !result.data) {
    return (
      <Problem
        title={`${what.charAt(0).toUpperCase()}${what.slice(1)} could not be loaded.`}
        note="MyShopEdge answered with an error, so no figures are shown rather than wrong ones. Try again in a moment."
        retry
      />
    );
  }
  return null;
}

/** @param {{ title: string, note: string, retry?: boolean }} props */
export function Problem({ title, note, retry }) {
  return (
    <section className="state">
      <h1>{title}</h1>
      <p>{note}</p>
      {retry && (
        <p>
          <a className="btn btn--quiet" href="">
            Try again
          </a>
        </p>
      )}
    </section>
  );
}

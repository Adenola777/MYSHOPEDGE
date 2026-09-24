/**
 * The one Stack Auth client this application holds.
 *
 * What was read, 24 September 2026, from `@stackframe/stack` 2.8.108 itself rather than from
 * its documentation:
 *
 * - `getDefaultProjectId` throws when neither `NEXT_PUBLIC_STACK_PROJECT_ID` nor
 *   `STACK_PROJECT_ID` is set. The project id is the only value it demands.
 * - `getDefaultPublishableClientKey` returns `NEXT_PUBLIC_STACK_PUBLISHABLE_CLIENT_KEY` and
 *   throws nothing when it is absent. Whether this project's Stack configuration requires one
 *   could not be read, because the container that wrote this cannot reach
 *   api.stack-auth.com. It is set on Vercel regardless.
 * - `STACK_SECRET_SERVER_KEY` is demanded only by `StackServerApp`. This application uses
 *   `StackClientApp` on both sides, so no Stack secret lives on Vercel.
 * - With `tokenStore: "nextjs-cookie"`, the client app reads the browser's cookies in the
 *   browser and the request's cookies through `next/headers` on the server. One object
 *   therefore serves server components and client components alike.
 * - `getAuthJson()` returns `accessToken` as the raw token string (`tokens.accessToken.token`).
 *   `getAuthorizationHeader()` does not: it returns `Bearer stackauth_<base64 JSON>`, which
 *   the service would refuse, because `auth.py` verifies a bare ES256 JWT.
 *
 * When the project id is not set, as in CI and in a local build, `stackApp` is null and
 * every page that needs a seller says that sign-in is not configured. Constructing the app
 * without a project id would throw at import and break the whole build.
 *
 * **Unverified until a real sign-in.** No token from this project has passed through this
 * code yet. The first seller to sign in on the live site is its test.
 */

import { StackClientApp } from "@stackframe/stack";

export const STACK_CONFIGURED = Boolean(process.env.NEXT_PUBLIC_STACK_PROJECT_ID);

export const stackApp = STACK_CONFIGURED
  ? new StackClientApp({
      tokenStore: "nextjs-cookie",
      urls: {
        afterSignIn: "/shops",
        afterSignUp: "/shops",
        afterSignOut: "/start",
        home: "/",
      },
    })
  : null;

/**
 * The value for the Authorization header, or null when nobody is signed in.
 *
 * A failure to read the session is treated as signed out rather than thrown, so that a
 * screen shows its signed out state instead of a 500.
 *
 * @returns {Promise<string | null>}
 */
export async function authorizationHeader() {
  if (!stackApp) return null;
  try {
    const { accessToken } = await stackApp.getAuthJson();
    return accessToken ? `Bearer ${accessToken}` : null;
  } catch {
    return null;
  }
}

/**
 * The signed in user, or null.
 *
 * @returns {Promise<import("@stackframe/stack").CurrentUser | null>}
 */
export async function currentUser() {
  if (!stackApp) return null;
  try {
    return await stackApp.getUser();
  } catch {
    return null;
  }
}

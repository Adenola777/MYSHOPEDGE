/**
 * Every shop screen needs a signed in seller. A visitor who is not signed in is sent to S17
 * Start rather than shown a screen of errors.
 *
 * This is a convenience, not the protection. The service refuses any shop request without a
 * valid token, and that refusal is what keeps one seller out of another's figures. When
 * sign-in is not configured this passes through, and each screen shows its signed out state.
 */

import { redirect } from "next/navigation";
import { STACK_CONFIGURED, currentUser } from "@/lib/stack";

export const dynamic = "force-dynamic";

/** @param {{ children: React.ReactNode }} props */
export default async function ShopsLayout({ children }) {
  if (STACK_CONFIGURED && !(await currentUser())) redirect("/start");
  return children;
}

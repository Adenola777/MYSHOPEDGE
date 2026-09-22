/**
 * Resolves the signed-in account from the request.
 *
 * Neon Auth on Stack Auth issues the session. accounts.auth_subject holds the provider
 * subject and the account_identity view in migration 0011 joins the two. This module is a
 * placeholder with the correct shape: the session flow has not been written yet, and the
 * billing route is written against this interface so that it does not need changing when
 * it is.
 */
import type { NextRequest } from "next/server";

export interface Account {
  id: string;
  email: string;
  name: string | null;
}

export async function requireAccount(_request: NextRequest): Promise<Account | null> {
  throw new Error(
    "The authentication session flow has not been written. See A13 and the open items in the README.",
  );
}

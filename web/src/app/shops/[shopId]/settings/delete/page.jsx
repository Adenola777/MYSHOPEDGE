/** S30 Delete my account, bound to deleteMe (ACC-4). */

import { api } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { DeleteAccountForm } from "@/components/SettingsForms";

export const metadata = { title: "Delete my account" };

export default async function DeleteAccountPage() {
  const result = await api("/me", { cache: "no-store" });
  const problem = apiProblem(result, { what: "your account" });
  if (problem) return problem;

  return (
    <section data-testid="delete-account-screen">
      <header className="page-head">
        <h1>Delete my account</h1>
        <p>This closes your account for good. Take a copy of anything you need first.</p>
      </header>
      <DeleteAccountForm email={result.data.email} />
    </section>
  );
}

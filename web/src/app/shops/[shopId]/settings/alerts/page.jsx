/** S27 Alert settings, bound to getAlertSettings and putAlertSettings (STK-3, STK-8). */

import { fetchShop } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { AlertSettingsForm } from "@/components/SettingsForms";

export const metadata = { title: "Alert settings" };

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function AlertSettingsPage({ params }) {
  const { shopId } = await params;
  const result = await fetchShop(shopId, "/alert-settings");
  const problem = apiProblem(result, { what: "your alert settings" });
  if (problem) return problem;

  return (
    <section data-testid="alert-settings-screen">
      <header className="page-head">
        <h1>Alert settings</h1>
        <p>These thresholds decide when a variant is low, coming back or raised as a discrepancy.</p>
      </header>
      <AlertSettingsForm shopId={shopId} initial={result.data} />
    </section>
  );
}

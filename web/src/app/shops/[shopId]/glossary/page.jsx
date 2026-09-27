/**
 * S32 Glossary, from the shared reference rules (TAX-6). It renders whatever `listRules`
 * returns, each term carrying the date its rule was last reviewed and its source, so a
 * seller can see the figure is current rather than trusting it.
 */

import { api, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";

export const metadata = { title: "Glossary" };

/** @type {Record<string, string>} */
const SET_LABEL = {
  vat: "VAT",
  income_tax: "Income tax and Self Assessment",
  national_insurance: "National Insurance",
  mtd: "Making Tax Digital",
};

function describe(value) {
  if (value && typeof value === "object") {
    if (value.label) return value.label;
    if (value.amount_minor != null) {
      return new Intl.NumberFormat("en-GB", { style: "currency", currency: value.currency ?? "GBP" })
        .format(value.amount_minor / 100);
    }
  }
  return String(value ?? "");
}

export default async function GlossaryPage() {
  const result = await api("/rules", { cache: "no-store" });
  const problem = apiProblem(result, { what: "the glossary" });
  if (problem) return problem;

  /** @type {import("@/lib/api-types").components["schemas"]["ReferenceRule"][]} */
  const rules = result.data.rules ?? [];
  /** @type {Record<string, typeof rules>} */
  const grouped = {};
  for (const r of rules) (grouped[r.rule_set] ??= []).push(r);

  return (
    <section data-testid="glossary-screen">
      <header className="page-head">
        <h1>Glossary</h1>
        <p>The rules MyShopEdge uses, with the date each was last checked against its source.</p>
      </header>
      {rules.length === 0 ? (
        <section className="state">
          <h2>No rules are loaded yet.</h2>
          <p>Reference rules appear here once they are configured.</p>
        </section>
      ) : (
        <div className="stack">
          {Object.entries(grouped).map(([set, items]) => (
            <div className="card" key={set}>
              <h2>{SET_LABEL[set] ?? set}</h2>
              <ul className="rows">
                {items.map((r) => (
                  <li key={`${r.rule_set}-${r.rule_key}-${r.effective_from}`}>
                    <span>
                      {r.rule_key}
                      <div className="rows__sub">
                        {[describe(r.value),
                          `from ${formatDate(r.effective_from)}`,
                          r.reviewed_at ? `reviewed ${formatDate(r.reviewed_at)}` : null,
                        ].filter(Boolean).join(". ")}
                        {r.source_url && (
                          <> · <a href={r.source_url} target="_blank" rel="noreferrer">source</a></>
                        )}
                      </div>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

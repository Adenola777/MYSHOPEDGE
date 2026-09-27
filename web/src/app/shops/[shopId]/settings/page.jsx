/**
 * S15 Settings and data. The hub that reaches disconnect, delete, download, alert settings
 * and the glossary. It reads nothing of its own; each link opens a screen that does.
 */

import Link from "next/link";

export const metadata = { title: "Settings and data" };

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function SettingsPage({ params }) {
  const { shopId } = await params;
  const base = `/shops/${shopId}`;
  const links = [
    [`${base}/settings/alerts`, "Alert settings", "Low-stock, coming-back and absorption thresholds."],
    [`${base}/costs`, "Product costs", "Upload a spreadsheet of costs, or add them by hand."],
    [`${base}/other-sales`, "Other-channel sales", "Enter sales from outside TikTok so the VAT monitor sees your whole turnover."],
    [`${base}/export`, "Export figures", "Build a spreadsheet of your figures for your accountant."],
    [`${base}/sync`, "Sync status", "See what MyShopEdge has brought in from TikTok."],
    [`${base}/glossary`, "Glossary", "Plain definitions of the tax and finance terms MyShopEdge uses."],
    [`${base}/settings/export`, "Download my data", "Prepare a full archive of everything held about your account."],
    [`${base}/settings/disconnect`, "Disconnect this shop", "Stop reading from TikTok. Your records stay."],
    [`${base}/settings/delete`, "Delete my account", "Close your account. Your ledger is kept as a record."],
  ];
  return (
    <section data-testid="settings-page">
      <header className="page-head">
        <h1>Settings and data</h1>
        <p>Manage your shop connection, your thresholds and your data.</p>
      </header>
      <div className="card">
        <ul className="rows">
          {links.map(([href, title, why]) => (
            <li key={href}>
              <span>
                <Link href={href} data-testid={`settings-link-${title.toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "")}`}>{title}</Link>
                <div className="rows__sub">{why}</div>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

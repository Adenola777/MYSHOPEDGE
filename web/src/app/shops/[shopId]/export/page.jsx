/** S23 Export, bound to createExport and getExport (MON-2). */

import { ExportForm } from "@/components/ExportForm";

export const metadata = { title: "Export" };

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function ExportScreen({ params }) {
  const { shopId } = await params;
  return (
    <section data-testid="export-figures-screen">
      <header className="page-head">
        <h1>Export</h1>
        <p>Build a spreadsheet of your figures to hand to your accountant.</p>
      </header>
      <div className="card">
        <p className="card__why">
          Pick a period and a basis. The basis matters: the same period is a different figure
          on a sales basis and a cash basis, and a file that does not say which cannot be used.
        </p>
      </div>
      <ExportForm shopId={shopId} />
    </section>
  );
}

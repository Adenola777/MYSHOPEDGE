/** S31 Download my data, bound to requestAccountExport (ACC-4). */

import { ExportAction } from "@/components/SettingsForms";

export const metadata = { title: "Download my data" };

export default async function ExportPage() {
  return (
    <section data-testid="export-screen">
      <header className="page-head">
        <h1>Download my data</h1>
        <p>We prepare a single archive of everything held about your account.</p>
      </header>
      <div className="card">
        <p className="card__why">
          Preparing the file can take a little while. When it is ready you can download it
          from this screen, and the link stays valid for a short time.
        </p>
        <ExportAction />
      </div>
    </section>
  );
}

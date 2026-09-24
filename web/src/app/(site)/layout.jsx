/**
 * Screens outside a shop: Start, sign-in, billing and the TikTok return page. They carry
 * the top bar with the logo only, because there is no shop to be up to date or to notify.
 */

import { AppBar } from "@/components/AppBar";

/** @param {{ children: React.ReactNode }} props */
export default function SiteLayout({ children }) {
  return (
    <>
      <AppBar />
      <main id="main" className="content">{children}</main>
    </>
  );
}

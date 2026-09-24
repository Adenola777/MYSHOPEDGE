/**
 * `/shops`, the list of a seller's shops and S1 Connect TikTok Shop while there is none.
 * It sits in a route group so it can carry the plain top bar while the shop screens beside
 * it carry the Updated stamp, the bell and the tabs. The address is unchanged.
 */

import { AppBar } from "@/components/AppBar";

/** @param {{ children: React.ReactNode }} props */
export default function ShopListLayout({ children }) {
  return (
    <>
      <AppBar />
      <main id="main" className="content">{children}</main>
    </>
  );
}

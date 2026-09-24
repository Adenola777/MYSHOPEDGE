/**
 * The root layout: the document, the fonts, the icons, sign-in, and the footer.
 *
 * The top bar is not drawn here. Inside a shop it carries the Updated stamp and the bell,
 * which need the shop, so each area draws its own: `(site)/layout.jsx` and
 * `shops/(list)/layout.jsx` without them, `shops/[shopId]/layout.jsx` with them.
 *
 * Until 24 September this layout drew its own line icon, set "MyShopEdge" in a font and set
 * "Know Your Numbers." beside it with a full stop. A7.6 forbids all three. The logo now
 * comes from `brand/`, and the icons and manifest are the ones A7.3 built
 * (`brand/head-snippet.html`).
 *
 * Fonts, WFW 1.1: Plus Jakarta Sans for text and Archivo for figures, self-hosted from the
 * @fontsource packages, so no request leaves for a font service.
 */

import "@fontsource-variable/plus-jakarta-sans";
import "@fontsource-variable/archivo";
import "./globals.css";
import { StackProvider, StackTheme } from "@stackframe/stack";
import { stackApp } from "@/lib/stack";

export const metadata = {
  title: {
    default: "MyShopEdge",
    template: "%s | MyShopEdge",
  },
  description:
    "Bookkeeping and finance for UK TikTok Shop sellers. See what you actually earned, " +
    "not what the platform paid out.",
  applicationName: "MyShopEdge",
  manifest: "/site.webmanifest",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "16x16 32x32 48x48" },
      { url: "/icons/mse-favicon.svg", type: "image/svg+xml" },
    ],
    apple: "/icons/apple-touch-icon-180.png",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#C4400C",
};

/**
 * @param {{ children: React.ReactNode }} props
 */
export default function RootLayout({ children }) {
  const page = (
    <div className="shell">
      {children}
      <footer className="footer">
        <div className="footer__inner">
          <p>
            MyShopEdge is operated by Inspirecraft Global Limited, Leicester. Figures are drawn
            from your own shop data and are not financial advice.
          </p>
        </div>
      </footer>
    </div>
  );

  return (
    <html lang="en-GB">
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        {/* StackTheme is required, not decoration: in 2.8.108 it renders the TooltipProvider
            that Stack's sign-in form needs. Without it the live sign-up page crashed on
            24 September. The provider is left out when sign-in is not configured. */}
        {stackApp ? (
          <StackProvider app={stackApp}>
            <StackTheme>{page}</StackTheme>
          </StackProvider>
        ) : (
          page
        )}
      </body>
    </html>
  );
}

/**
 * The root layout.
 *
 * Written 23 September 2026. Until then the application did not build at all: the App
 * Router requires a root layout and there was none, so `next build` failed with
 * "(onboarding)/billing/page.jsx doesn't have a root layout". Two pages existed and
 * neither had ever rendered. Nothing in the project said so, which is why running the
 * build rather than reading the tree is the rule.
 *
 * The mark is drawn here rather than loaded as a file, so it inherits colour, scales with
 * the text, and costs no request. It is a rising edge, which is the one thing the product
 * is for.
 */

import "./globals.css";

export const metadata = {
  title: {
    default: "MyShopEdge",
    template: "%s | MyShopEdge",
  },
  description:
    "Bookkeeping and finance for UK TikTok Shop sellers. See what you actually earned, " +
    "not what the platform paid out.",
  applicationName: "MyShopEdge",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f2700f",
};

/**
 * @param {{ children: React.ReactNode }} props
 */
export default function RootLayout({ children }) {
  return (
    <html lang="en-GB">
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>

        <div className="shell">
          <header className="masthead">
            <div className="masthead__inner">
              <a className="wordmark" href="/">
                <svg
                  width="26"
                  height="26"
                  viewBox="0 0 26 26"
                  fill="none"
                  aria-hidden="true"
                  focusable="false"
                >
                  <rect width="26" height="26" rx="7" fill="currentColor" opacity="0.08" />
                  <path
                    d="M6 17.5L10.5 12.5L14 15.5L20 8"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <circle cx="20" cy="8" r="2.4" fill="currentColor" />
                </svg>
                <span>
                  MyShop<span className="wordmark__edge">Edge</span>
                </span>
              </a>
              <p className="tagline">Know Your Numbers.</p>
            </div>
          </header>

          <main id="main" className="content">
            {children}
          </main>

          <footer className="footer">
            <div className="footer__inner">
              <p>
                MyShopEdge is operated by Inspirecraft Global Limited, Leicester. Figures
                are drawn from your own shop data and are not financial advice.
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}

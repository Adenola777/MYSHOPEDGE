"use client";

/**
 * The shop's tabs (WFW 1.1): at the bottom on a phone, a left rail on a larger screen
 * (WFW 7). The wireframes carry five: Today, Stock, Products, Money and Tax. Tax is left
 * out, because VAT is out of scope (A29.8) and a tab to a screen that does not exist is a
 * promise the product cannot keep.
 *
 * The icons are simple line drawings, so each tab is named by its word and the icon only
 * helps the eye find it.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

/** @type {Record<string, React.ReactElement>} */
const ICON = {
  today: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3.5" y="4.5" width="17" height="16" rx="2.5" />
      <path d="M3.5 9.5h17M8 2.5v4M16 2.5v4" />
    </svg>
  ),
  stock: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5z" />
      <path d="M3.5 7.5 12 12l8.5-4.5M12 12v9" />
    </svg>
  ),
  products: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 12.5V4.5A1.5 1.5 0 0 1 4.5 3h8l8.5 8.5-9.5 9.5z" />
      <circle cx="8" cy="8" r="1.6" />
    </svg>
  ),
  money: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M16.5 6.5a4 4 0 0 0-7 2.5v9.5M7 18.5h10M7 13h7" />
    </svg>
  ),
};

/** @type {[string, string][]} */
const TABS = [
  ["today", "Today"],
  ["stock", "Stock"],
  ["products", "Products"],
  ["money", "Money"],
];

/** @param {{ shopId: string }} props */
export function ShopNav({ shopId }) {
  const path = usePathname() ?? "";
  const base = `/shops/${shopId}`;
  return (
    <nav className="tabs" aria-label="Your shop">
      {TABS.map(([slug, label]) => {
        const href = `${base}/${slug}`;
        const current = path === href || path.startsWith(`${href}/`)
          // Records and discrepancies are opened from Money and Today, so they keep their tab lit.
          || (slug === "money" && path.startsWith(`${base}/records`))
          || (slug === "today" && (path.startsWith(`${base}/discrepancies`) || path.startsWith(`${base}/notifications`)));
        return (
          <Link key={slug} href={href} aria-current={current ? "page" : undefined}>
            {ICON[slug]}
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

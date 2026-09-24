"use client";

/**
 * The shop's own navigation. The wireframes carry five tabs: Today, Stock, Products, Money
 * and Tax. Tax is not built, and a tab to a screen that does not exist is a promise the
 * product cannot keep, so it is left out until it is.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

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
    <nav className="shopnav" aria-label="Your shop">
      {TABS.map(([slug, label]) => {
        const href = `${base}/${slug}`;
        const current = path === href || path.startsWith(`${href}/`);
        return (
          <Link key={slug} href={href} aria-current={current ? "page" : undefined}>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

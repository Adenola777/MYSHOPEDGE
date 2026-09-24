// Next's own rules, including React hooks and accessibility checks. Added 24 September 2026
// so CI lints the front end (A29, master skill section 34).
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

export default [
  { ignores: [".next/**", "node_modules/**", "src/lib/api-types.d.ts"] },
  ...compat.extends("next/core-web-vitals"),
];

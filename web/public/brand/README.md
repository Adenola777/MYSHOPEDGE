# Copies of the brand files the web application serves

The source is `brand/` at the repository root, regenerated from the master by
`brand/build_brand.py` (A7.3). These files are copies, byte for byte, placed where Next.js
serves them. If the artwork changes, rebuild `brand/` and copy again; do not edit here.

| Served at | Copied from |
|---|---|
| `/favicon.ico` | `brand/raster/favicon.ico` |
| `/icons/*` | `brand/raster/` and `brand/mse-favicon.svg` |
| `/site.webmanifest` | `brand/site.webmanifest` |
| `/brand/*.svg` | `brand/` |

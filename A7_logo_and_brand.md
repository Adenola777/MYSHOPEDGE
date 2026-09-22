# Action 7: Logo integration

Closes audit question 4. You supplied a vector master, so this is a derivation from your artwork rather than a redraw. The geometry below is copied verbatim from your file. What changes is structure, colour discipline and the set of files.

---

## 7.1 What the master contains, and what it cannot do yet

Your file holds the mark as vector paths, the wordmark and the tagline as outlines rather than live text, and a three-stop gradient. That is a good starting point: no font is needed to render it, and it scales without loss.

Six things stop it being a production asset set. Each was measured rather than assumed.

| Finding | Detail |
|---|---|
| A white background is painted in | A `<rect>` of `#FFFFFF` fills the whole 2048 canvas. Placed on anything other than white, the logo arrives in a white box. |
| The square file is the horizontal lockup in a square | Artwork occupies 1639 of 2048 units across and 316 down, so about 15% of the height. At 32 px that is an illegible smear. The audit said this of the PNG; the vector has the same shape. |
| The inner shapes are painted white, not knocked out | The diagonal and the four bars are white fills at 0.96 opacity. They are invisible only on a white page. On any other background they appear as white shapes, and a single-colour version is impossible. |
| The mark sits 71 units below the text | Mark centre is at y 899, text block centre at y 827.5. On a page the mark reads as sitting low against the wordmark. |
| Two near-blacks | The wordmark is `#111820` and the tagline is `#16202a`. They differ by a shade nobody chose. |
| The arrow is orange on orange | The rising arrow is the idea of the mark, and it is drawn in the same gradient as the bag it sits on. It shows only where it crosses a white bar, and below roughly 48 px it disappears entirely. |

The last one is a design judgement rather than a defect, so it is handled by adding a variant rather than by changing your artwork. See 7.4.

---

## 7.2 The structural change

The inner shapes are now **knocked out with a mask** instead of painted white.

```
mask = white rectangle over the mark bounds
     − the diagonal wedge
     − the four bars
     − a 34-unit gap around the handle
```

The bag is then filled once, through that mask, in whatever colour is wanted. Three things follow.

1. The mark works on any background, because the inner shapes are transparent rather than white.
2. A reversed version is the same file with the fill set to white. A single-colour version is the same file with the fill set to navy. Nothing is redrawn.
3. `mse-mark-currentcolor.svg` inherits the surrounding text colour, so the mark can be dropped into a button or a heading and take that colour automatically.

The gradient is renamed from `orange` to `mseOrange`, because two logos on one page with a gradient both called `orange` collide and one of them loses its fill. The reference inside the wordmark follows the rename. This is not theoretical: it happened during the build, and "Edge" disappeared until it was fixed.

---

## 7.3 The asset set

Thirteen vector files, eleven rasters, a manifest and a head snippet.

### Lockups

| File | Use |
|---|---|
| `mse-logo-horizontal.svg` | The default. Mark, wordmark, tagline, transparent, optically aligned. |
| `mse-logo-horizontal-reversed.svg` | On navy, on photography, on any dark surface. All white, no gradient. |
| `mse-logo-horizontal-mono.svg` | One colour, for a stamp, an embossing, a single-colour print job. |
| `mse-logo-horizontal-notagline.svg` | Below 180 px wide, where the tagline stops being readable. |
| `mse-logo-stacked.svg` | A narrow column, a square-ish space, a social avatar with room for text. |

### The mark alone

| File | Use |
|---|---|
| `mse-mark-colour.svg` | The gradient mark, transparent. |
| `mse-mark-solid.svg` | Flat `#C4400C`, for anything that must meet a contrast requirement. |
| `mse-mark-reversed.svg` | White, for dark surfaces. |
| `mse-mark-navy.svg` | Single colour. |
| `mse-mark-currentcolor.svg` | Inherits the surrounding text colour. |
| `mse-mark-small.svg` | Below 48 px. Simplified: the diagonal is dropped and the arrow is white. |

### Icons

| File | Use |
|---|---|
| `mse-icon.svg` | Square app icon. The mark fills 76% of the canvas, centred. |
| `mse-icon-maskable.svg` | Android maskable. The mark shrinks to 58% and sits on a solid `#C4400C` field, so a circular crop takes nothing off it. |
| `mse-favicon.svg` | Browser tab. Simplified as above. |
| `raster/favicon.ico` | 16, 32 and 48 px in one file, for older browsers. |
| `raster/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon-180.png` | Web app install and iOS home screen. |
| `raster/logo-horizontal-1200.png`, `logo-horizontal-reversed-1200.png`, `mark-512.png` | Anywhere that will not take an SVG, such as an email template or a marketplace listing. |

`site.webmanifest` and `head-snippet.html` are ready to drop in. `build_brand.py` regenerates every file from the master, so a change to the artwork does not mean redoing this by hand.

---

## 7.4 The arrow, and a decision for you

In the master the arrow is drawn in the brand gradient on top of a bag filled with the same gradient. It is visible only where it crosses a white bar. At the size it appears in the app bar, roughly 21 px, it is gone.

The arrow is what makes the mark mean growth rather than shopping. Two options, and the specification carries both so the choice is yours.

**Keep it as drawn.** `mse-mark-colour.svg` is faithful to your file. The arrow reads as a subtle sheen at large sizes and disappears at small ones. Use `mse-mark-small.svg` below 48 px, which is what the app bar and the favicon now do.

**Make the arrow white throughout.** The arrow becomes part of the same negative-space system as the bars, so it reads at every size and survives single-colour printing. This changes your artwork, which is why it is not the default.

The recommendation is the second, applied to the full-size mark as well, so that one drawing works everywhere. Say the word and it is a one-line change to the builder.

---

## 7.5 Colour, and the accessibility problem

The audit measured two oranges, about `#FD5F05` in the logo files and about `#F05423` in the wireframes, and found both failing WCAG 2.2 AA for normal-size text. The master's gradient runs `#FF9A1F` to `#FF6A00` to `#F4511E`, which is a third set of values.

| Colour | Contrast on white | Verdict |
|---|---|---|
| `#FF6A00`, gradient midpoint | 2.87 : 1 | Fails AA for text at any size below 18.66 px bold |
| `#F05423`, the v0.1 interface orange | 3.5 : 1 | Fails AA for normal-size text |
| `#F4511E`, gradient end | 3.48 : 1 | Fails |
| **`#C4400C`, the v0.2 interface orange** | **5.14 : 1** | **Passes AA for all text, and AAA for large text** |

The rule that resolves it, and which is now written into the design language:

**The gradient is for the logo and for large graphics only. It is never used for text, for a button label, for a link, or for anything a person has to read.** Everything readable uses `#C4400C`. Logos are exempt from the contrast requirement, so the mark keeps its gradient. Interface text is not exempt, and NFR-10 requires AA.

White on `#C4400C` measures 5.14 : 1, so the primary button now passes. White on `#F05423` measured 3.5 : 1 and did not, unless the label was at least 18.66 px bold, which no button in the wireframes was.

The navy is standardised on `#111820`, the master's wordmark colour, replacing the tagline's `#16202a`.

---

## 7.6 Logo rules, added to Wireframes section 1.1

The v0.1 design language defines colour, type, layout, voice, labels and chips, and says nothing about the logo. This section fills that gap.

**Minimum size.** The horizontal lockup with the tagline is never used below 180 px wide. Below that, use `mse-logo-horizontal-notagline.svg`, down to 110 px. Below 110 px, use the mark alone. Below 48 px, use `mse-mark-small.svg`.

**Clear space.** Keep clear space on all four sides equal to the height of the bag's handle, which is 89 units in the mark's own coordinates, or roughly one sixth of the mark's height. Nothing else sits inside it, including the edge of the page.

**On dark backgrounds.** Use the reversed lockup. Do not place the colour lockup on a dark surface and do not add a white box behind it. The reversed lockup needs a background darker than `#6B7A8D` to hold its own; on anything lighter, use the colour version.

**On photography.** Reversed lockup, over an area of even tone. If no such area exists, the image is the wrong image.

**What is never done.** The lockup is not stretched, recoloured outside the supplied variants, outlined, given a shadow, rotated, or rebuilt by setting the wordmark in a font. The mark and the wordmark are not separated and rearranged into a new lockup; the five supplied lockups are the lockups.

**Tagline.** "Know Your Numbers" appears only as part of a supplied lockup, never set separately. It is title case, and it carries no full stop.

---

## 7.7 Where the logo now appears

The audit listed seven places. Each is specified.

| Place | Asset | Status |
|---|---|---|
| App top bar, every screen | `mse-mark-small.svg` plus the two-tone wordmark | Done. All nine new figures re-rendered. |
| Sign-in and sign-up screens | `mse-logo-horizontal.svg` | Specified on S17 and S19. |
| Web app icons, favicon, splash | `mse-icon.svg`, maskable, favicon set | Files built, manifest written. |
| Transactional email templates | `raster/logo-horizontal-1200.png` | Specified. Email clients are unreliable with SVG, so the raster is the one to use. |
| Excel and CSV export header | `raster/mark-512.png` plus the shop name, period, basis and as-at time | Specified in Action 5, section 5.7. CSV carries the text header only, since a CSV cannot hold an image. |
| Document covers and headers | `mse-logo-horizontal.svg` | Applied in Action 8. |
| Privacy notice, TikTok app listing | `mse-icon.svg` at 512, `mse-logo-horizontal.svg` | Specified. The TikTok review listing needs a square icon, which did not previously exist. |

---

## 7.8 What is still open in this action

The nine figures from Action 3 now carry the mark. **The original eight figures, covering screens S1 to S15, still show the v0.1 plain orange text wordmark**, because they are images produced before this project and the renderer has no definition of those fifteen screens.

Rebuilding them in the renderer is the remaining work. It is worth doing rather than patching the images, because it also applies the corrected orange, fixes the sample-data contradiction specified in Action 3, section 3.9, and leaves every figure in the pack regenerable from one source.

---

## 7.9 Summary of what Action 7 changes

| Document | Change |
|---|---|
| Wireframes and Workflows | Section 1.1 gains the logo rules in 7.6 and the colour rule in 7.5. All figures carry the mark once S1 to S15 are rebuilt. |
| All ten documents | Cover and header carry `mse-logo-horizontal.svg`, applied in Action 8. |
| SRD | NFR-10 acceptance names `#C4400C` as the interface orange and records the measured ratio. |
| TRD | Section 6, Frontend architecture, names the asset set and the manifest. |
| Data Protection | The privacy notice carries the logo. |
| API Integration | Section 3.1, Access and approval, notes that the TikTok app registration needs the 512 px square icon. |

---

## 7.10 The colour standard

Added to section 1.1 of the Wireframes and Workflows document, replacing the v0.1 rule
"Fixed colours for cost categories: stock magenta, postage teal, their cut blue, you
keep orange".

### Orange belongs to the platform

Orange is the logo, the primary action and the active tab. **It never carries data
meaning and it never carries status.** v0.1 used it for the hero figure, the VAT meter,
the "you keep" segment and the calculator total, which put the brand colour in
competition with the numbers and left nothing distinct for the brand itself.

### Three data families, and nothing else

| Family | Role | Values |
|---|---|---|
| Navy | Gross profit, and every headline figure | `#10263D`, 15.37 : 1 on white |
| Blue | TikTok fees, four tints in fee order | `#1D4FA8`, `#4076C8`, `#7099DC`, `#A3BFEB` |
| Plum | Your costs, two tints | `#6B2E8F`, `#A06BC4` |

One hue per family is what keeps this minimal. The fees stay separately identifiable
because they are tints of one blue rather than four unrelated colours, and because every
segment carries its name and its amount in the legend beside it. Section 7 of the
Wireframes document already requires that no meaning is carried by colour alone, and
that rule is unchanged.

### Three status colours, for payment only

| Status | Text | Background | Contrast |
|---|---|---|---|
| Not paid, overdue | `#B3261E` | `#FBE9E7` | 5.58 : 1 |
| Pending | `#8A5A00` | `#FBF0D9` | 5.24 : 1 |
| Settled | `#12633A` | `#E2F1E8` | 6.26 : 1 |

These three appear on settlement, on expected payouts, on a payout's own screen and on a
refund's status. They are not used for anything else, so that red on this product always
means money that has not arrived.

Every value above passes WCAG 2.2 AA, which NFR-10 requires. The ratios were measured
rather than judged by eye.

### What this replaces

The v0.1 category colours are withdrawn. Magenta, teal and the orange "you keep" segment
were four unrelated hues carrying four unrelated ideas, and the audit's accessibility
finding applied to the orange among them.

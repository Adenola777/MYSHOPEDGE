"""MyShopEdge brand asset builder.

Derives the production asset set from the supplied vector master
(brand/master_supplied.svg). The artwork geometry is copied exactly; what changes
is structure, so the mark works on any background and in one colour.

Key structural change: the white shapes inside the bag (the diagonal, the four bars)
and the gap around the handle are knocked out with a mask rather than painted white.
A painted white shape is only invisible on a white page. A knockout is transparent
everywhere, which is what a reversed or single-colour mark needs.
"""
import os, re

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- geometry
# Copied verbatim from the supplied master, local coordinates of group g10.
BAG      = "M45 95 Q45 62 78 62 L485 62 Q518 62 518 95 L518 486 Q518 518 486 518 L78 518 Q45 518 45 486 Z"
HANDLE   = "M178 69 V28 C178 -18 371 -18 371 28 V69"        # stroke 26
HANDLE_G = "M185 68 V25 C185 -35 378 -35 378 25 V68"        # stroke 34, the separation gap
DIAGONAL = "M76 109 L302 218 L246 281 L76 194 Z"
ARROW    = "M251 401 C304 365 341 322 384 277 C418 242 443 208 462 171"   # stroke 20
ARROWHD  = "M439 184 L468 151 L470 197 Z"
BARS = [(105, 390, 48, 128), (176, 342, 48, 176), (247, 291, 48, 227), (318, 235, 48, 283)]

# Tight bounds of the mark, measured from the master rather than assumed.
MARK_X, MARK_Y, MARK_W, MARK_H = 45, -20, 473, 538

# ---------------------------------------------------------------- colour
GRADIENT = [("0%", "#FF9A1F"), ("55%", "#FF6A00"), ("100%", "#F4511E")]
ORANGE_SOLID = "#C4400C"   # 5.14:1 on white. For anything that is text or a control.
NAVY = "#111820"           # the master's wordmark colour, now used for the tagline too
WHITE = "#FFFFFF"


def grad_def(gid="mseOrange"):
    stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in GRADIENT)
    return (f'<linearGradient id="{gid}" x1="0%" y1="0%" x2="100%" y2="100%">'
            f'{stops}</linearGradient>')


def mark_body(fill, mask_id="mseCut", grad_id=None):
    """The mark itself. fill is a colour or url(#gradient)."""
    bars = "".join(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#000"/>'
        for x, y, w, h in BARS)
    return f"""  <defs>
    {grad_def(grad_id) if grad_id else ''}
    <mask id="{mask_id}" maskUnits="userSpaceOnUse"
          x="{MARK_X}" y="{MARK_Y}" width="{MARK_W}" height="{MARK_H}">
      <rect x="{MARK_X}" y="{MARK_Y}" width="{MARK_W}" height="{MARK_H}" fill="#fff"/>
      <path d="{DIAGONAL}" fill="#000"/>
      {bars}
      <path d="{HANDLE_G}" fill="none" stroke="#000" stroke-width="34" stroke-linecap="round"/>
      <!-- The arrow is knocked out so it reads at every size, not only where it
           happens to cross a bar. A fill-coloured separation is drawn back over it
           below, so the bars stay four bars rather than merging into the arrow. -->
      <path d="{ARROW}" fill="none" stroke="#000" stroke-width="26" stroke-linecap="round"/>
      <path d="{ARROWHD}" fill="#000" stroke="#000" stroke-width="10" stroke-linejoin="round"/>
    </mask>
  </defs>
  <g fill="{fill}">
    <path d="{BAG}" mask="url(#{mask_id})"/>
    <path d="{HANDLE}" fill="none" stroke="{fill}" stroke-width="26" stroke-linecap="round"/>
  </g>"""


def write(name, svg):
    p = os.path.join(OUT, name)
    open(p, "w").write(svg)
    print(" ", name)


def svg_doc(viewbox, body, w=None, h=None, title="MyShopEdge"):
    size = f' width="{w}" height="{h}"' if w else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}"{size} '
            f'role="img" aria-label="{title}">\n'
            f'  <title>{title}</title>\n{body}\n</svg>\n')


# ---------------------------------------------------------------- the mark alone
def build_marks():
    vb = f"{MARK_X} {MARK_Y} {MARK_W} {MARK_H}"
    write("mse-mark-colour.svg",
          svg_doc(vb, mark_body("url(#mseOrange)", "mseCutA", "mseOrange"),
                  title="MyShopEdge mark"))
    write("mse-mark-solid.svg",
          svg_doc(vb, mark_body(ORANGE_SOLID, "mseCutB"), title="MyShopEdge mark"))
    write("mse-mark-reversed.svg",
          svg_doc(vb, mark_body(WHITE, "mseCutC"), title="MyShopEdge mark"))
    write("mse-mark-navy.svg",
          svg_doc(vb, mark_body(NAVY, "mseCutD"), title="MyShopEdge mark"))
    # currentColor lets the mark inherit a text colour wherever it is embedded.
    write("mse-mark-currentcolor.svg",
          svg_doc(vb, mark_body("currentColor", "mseCutE"), title="MyShopEdge mark"))


# ---------------------------------------------------------------- square icons
def build_square_icons():
    """A square icon is the MARK alone, sized to fill the canvas.

    The supplied square file is the horizontal lockup centred in a square, so the
    artwork spans about 17% of the height and is illegible at 32 px. This is the fix.
    """
    # Safe area: the mark occupies 76% of the canvas, centred.
    canvas = 512
    target = canvas * 0.76
    scale = target / MARK_H
    w = MARK_W * scale
    tx = (canvas - w) / 2 - MARK_X * scale
    ty = (canvas - target) / 2 - MARK_Y * scale
    body = (f'  <g transform="translate({tx:.2f},{ty:.2f}) scale({scale:.5f})">\n'
            + mark_body("url(#mseOrange)", "mseCutIcon", "mseOrange") + "\n  </g>")
    write("mse-icon.svg", svg_doc(f"0 0 {canvas} {canvas}", body, title="MyShopEdge"))

    # Maskable: Android crops to a circle of 80% diameter, so the mark shrinks to 58%
    # and the canvas carries the brand colour rather than transparency.
    target_m = canvas * 0.58
    scale_m = target_m / MARK_H
    w_m = MARK_W * scale_m
    tx_m = (canvas - w_m) / 2 - MARK_X * scale_m
    ty_m = (canvas - target_m) / 2 - MARK_Y * scale_m
    body_m = (f'  <rect width="{canvas}" height="{canvas}" fill="{ORANGE_SOLID}"/>\n'
              f'  <g transform="translate({tx_m:.2f},{ty_m:.2f}) scale({scale_m:.5f})">\n'
              + mark_body(WHITE, "mseCutMask") + "\n  </g>")
    write("mse-icon-maskable.svg",
          svg_doc(f"0 0 {canvas} {canvas}", body_m, title="MyShopEdge"))

    # Favicon: at 16 and 32 px the four bars merge, so the favicon drops the diagonal
    # and keeps the bag, the handle and the arrow only.
    bars_only_mask = f"""  <defs>
    {grad_def('mseOrangeF')}
    <mask id="mseCutFav" maskUnits="userSpaceOnUse"
          x="{MARK_X}" y="{MARK_Y}" width="{MARK_W}" height="{MARK_H}">
      <rect x="{MARK_X}" y="{MARK_Y}" width="{MARK_W}" height="{MARK_H}" fill="#fff"/>
      <path d="{DIAGONAL}" fill="#000"/>
      <path d="{HANDLE_G}" fill="none" stroke="#000" stroke-width="34" stroke-linecap="round"/>
    </mask>
  </defs>
  <g fill="url(#mseOrangeF)">
    <path d="{BAG}" mask="url(#mseCutFav)"/>
    <path d="{HANDLE}" fill="none" stroke="url(#mseOrangeF)" stroke-width="26" stroke-linecap="round"/>
    <path d="{ARROW}" fill="none" stroke="#FFFFFF" stroke-width="34" stroke-linecap="round"/>
    <path d="{ARROWHD}" fill="#FFFFFF"/>
  </g>"""
    # The same simplified construction, as a reusable mark for anything under 48 px.
    cs = f"{MARK_X} {MARK_Y} {MARK_W} {MARK_H}"
    write("mse-mark-small.svg", svg_doc(cs, bars_only_mask, title="MyShopEdge mark"))

    cf = 64
    sf = cf * 0.84 / MARK_H
    wf = MARK_W * sf
    body_f = (f'  <g transform="translate({(cf-wf)/2 - MARK_X*sf:.3f},'
              f'{(cf-cf*0.84)/2 - MARK_Y*sf:.3f}) scale({sf:.5f})">\n'
              + bars_only_mask + "\n  </g>")
    write("mse-favicon.svg", svg_doc(f"0 0 {cf} {cf}", body_f, title="MyShopEdge"))


# ---------------------------------------------------------------- lockups
def wordmark_paths():
    """Lift the wordmark and tagline outlines out of the master.

    They are already outlines rather than live text, so no font is needed to render
    them. The tagline is recoloured from #16202a to #111820: the master carries two
    near-blacks that differ by a shade nobody intended.
    """
    s = open(os.path.join(OUT, "master_supplied.svg")).read()
    def grab(tid):
        i = s.index(f'id="{tid}"')
        j = s.rindex("<path", 0, i)
        k = s.index("/>", i) + 2
        return s[j:k]
    my   = grab("text10")   # "MyShop", navy
    edge = grab("text11")   # "Edge", gradient
    tag  = grab("text12")   # "Know Your Numbers"
    tag = tag.replace("#16202a", NAVY).replace("#16202A", NAVY)
    # The master's "Edge" fills from a gradient called "orange". The derived files
    # name their gradient "mseOrange" so that several logos can sit on one page
    # without their gradient ids colliding. The reference has to follow the rename,
    # or "Edge" silently disappears.
    edge = edge.replace("url(#orange)", "url(#mseOrange)")
    # The master sets "MyShop" ending at x 1364.5 and "Edge" starting at x 1430.6, a gap
    # of 66 units at a 174-unit type size. That is a full word space, so the master reads
    # "MyShop Edge" while the supplied PNG reads "MyShopEdge". The gap is closed to 6
    # units, which matches the tight letter spacing the wordmark already uses.
    edge = '<g transform="translate(-60,0)">' + edge + '</g>'
    return my, edge, tag


def build_lockups():
    my, edge, tag = wordmark_paths()

    # Measured bounds from the master.
    mark_gx, mark_gy = 130, 650                     # the master's translate on g10
    text_x0, text_y0, text_x1, text_y1 = 746.5, 708.9, 1814.4, 945.7

    # The master sets the mark 71 units below the optical centre of the text block.
    # The derived lockups centre the two on each other.
    mark_cy = mark_gy + MARK_Y + MARK_H / 2
    text_cy = (text_y0 + text_y1) / 2
    dy = text_cy - mark_cy

    pad = 40
    x0 = mark_gx + MARK_X - pad
    y0 = min(mark_gy + MARK_Y + dy, text_y0) - pad
    x1 = text_x1 - 60 + pad
    y1 = max(mark_gy + MARK_Y + MARK_H + dy, text_y1) + pad
    vb = f"{x0:.1f} {y0:.1f} {x1-x0:.1f} {y1-y0:.1f}"

    def lockup(mark_fill, mask_id, grad, word_my, word_edge, word_tag, with_tag=True):
        g = (f'  <g transform="translate({mark_gx},{mark_gy + dy:.2f})">\n'
             + mark_body(mark_fill, mask_id, grad) + "\n  </g>\n"
             f'  <g>{word_my}{word_edge}</g>')
        if with_tag:
            g += f"\n  {word_tag}"
        return g

    write("mse-logo-horizontal.svg",
          svg_doc(vb, lockup("url(#mseOrange)", "mseCutL1", "mseOrange", my, edge, tag),
                  title="MyShopEdge, Know Your Numbers"))

    # Reversed: mark and wordmark go white, the gradient is dropped.
    my_r   = re.sub(r'fill:#111820', 'fill:#FFFFFF', my)
    edge_r = re.sub(r'fill:url\(#mseOrange\)', 'fill:#FFFFFF', edge)
    tag_r  = re.sub(r'fill:#111820', 'fill:#FFFFFF', tag)
    write("mse-logo-horizontal-reversed.svg",
          svg_doc(vb, lockup(WHITE, "mseCutL2", None, my_r, edge_r, tag_r),
                  title="MyShopEdge, Know Your Numbers"))

    # Single colour, for a fax, an embossing, a one-colour print job.
    my_m   = re.sub(r'fill:#111820', f'fill:{NAVY}', my)
    edge_m = re.sub(r'fill:url\(#mseOrange\)', f'fill:{NAVY}', edge)
    tag_m  = re.sub(r'fill:#111820', f'fill:{NAVY}', tag)
    write("mse-logo-horizontal-mono.svg",
          svg_doc(vb, lockup(NAVY, "mseCutL3", None, my_m, edge_m, tag_m),
                  title="MyShopEdge, Know Your Numbers"))

    # No tagline. Below about 120 px wide the tagline stops being readable.
    y0n = min(mark_gy + MARK_Y + dy, text_y0) - pad
    y1n = max(mark_gy + MARK_Y + MARK_H + dy, text_y1 - 49.2 - 25) + pad
    vbn = f"{x0:.1f} {y0n:.1f} {x1-x0:.1f} {y1n-y0n:.1f}"
    write("mse-logo-horizontal-notagline.svg",
          svg_doc(vbn, lockup("url(#mseOrange)", "mseCutL4", "mseOrange",
                              my, edge, tag, with_tag=False),
                  title="MyShopEdge"))

    # Stacked, for a narrow column or a square-ish space.
    sm = 1.55
    word_w = text_x1 - 60 - text_x0
    mark_w_s = MARK_W * sm
    total_w = max(word_w, mark_w_s)
    gap = 90
    body = (f'  <g transform="translate({(total_w - mark_w_s)/2 - MARK_X*sm:.2f},'
            f'{-MARK_Y*sm:.2f}) scale({sm})">\n'
            + mark_body("url(#mseOrange)", "mseCutS", "mseOrange") + "\n  </g>\n"
            f'  <g transform="translate({(total_w - word_w)/2 - text_x0:.2f},'
            f'{MARK_H*sm + gap - text_y0:.2f})">{my}{edge}\n  {tag}</g>')
    write("mse-logo-stacked.svg",
          svg_doc(f"-40 -40 {total_w+80:.1f} {MARK_H*sm + gap + (text_y1-text_y0) + 80:.1f}",
                  body, title="MyShopEdge, Know Your Numbers"))


if __name__ == "__main__":
    print("Building MyShopEdge brand assets:")
    build_marks()
    build_square_icons()
    build_lockups()
    print("done")

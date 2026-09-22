/* Pending Figma change set. Written 22 September 2026.
 *
 * The Figma account reached the Starter plan tool call limit before this could run, so
 * none of it has been applied. It is one script on purpose: it is safe to retry from the
 * start, and it spends one call rather than five.
 *
 *   File   Lv1sLPt9MeE27TeKGy4hOT  "MyShopEdge Onboarding"
 *   Team   team::1663465918505300844
 *   Ruled  A15 sections 15.1 to 15.5
 *
 * Node ids are stable across sessions, so the literals below remain correct. If a call
 * fails on a missing node, read the page first rather than guessing a replacement id.
 */

async function setText(t, s) {
  for (const seg of t.getStyledTextSegments(["fontName"])) await figma.loadFontAsync(seg.fontName);
  t.characters = s;
  t.name = s.slice(0, 60);
}
const done = [];

// 15.1  S39: Excel and CSV only. Word and PDF are withdrawn.
const s39 = await figma.getNodeByIdAsync("12:259");
const c39 = s39.children.filter(n => n.name === "Card");
await setText(s39.children[2], "We read Excel and CSV. Send the file in the shape you already keep it.");
await setText(c39[1].children[0], "What we accept");
await setText(c39[1].children[1], "XLSX, XLS and CSV, up to 10 MB.");
await setText(c39[2].children[0], "Why a spreadsheet only");
await setText(c39[2].children[1], "Excel and CSV files have rows and columns, so we can match them to your products. A Word file or a PDF has no columns, so we would be guessing at your costs. We would rather you typed them in than have us guess.");
done.push("S39 formats");

// 15.4  S3: cut the three duplicate cards, keep the buttons, keep one reassurance.
const s3 = await figma.getNodeByIdAsync("3:47");
const skipLine = s3.query("TEXT[name*=add your costs later]").first();
const keptLine = skipLine ? skipLine.characters : null;
for (const card of s3.children.filter(n => n.name === "Card")) card.remove();
await setText(s3.children[2], "Without costs we can show what TikTok took. With costs we can show what you keep. We read Excel and CSV files.");
if (keptLine) {
  const foot = s3.children[2].clone();
  await setText(foot, keptLine);
  foot.fontSize = 13;
  s3.appendChild(foot);
  foot.layoutSizingHorizontal = "FILL";
}
done.push("S3 cards cut");

// 15.2 and 15.3  Cut S19 Sign in (hosted) and S18 Return.
for (const id of ["2:12", "2:17"]) {
  const n = await figma.getNodeByIdAsync(id);
  if (n) { done.push("cut " + n.name); n.remove(); }
}

// 15.5  S6 keeps its congratulation, and now carries a celebration.
const s6 = await figma.getNodeByIdAsync("4:59");
await setText(s6.children[1], "You are set up 🎉");
done.push("S6 emoji");

// Close the gaps the two cuts leave in the canvas.
const frames = figma.currentPage.children.filter(n => n.type === "FRAME");
frames.sort((a, b) => (a.y - b.y) || (a.x - b.x));
frames.forEach((f, i) => { f.x = (i % 6) * 450; f.y = Math.floor(i / 6) * 950; });

return { done, frameCount: frames.length, order: frames.map(f => f.name) };

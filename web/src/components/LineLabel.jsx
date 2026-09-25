/**
 * The name of one calculator line, shared by Money and Products so the same money reads
 * the same way on both screens.
 *
 * A platform adjustment or a fee MyShopEdge does not recognise is named in plain words,
 * with TikTok's own name for it underneath, because TikTok's name is what the seller will
 * find on the statement (A8). Every other line carries the label the service gave it.
 */

/** @param {{ line: { label: string, category?: string | null, tiktok_fee_type?: string | null } }} props */
export function LineLabel({ line }) {
  if (!line.tiktok_fee_type) return line.label;
  return (
    <span>
      {line.category === "platform_adjustment" ? "TikTok adjustment" : "Fee we do not recognise"}
      <span className="rows__sub" style={{ display: "block" }}>TikTok calls it {line.tiktok_fee_type}</span>
    </span>
  );
}

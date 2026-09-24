import { ShopNav } from "@/components/ShopNav";

/** @param {{ children: React.ReactNode, params: Promise<{ shopId: string }> }} props */
export default async function ShopLayout({ children, params }) {
  const { shopId } = await params;
  return (
    <>
      <ShopNav shopId={shopId} />
      {children}
    </>
  );
}

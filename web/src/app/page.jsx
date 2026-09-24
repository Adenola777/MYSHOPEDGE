import { redirect } from "next/navigation";

/** The home address has nothing of its own. A seller's figures live under their shop. */
export default function Home() {
  redirect("/shops");
}

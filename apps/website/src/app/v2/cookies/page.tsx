import type { Metadata } from "next";
import { LegalReader } from "../../../features/supporting/LegalReader";
export const metadata: Metadata = {
  title: "Cookie Policy — Bali Zero",
  robots: { index: false, follow: false },
};
export default function Page() {
  return <LegalReader documentKey="v2-cookies" />;
}

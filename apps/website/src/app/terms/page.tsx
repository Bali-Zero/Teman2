import type { Metadata } from "next";
import { LegalReader } from "../../features/supporting/LegalReader";
export const metadata: Metadata = {
  title: "Terms of Service — Bali Zero",
  description: "Terms governing Bali Zero's services.",
};
export default function Page() {
  return <LegalReader documentKey="terms" />;
}

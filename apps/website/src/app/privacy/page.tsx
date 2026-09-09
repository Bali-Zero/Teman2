import type { Metadata } from "next";
import { LegalReader } from "../../features/supporting/LegalReader";
export const metadata: Metadata = {
  title: "Privacy Policy — Bali Zero",
  description: "Bali Zero's privacy policy and personal data rights.",
};
export default function Page() {
  return <LegalReader documentKey="privacy" />;
}

import type { Metadata } from "next";
import { CompanyPage } from "../../../../features/supporting/CompanyPage";
export const metadata: Metadata = {
  title: "Press & Media — Bali Zero",
  description:
    "Media enquiries and background on Bali Zero's work in Indonesia.",
  robots: { index: false, follow: false },
};
export default function Page() {
  return <CompanyPage kind="press" />;
}

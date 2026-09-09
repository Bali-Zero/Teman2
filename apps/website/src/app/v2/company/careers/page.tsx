import type { Metadata } from "next";
import { CompanyPage } from "../../../../features/supporting/CompanyPage";
export const metadata: Metadata = {
  title: "Careers — Bali Zero",
  description:
    "Meet the work behind Bali Zero and introduce yourself for future opportunities.",
  robots: { index: false, follow: false },
};
export default function Page() {
  return <CompanyPage kind="careers" />;
}

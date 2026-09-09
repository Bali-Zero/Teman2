import type { Metadata } from "next";
import { ToolFrame } from "../../features/tax-property/ToolFrame";
import { Preparation } from "../../features/tax-property/Preparation";

export const metadata: Metadata = {
  title: "Zoning & property due diligence | Bali Zero",
  description:
    "Prepare the title, zoning, building and agreement records for a property review in Bali.",
};
export default function ZoningPage() {
  return (
    <ToolFrame
      family="Property"
      title="Read the site. Review the whole picture."
      intro="Land use, title, building approvals and the agreement each answer a different question. Bring them together before making a property decision."
    >
      <Preparation family="property" />
    </ToolFrame>
  );
}

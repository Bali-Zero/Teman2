import type { Metadata } from "next";
import { ToolFrame } from "../../../features/tax-property/ToolFrame";
import { PropertyCheck } from "../../../features/tax-property/PropertyCheck";

export const metadata: Metadata = {
  title: "Property coordinate check | Bali Zero",
  description:
    "Review the zoning record, building parameters and preliminary findings for an exact property location.",
};
export default function PropertyEligibilityPage() {
  return (
    <ToolFrame
      family="Property"
      title="Every property starts with a place."
      intro="Enter the exact coordinates to request the zoning record and a preliminary site assessment. Add an activity code or investment inputs when those questions are part of your review."
    >
      <PropertyCheck />
    </ToolFrame>
  );
}

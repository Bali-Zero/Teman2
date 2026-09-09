import type { Metadata } from "next";
import { ToolFrame } from "../../features/tax-property/ToolFrame";
import { PropertyCheck } from "../../features/tax-property/PropertyCheck";

export const metadata: Metadata = {
  title: "Prime zoning atlas | Bali Zero",
  description:
    "Explore the public zoning polygons, compare recorded limits and request a property coordinate analysis.",
  robots: { index: false, follow: false },
};
export default function PrimePage() {
  return (
    <ToolFrame
      family="Property"
      title="A closer reading of Bali."
      intro="Explore the zoning layer, inspect recorded building limits and choose an exact site for analysis. Prime brings the map and the property questions into one place."
    >
      <PropertyCheck atlas />
    </ToolFrame>
  );
}

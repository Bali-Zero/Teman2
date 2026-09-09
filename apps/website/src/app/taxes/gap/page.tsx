import type { Metadata } from "next";
import { ToolFrame } from "../../../features/tax-property/ToolFrame";
import { Preparation } from "../../../features/tax-property/Preparation";

export const metadata: Metadata = {
  title: "Tax gap review | Bali Zero",
  description:
    "Prepare registrations, previous filings and supporting records for a review of your tax position.",
};
export default function TaxGapPage() {
  return (
    <ToolFrame
      family="Tax"
      title="Bring your tax picture into focus."
      intro="A practical route through registrations, reporting periods and previous filings. Gather the evidence, identify the questions and agree the next steps with your tax adviser."
    >
      <Preparation family="tax" />
    </ToolFrame>
  );
}

import type { Metadata } from "next";
import { ToolFrame } from "../../features/tax-property/ToolFrame";
import { TaxCalendar } from "../../features/tax-property/TaxCalendar";

export const metadata: Metadata = {
  title: "Tax calendar archive | Bali Zero",
  description:
    "Browse the retained tax calendar records, filter by obligation and regency, and prepare a review of your reporting periods.",
};
export default function TaxCalendarPage() {
  return (
    <ToolFrame
      family="Tax"
      title="Your reporting, in perspective."
      intro="Find the records behind a reporting period. Filter the archived calendar, export the dates and bring the right questions to the tax team."
    >
      <TaxCalendar />
    </ToolFrame>
  );
}

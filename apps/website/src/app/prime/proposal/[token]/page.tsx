import type { Metadata } from "next";
import { ToolFrame } from "../../../../features/tax-property/ToolFrame";
import { Proposal } from "../../../../features/tax-property/Proposal";

export const metadata: Metadata = {
  title: "Shared property proposal | Bali Zero",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export default async function ProposalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return (
    <ToolFrame
      family="Property"
      title="The property dossier."
      intro="Review the saved site findings and the assumptions behind the assessment."
    >
      <Proposal token={token} />
    </ToolFrame>
  );
}

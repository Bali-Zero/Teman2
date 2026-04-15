import type { Metadata } from "next";
import { TokenExplorer } from "./TokenExplorer";

// Internal QA + onboarding surface. Not linked from public nav.
export const metadata: Metadata = {
  title: "Token Explorer · DS Internal",
  robots: { index: false, follow: false },
};

export default function TokenExplorerPage() {
  return <TokenExplorer />;
}

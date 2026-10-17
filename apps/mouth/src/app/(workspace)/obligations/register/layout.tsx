import type { ReactNode } from "react";

// Keep the authenticated register out of public prerendered route payloads.
export const dynamic = "force-dynamic";

export default function ComplianceRegisterLayout({
  children,
}: {
  children: ReactNode;
}) {
  return children;
}

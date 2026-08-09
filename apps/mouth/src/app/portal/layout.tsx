import type { Metadata } from "next";
import type { ReactNode } from "react";

/**
 * The client portal is a private product surface, including its public
 * authentication and recovery screens. None of its URLs should inherit the
 * marketing site's indexable metadata or canonical URL.
 */
export const metadata: Metadata = {
  title: {
    default: "Client Portal",
    template: "%s | Bali Zero",
  },
  description: "Secure Bali Zero client portal.",
  robots: { index: false, follow: false },
  alternates: { canonical: null },
  openGraph: null,
  twitter: null,
};

export default function PortalMetadataLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children;
}

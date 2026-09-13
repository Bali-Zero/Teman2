import type { Metadata } from "next";

const DESCRIPTION =
  "Kepatuhan usaha Anda, dikerjakan tim kami, dicek ulang oleh manusia.";

// Served on nuzantara.co.id through the NUZANTARA_DOMAIN rewrite in proxy.ts.
// Every field below that the root layout sets with Bali Zero copy is
// overridden here, so the domestic brand does not inherit it.
export const metadata: Metadata = {
  title: { absolute: "Nuzantara" },
  description: DESCRIPTION,
  keywords: ["kepatuhan usaha", "LKPM", "pajak bulanan", "PSE"],
  authors: [{ name: "Nuzantara" }],
  creator: "Nuzantara",
  publisher: "Nuzantara",
  appleWebApp: { capable: true, title: "Nuzantara", statusBarStyle: "default" },
  openGraph: {
    type: "website",
    locale: "id_ID",
    url: "https://nuzantara.co.id",
    title: "Nuzantara",
    description: DESCRIPTION,
    siteName: "Nuzantara",
  },
  twitter: { card: "summary", title: "Nuzantara", description: DESCRIPTION },
  alternates: { canonical: "https://nuzantara.co.id" },
  robots: { index: false, follow: false },
};

export default function NuzantaraLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div lang="id" className="min-h-screen flex flex-col">
      {children}
    </div>
  );
}

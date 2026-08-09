import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    "https://bali-zero-magazine.antonellosiano.chatgpt.site",
  ),
  title: "Bali Zero Magazine",
  description:
    "Verified intelligence on immigration, investment, tax, property, and compliance in Bali.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: "Bali Zero Magazine",
    description:
      "Verified intelligence on immigration, investment, tax, property, and compliance in Bali.",
    images: [
      {
        url: "/social/bali-zero-magazine-og.jpg",
        width: 1200,
        height: 630,
        alt: "Bali Zero Magazine editorial intelligence desk at dawn.",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Bali Zero Magazine",
    description:
      "Verified intelligence on immigration, investment, tax, property, and compliance in Bali.",
    images: ["/social/bali-zero-magazine-og.jpg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

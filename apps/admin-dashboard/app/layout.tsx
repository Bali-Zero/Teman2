import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { ErrorBoundary } from "@/components/optimization";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Nuzantara Admin Dashboard",
  description: "Inspector for PostgreSQL and Qdrant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 ml-64 bg-background">
            <ErrorBoundary>{children}</ErrorBoundary>
          </main>
        </div>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { ErrorBoundary } from "@/components/optimization";
import { I18nProvider } from "@/src/i18n";

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
        <I18nProvider>
          <div className="flex min-h-screen flex-col lg:flex-row">
            <Sidebar />
            <main className="min-w-0 flex-1 bg-background lg:ml-64">
              <ErrorBoundary>{children}</ErrorBoundary>
            </main>
          </div>
        </I18nProvider>
      </body>
    </html>
  );
}

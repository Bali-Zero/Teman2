import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bali Zero Drive",
  description: "Gestione documenti aziendali — Bali Zero",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="h-screen overflow-hidden bg-[#141416] text-[#f1f1f1]">
        <Providers>
          <AuthGate>{children}</AuthGate>
        </Providers>
      </body>
    </html>
  );
}

/**
 * Auth gate: checks for JWT cookie on .balizero.com domain.
 * If no valid session → redirects to kita.balizero.com/login?redirect=drive.balizero.com
 * Runs as a Server Component — redirect happens before any JS is sent to the browser.
 */
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

async function AuthGate({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const token = cookieStore.get("nz_auth_token")?.value;

  if (!token) {
    const redirectUrl = encodeURIComponent(
      process.env.NEXT_PUBLIC_APP_URL || "https://drive.balizero.com",
    );
    redirect(`https://kita.balizero.com/login?redirect=${redirectUrl}`);
  }

  return <>{children}</>;
}

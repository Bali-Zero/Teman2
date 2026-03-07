import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import "./globals.css";

const geist = Geist({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Bali Zero Calendar",
  description: "Bali Zero Team Calendar",
};

async function getSession(): Promise<boolean> {
  const cookieStore = await cookies();
  const token =
    cookieStore.get("balizero_session")?.value ||
    cookieStore.get("auth_token")?.value ||
    cookieStore.get("next-auth.session-token")?.value ||
    cookieStore.get("__Secure-next-auth.session-token")?.value;

  return !!token;
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const isAuthenticated = await getSession();

  if (!isAuthenticated) {
    redirect(
      "https://kita.balizero.com/login?redirect=https://calendar.balizero.com",
    );
  }

  return (
    <html lang="it">
      <body className={geist.className}>{children}</body>
    </html>
  );
}

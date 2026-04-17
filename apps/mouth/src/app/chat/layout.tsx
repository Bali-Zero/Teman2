import type { Metadata } from "next";
import { cookies } from "next/headers";
import { ContextPanel } from "./_components/ContextPanel";

export const metadata: Metadata = {
  title: "Zantara AI | Your Business Assistant in Bali",
  description:
    "AI-powered business assistant for Indonesia. Get instant answers about visas, company setup, KBLI codes, tax compliance, and more.",
  openGraph: {
    title: "Zantara AI | Your Business Assistant in Bali",
    description:
      "AI-powered business assistant for Indonesia. Visas, company setup, KBLI codes, and more.",
    url: "https://zantara.balizero.com",
  },
};

export default async function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const c = await cookies();
  const authenticated = Boolean(c.get("nz_access_token")?.value);
  const theme = authenticated ? "operative-light" : "editorial";

  return (
    <div data-theme={theme} className="flex flex-row h-screen">
      <main className="flex-1 min-w-0">{children}</main>
      {authenticated && (
        <aside className="hidden lg:block w-80 border-l border-[var(--glass-rim)] overflow-y-auto">
          <ContextPanel />
        </aside>
      )}
    </div>
  );
}

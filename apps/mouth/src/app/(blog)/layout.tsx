import type { ReactNode } from "react";
import { BlogNav } from "@/app/(blog)/_components/BlogNav";
import { ZantaraFAB } from "@/app/v2/_components/ZantaraFAB";
import { Footer } from "@/app/v2/_components/Footer";
import { I18nProvider } from "@/i18n";

export default function BlogLayout({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <div
        className="min-h-screen flex flex-col"
        style={{
          background: "var(--surface-base)",
          color: "var(--text-primary)",
        }}
      >
        <BlogNav />
        <main className="flex-1 pt-14">{children}</main>
        <Footer />
        <ZantaraFAB />
      </div>
    </I18nProvider>
  );
}

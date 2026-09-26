import type { ReactNode } from "react";
import { R19Presentation } from "@/components/r19/R19Presentation";
import { BlogNav } from "@/app/(blog)/_components/BlogNav";
import { ZantaraFAB } from "@/app/v2/_components/ZantaraFAB";
import { Footer } from "@/app/v2/_components/Footer";
import { I18nProvider } from "@/i18n";

export default function BlogLayout({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <R19Presentation>
        <div
          className="min-h-screen flex flex-col"
          style={{
            background: "var(--surface-base)",
            color: "var(--text-primary)",
          }}
        >
          <BlogNav />
          <main
            className="flex-1"
            style={{ paddingTop: "var(--public-header-height, 56px)" }}
          >
            {children}
          </main>
          <Footer />
          <ZantaraFAB />
        </div>
      </R19Presentation>
    </I18nProvider>
  );
}

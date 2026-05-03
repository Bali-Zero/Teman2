import { LanguageProvider } from "@/components/kbli/LanguageToggle";

export default function KBLILayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <LanguageProvider>
      <div className="relative z-1 mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {children}
      </div>
    </LanguageProvider>
  );
}

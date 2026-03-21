import type { Metadata } from "next";
import { getSections } from "@/lib/kbli-data";
import { KBLIBreadcrumb } from "@/components/kbli/KBLIBreadcrumb";
import { KBLISectorGrid } from "@/components/kbli/KBLISectorGrid";

export const metadata: Metadata = {
  title: "KBLI 2025 Sectors — Browse All Business Categories",
  description:
    "Browse all 22 KBLI 2025 business sectors. Indonesia's complete business classification system with PMA rules and licensing requirements.",
};

export default function SectorsPage() {
  const sections = getSections().filter((s) => s.codeCount > 0);

  return (
    <div className="space-y-8">
      <KBLIBreadcrumb
        items={[
          { label: "KBLI Navigator", href: "/kbli" },
          { label: "Sectors" },
        ]}
      />
      <div>
        <h1 className="text-3xl font-black tracking-tight text-[var(--foreground)] sm:text-4xl">
          KBLI 2025 Sectors
        </h1>
        <p className="mt-3 text-lg text-[var(--foreground-secondary)]">
          Indonesia&apos;s business classification system organized into{" "}
          {sections.length} economic sectors.
        </p>
      </div>
      <KBLISectorGrid sections={sections} />
    </div>
  );
}

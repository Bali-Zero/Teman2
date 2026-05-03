import type { Metadata } from "next";
import { getSections } from "@/lib/kbli-data";
import { KBLISectorGrid } from "@/components/kbli/KBLISectorGrid";
import { KBLIBreadcrumb } from "@/components/kbli/KBLIBreadcrumb";

export const metadata: Metadata = {
  title: "KBLI 2025 Sectors — Browse All 22 Business Sectors",
  description:
    "Browse all 22 KBLI 2025 sectors. From Agriculture to Extraterritorial Organizations — find the right business classification for your Indonesian business.",
};

export default function SectorsPage() {
  const sections = getSections().filter((s) => s.codeCount > 0);

  return (
    <div className="space-y-8">
      <KBLIBreadcrumb
        items={[
          { label: "KBLI Navigator", href: "/kbli" },
          { label: "All Sectors" },
        ]}
      />

      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">
          KBLI 2025 Sectors
        </h1>
        <p className="mt-2 text-[var(--foreground-secondary)]">
          Indonesia&apos;s business classification is organized into{" "}
          {sections.length} sectors covering every type of economic activity.
        </p>
      </div>

      <KBLISectorGrid sections={sections} />
    </div>
  );
}

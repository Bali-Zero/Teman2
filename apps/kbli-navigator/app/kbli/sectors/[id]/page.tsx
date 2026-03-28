import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getCodesBySection,
  getSections,
  getSectionMeta,
} from "@/lib/kbli-data";
import { KBLICard } from "@/components/kbli/KBLICard";
import { KBLIBreadcrumb } from "@/components/kbli/KBLIBreadcrumb";

export async function generateStaticParams() {
  return getSections()
    .filter((s) => s.codeCount > 0)
    .map((s) => ({ id: s.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const meta = getSectionMeta(id);
  if (!meta) return { title: "Sector Not Found" };

  return {
    title: `Section ${id.toUpperCase()} — ${meta.nameEn} | KBLI 2025`,
    description: `Browse all KBLI 2025 codes in Section ${id.toUpperCase()}: ${meta.nameEn}. ${meta.description}.`,
  };
}

export default async function SectorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const meta = getSectionMeta(id);
  if (!meta) notFound();

  const codes = getCodesBySection(id);

  return (
    <div className="space-y-8">
      <KBLIBreadcrumb
        items={[
          { label: "KBLI Navigator", href: "/kbli" },
          { label: "Sectors", href: "/kbli/sectors" },
          { label: `Section ${id.toUpperCase()}` },
        ]}
      />

      <div>
        <div className="mb-1 text-3xl" aria-hidden="true">
          {meta.icon}
        </div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">
          Section {id.toUpperCase()} — {meta.nameEn}
        </h1>
        <p className="mt-1 text-[var(--foreground-secondary)]">{meta.nameId}</p>
        <p className="mt-2 text-sm text-[var(--foreground-muted)]">
          {codes.length} codes • {meta.description}
        </p>
      </div>

      <div
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
        aria-label={`KBLI codes in Section ${id.toUpperCase()}`}
      >
        {codes.map((c) => (
          <KBLICard key={c.code} code={c} />
        ))}
      </div>
    </div>
  );
}

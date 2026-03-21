import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getSections,
  getCodesBySection,
  getSectionMeta,
} from "@/lib/kbli-data";
import { KBLIBreadcrumb } from "@/components/kbli/KBLIBreadcrumb";
import { KBLICard } from "@/components/kbli/KBLICard";

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

  const codes = getCodesBySection(id);
  const title = `Section ${id.toUpperCase()}: ${meta.nameEn} — KBLI 2025 Navigator`;
  const description = `Browse ${codes.length} KBLI 2025 codes in Section ${id.toUpperCase()} (${meta.nameEn}). ${meta.description}. PMA rules, licensing & risk levels.`;

  return {
    title,
    description,
    openGraph: { title, description, type: "website" },
    alternates: {
      canonical: `https://balizero.com/kbli/sectors/${id.toUpperCase()}`,
    },
  };
}

export default async function SectorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const meta = getSectionMeta(id);
  if (!meta) notFound();

  const codes = getCodesBySection(id);
  if (codes.length === 0) notFound();

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
        <div className="flex items-center gap-3 mb-2">
          <span className="text-4xl">{meta.icon}</span>
          <div>
            <h1 className="text-3xl font-black tracking-tight text-[var(--foreground)] sm:text-4xl">
              {meta.nameEn}
            </h1>
            <p className="text-base text-[var(--foreground-muted)]">
              {meta.nameId}
            </p>
          </div>
        </div>
        <p className="mt-3 text-lg text-[var(--foreground-secondary)]">
          {meta.description} — {codes.length} business codes in Section{" "}
          {id.toUpperCase()}.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {codes.map((code) => (
          <KBLICard key={code.code} code={code} />
        ))}
      </div>
    </div>
  );
}

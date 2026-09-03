import {
  getCodesBySection,
  getSectionMeta,
  getSections,
} from "@/lib/kbli-data";
import { toPanelDetail, type KBLIPanelDetail } from "@/lib/kbli-panel-detail";
import { KBLICard } from "@/components/kbli/KBLICard";
import { KBLISectorOffcanvas } from "@/components/kbli/KBLISectorOffcanvas";
import { KBLISectorStrip } from "@/components/kbli/KBLISectorStrip";

/**
 * Intercepted sector route — the off-canvas panel.
 *
 * Reached ONLY by client-side navigation to `/kbli/sectors/<id>` from inside
 * the `/kbli` layout (a sector card, or the strip inside an already-open
 * panel). A hard load, a shared link, a crawler or a JS-disabled browser all
 * get `app/kbli/sectors/[id]/page.tsx` — the full page — untouched. The panel
 * is an enhancement of that route, never a replacement for it.
 *
 * This component reads NO search params on purpose: the route is statically
 * prerendered, so a query string cannot reach the server here (the measurement
 * is in KBLISectorOffcanvas). The `?code=` drill-down is applied on the client
 * from the `details` projection below.
 *
 * A slot must not 404 the page it is rendered beside: an id we cannot resolve
 * returns null, which is what `@panel/default.tsx` would have rendered anyway.
 */
export default async function SectorPanelPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const sectionId = id.toUpperCase();

  const meta = getSectionMeta(sectionId);
  if (!meta) return null;

  const codes = getCodesBySection(sectionId);
  if (codes.length === 0) return null;

  const sections = getSections().filter((s) => s.codeCount > 0);
  const details: Record<string, KBLIPanelDetail> = {};
  for (const c of codes) details[c.code] = toPanelDetail(c);

  return (
    <KBLISectorOffcanvas
      title={`Section ${sectionId} — ${meta.nameEn}`}
      sectionId={sectionId}
      details={details}
      grid={
        <div className="grid grid-cols-1 gap-3 @[440px]:grid-cols-2">
          {codes.map((c) => (
            <KBLICard key={c.code} code={c} />
          ))}
        </div>
      }
    >
      <header className="shrink-0 border-b border-white/[0.06] px-5 pb-4 pr-14 pt-5">
        <div className="flex items-start gap-3">
          <span className="text-3xl leading-none" aria-hidden>
            {meta.icon}
          </span>
          <div className="min-w-0">
            <div
              data-testid="kbli-panel-section-eyebrow"
              className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--kbli-accent)]"
            >
              Section {sectionId}
            </div>
            <h2 className="mt-0.5 truncate text-lg font-bold leading-snug text-white">
              {meta.nameEn}
            </h2>
            <p className="truncate text-sm text-zinc-400">{meta.nameId}</p>
          </div>
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          {codes.length} business {codes.length === 1 ? "code" : "codes"} ·{" "}
          {/* A plain <a>: this one deliberately leaves the panel for the real
              page rather than being intercepted back into it. */}
          <a
            href={`/kbli/sectors/${sectionId}`}
            className="underline underline-offset-2 hover:text-zinc-300"
            data-testid="kbli-panel-fullpage-link"
          >
            open as full page
          </a>
        </p>
      </header>

      <KBLISectorStrip sections={sections} activeId={sectionId} />
    </KBLISectorOffcanvas>
  );
}

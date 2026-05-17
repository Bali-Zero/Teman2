import { WidgetPlaceholder } from "@/components/cockpit/WidgetPlaceholder";

export const dynamic = "force-dynamic";

export default function CockpitPage() {
  return (
    <main className="cockpit-grid">
      {/* Row 1 — Global */}
      <WidgetPlaceholder title="Global Pulse" deferTo="Task 20" />
      <WidgetPlaceholder title="Decisions Attesa" deferTo="Task 21" />
      <WidgetPlaceholder title="Cosa Ha Imparato" deferTo="S5" />
      <WidgetPlaceholder title="Comandi Rapidi" deferTo="S5" />
      {/* Row 2 — Intel-Lake */}
      <WidgetPlaceholder title="Intel Pipeline Live" deferTo="S2" />
      <WidgetPlaceholder title="Source Health" deferTo="S2" />
      <WidgetPlaceholder title="NB Push Log" deferTo="S2" />
      <WidgetPlaceholder title="Intel Manual Override" deferTo="S2" />
      {/* Row 3 — WR2 */}
      <WidgetPlaceholder title="WR2 Drafts Pipeline" deferTo="S3" />
      <WidgetPlaceholder title="WR2 IG Metrics" deferTo="S3" />
      <WidgetPlaceholder title="Canva Status" deferTo="S3" />
      <WidgetPlaceholder title="WR2 Manual Override" deferTo="S3" />
    </main>
  );
}

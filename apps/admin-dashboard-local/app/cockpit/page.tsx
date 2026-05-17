import { WidgetPlaceholder } from "@/components/cockpit/WidgetPlaceholder";
import { GlobalPulse } from "@/components/cockpit/GlobalPulse";
import { DecisionsAttesa } from "@/components/cockpit/DecisionsAttesa";
import { PinGate } from "@/components/cockpit/PinGate";

export const dynamic = "force-dynamic";

export default function CockpitPage() {
  return (
    <PinGate>
      <main className="cockpit-grid">
        {/* Row 1 — Global */}
        <GlobalPulse />
        <DecisionsAttesa />
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
    </PinGate>
  );
}

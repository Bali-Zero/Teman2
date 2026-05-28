import { WidgetFrame } from "./WidgetFrame";

export function WidgetPlaceholder({
  title,
  deferTo,
}: {
  title: string;
  deferTo: string;
}) {
  return (
    <WidgetFrame title={title} status="amber">
      <div style={{ color: "var(--fg-dim)", fontSize: 11 }}>
        deferred to {deferTo}
      </div>
    </WidgetFrame>
  );
}

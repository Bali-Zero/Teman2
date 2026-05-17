/**
 * WidgetFrame — generic titled panel wrapper.
 *
 * Used by /wr2 and /intel-lake pages to host tables / detail sections.
 */

interface WidgetFrameProps {
  title: string;
  status?: "healthy" | "amber" | "red";
  toolbar?: React.ReactNode;
  children: React.ReactNode;
}

export default function WidgetFrame({
  title,
  status,
  toolbar,
  children,
}: WidgetFrameProps) {
  return (
    <section className="cockpit-widget">
      <div
        className="cockpit-widget-title"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <span>
          {status ? <span className={`cockpit-dot ${status}`} /> : null}
          {title}
        </span>
        {toolbar}
      </div>
      <div className="cockpit-widget-body">{children}</div>
    </section>
  );
}

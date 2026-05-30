import { ReactNode } from "react";

export interface WidgetFrameProps {
  title: string;
  children: ReactNode;
  status?: "green" | "amber" | "red";
}

export function WidgetFrame({ title, children, status }: WidgetFrameProps) {
  return (
    <div className="cockpit-widget">
      <div className="cockpit-widget-title">
        {status && <span className={`status-dot ${status}`} aria-hidden />}
        {title}
      </div>
      <div className="cockpit-widget-body">{children}</div>
    </div>
  );
}

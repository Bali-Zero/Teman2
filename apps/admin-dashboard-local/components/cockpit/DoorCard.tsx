/**
 * DoorCard — large clickable card that navigates to a subpage.
 *
 * MVP rule: navigation only. NO destructive action. Click pushes the user
 * to /cockpit/<section>; the destination page is read-only.
 */
"use client";

import { useRouter } from "next/navigation";

interface DoorCardProps {
  title: string;
  description: string;
  href: string;
  children?: React.ReactNode;
}

export default function DoorCard({
  title,
  description,
  href,
  children,
}: DoorCardProps) {
  const router = useRouter();
  const onActivate = () => router.push(href);

  return (
    <div
      className="cockpit-door-card"
      role="link"
      tabIndex={0}
      onClick={onActivate}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onActivate();
        }
      }}
      aria-label={`Open ${title}`}
    >
      <h2>{title}</h2>
      <p className="desc">{description}</p>
      {children ? <div className="door-body">{children}</div> : null}
    </div>
  );
}

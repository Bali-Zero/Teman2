"use client";

import { useState } from "react";
import Image from "next/image";
import { initialsOf } from "@/lib/team-initials";
import { cn } from "@/lib/utils";

export function ChampionPortrait({
  name,
  src,
  className,
}: {
  name: string;
  src?: string | null;
  className?: string;
}) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const safeSource =
    src && /^\/static\/team\/[a-z0-9_-]+\.(jpg|jpeg|png|webp)$/i.test(src)
      ? src
      : null;
  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-[var(--bz-card-hover)] text-[var(--bz-copper-text)]",
        className,
      )}
    >
      {safeSource && safeSource !== failedSource ? (
        <Image
          src={safeSource}
          alt={name}
          fill
          sizes="(max-width: 640px) 120px, 220px"
          className="object-cover"
          onError={() => setFailedSource(safeSource)}
        />
      ) : (
        <span role="img" aria-label={name} className="text-2xl font-bold">
          {initialsOf(name)}
        </span>
      )}
    </span>
  );
}

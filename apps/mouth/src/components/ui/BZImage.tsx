"use client";

import NextImage, { type ImageProps } from "next/image";
import { useState } from "react";

interface BZImageProps extends Omit<ImageProps, "onError"> {
  fallbackLabel?: string;
  containerClassName?: string;
}

export function BZImage({
  fallbackLabel = "Bali Zero",
  containerClassName = "",
  className = "",
  alt,
  ...props
}: BZImageProps) {
  const [failed, setFailed] = useState(false);

  return (
    <div className={`relative overflow-hidden ${containerClassName}`}>
      {!failed && (
        <NextImage
          alt={alt}
          className={`object-cover transition-opacity duration-300 ${className}`}
          onError={() => setFailed(true)}
          {...props}
        />
      )}
      {failed && (
        <div className="absolute inset-0 flex items-center justify-center bg-[var(--surface-muted)]">
          <span className="text-[var(--text-tertiary)] text-[11px] font-semibold uppercase tracking-[0.15em]">
            {fallbackLabel}
          </span>
        </div>
      )}
    </div>
  );
}

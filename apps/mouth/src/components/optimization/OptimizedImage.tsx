/**
 * Optimized Image Component
 *
 * Wrapper around Next.js Image with best practices for performance:
 * - Lazy loading
 * - Proper sizing
 * - Blur placeholder
 * - Priority loading for above-fold images
 */

import React from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

interface OptimizedImageProps {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  fill?: boolean;
  priority?: boolean;
  className?: string;
  containerClassName?: string;
  blurDataURL?: string;
  sizes?: string;
  quality?: number;
  objectFit?: "cover" | "contain" | "fill" | "none" | "scale-down";
  onLoad?: () => void;
  onError?: () => void;
}

/**
 * Optimized Image Component
 *
 * Best practices implemented:
 * 1. Lazy loading by default (unless priority)
 * 2. Proper aspect ratio to prevent CLS
 * 3. Blur placeholder for better perceived performance
 * 4. Responsive sizes
 * 5. WebP/AVIF format support (handled by Next.js)
 */
export function OptimizedImage({
  src,
  alt,
  width,
  height,
  fill = false,
  priority = false,
  className,
  containerClassName,
  blurDataURL,
  sizes = "(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw",
  quality = 85,
  objectFit = "cover",
  onLoad,
  onError,
}: OptimizedImageProps) {
  // Generate low-quality blur placeholder if not provided
  const placeholder = blurDataURL ? "blur" : "empty";

  return (
    <div
      className={cn(
        "relative overflow-hidden",
        fill ? "absolute inset-0" : "",
        containerClassName,
      )}
      style={
        !fill && width && height
          ? { aspectRatio: `${width}/${height}` }
          : undefined
      }
    >
      <Image
        src={src}
        alt={alt}
        fill={fill}
        width={!fill ? width : undefined}
        height={!fill ? height : undefined}
        priority={priority}
        loading={priority ? "eager" : "lazy"}
        quality={quality}
        placeholder={placeholder}
        blurDataURL={blurDataURL}
        sizes={sizes}
        className={cn(
          "transition-opacity duration-300",
          objectFit === "cover" && "object-cover",
          objectFit === "contain" && "object-contain",
          objectFit === "fill" && "object-fill",
          objectFit === "none" && "object-none",
          objectFit === "scale-down" && "object-scale-down",
          className,
        )}
        onLoad={onLoad}
        onError={onError}
      />
    </div>
  );
}

interface ResponsiveImageProps extends Omit<
  OptimizedImageProps,
  "width" | "height"
> {
  aspectRatio?: string;
  maxWidth?: number;
}

/**
 * Responsive Image with Aspect Ratio
 * Maintains aspect ratio while being responsive
 */
export function ResponsiveImage({
  aspectRatio = "16/9",
  maxWidth = 1200,
  className,
  containerClassName,
  ...props
}: ResponsiveImageProps) {
  return (
    <div
      className={cn("w-full", containerClassName)}
      style={{ maxWidth, aspectRatio }}
    >
      <OptimizedImage
        {...props}
        fill
        className={className}
        sizes={`(max-width: ${maxWidth}px) 100vw, ${maxWidth}px`}
      />
    </div>
  );
}

interface AvatarProps {
  src?: string | null;
  alt: string;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  fallback?: string;
  className?: string;
}

const sizeMap = {
  xs: 24,
  sm: 32,
  md: 40,
  lg: 48,
  xl: 64,
};

/**
 * Optimized Avatar Component
 * Perfect for user lists, team pages, etc.
 */
export function OptimizedAvatar({
  src,
  alt,
  size = "md",
  fallback,
  className,
}: AvatarProps) {
  const sizePx = sizeMap[size];
  const initials = fallback || alt.slice(0, 2).toUpperCase();

  if (!src) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-full bg-primary text-primary-foreground font-medium",
          className,
        )}
        style={{ width: sizePx, height: sizePx, fontSize: sizePx * 0.4 }}
      >
        {initials}
      </div>
    );
  }

  return (
    <OptimizedImage
      src={src}
      alt={alt}
      width={sizePx}
      height={sizePx}
      className={cn("rounded-full object-cover", className)}
      containerClassName={cn("rounded-full overflow-hidden", className)}
    />
  );
}

interface IconSpriteProps {
  name: string;
  size?: number;
  className?: string;
}

/**
 * SVG Icon Sprite Component
 * Reduces HTTP requests by using sprite sheets
 */
export function IconSprite({ name, size = 24, className }: IconSpriteProps) {
  return (
    <svg
      width={size}
      height={size}
      className={cn("fill-current", className)}
      aria-hidden="true"
    >
      <use href={`/icons/sprite.svg#${name}`} />
    </svg>
  );
}

// Preload critical images
export const preloadCriticalImages = (imageUrls: string[]) => {
  if (typeof window === "undefined") return;

  imageUrls.forEach((url) => {
    const link = document.createElement("link");
    link.rel = "preload";
    link.as = "image";
    link.href = url;
    document.head.appendChild(link);
  });
};

// Image optimization utilities
export const imageUtils = {
  /**
   * Generate blur data URL for placeholder
   */
  generateBlurDataURL: (width: number = 10, height: number = 10): string => {
    // Simple SVG-based blur placeholder
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}">
        <rect width="100%" height="100%" fill="#e5e7eb"/>
      </svg>
    `;
    return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
  },

  /**
   * Get optimal image size for viewport
   */
  getOptimalSize: (viewportWidth: number): number => {
    const sizes = [640, 750, 828, 1080, 1200, 1920, 2048];
    return (
      sizes.find((size) => size >= viewportWidth) || sizes[sizes.length - 1]
    );
  },

  /**
   * Convert image to WebP format hint
   */
  getWebPUrl: (url: string): string => {
    if (url.endsWith(".webp")) return url;
    if (url.includes("?")) return `${url}&format=webp`;
    return `${url}?format=webp`;
  },
};

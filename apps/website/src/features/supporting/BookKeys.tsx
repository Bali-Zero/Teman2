"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Arrow shortcuts supplement ordinary links; never capture input or component navigation. */
export function BookKeys({
  previous,
  next,
}: {
  previous?: string;
  next?: string;
}) {
  const router = useRouter();
  useEffect(() => {
    function navigate(event: KeyboardEvent) {
      if (
        event.altKey ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.defaultPrevented
      )
        return;
      if (
        event.target instanceof Element &&
        event.target.closest(
          "input,textarea,select,button,a,summary,[contenteditable=true]",
        )
      )
        return;
      const href =
        event.key === "ArrowLeft"
          ? previous
          : event.key === "ArrowRight"
            ? next
            : undefined;
      if (href) {
        event.preventDefault();
        router.push(href);
      }
    }
    document.addEventListener("keydown", navigate);
    return () => document.removeEventListener("keydown", navigate);
  }, [previous, next, router]);
  return null;
}

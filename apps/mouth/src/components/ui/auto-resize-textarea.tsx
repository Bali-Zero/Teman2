"use client";

import React, { useLayoutEffect, forwardRef, useImperativeHandle, useRef, TextareaHTMLAttributes } from "react";
import { UI } from "@/constants";

interface AutoResizeTextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  value: string;
  maxHeight?: number;
}

/**
 * A textarea component that automatically adjusts its height based on content.
 * Prevents visual flickering by using useLayoutEffect to recalculate height before paint.
 */
export const AutoResizeTextarea = forwardRef<HTMLTextAreaElement, AutoResizeTextareaProps>(
  ({ value, className, maxHeight = UI.MAX_TEXTAREA_HEIGHT, ...props }, ref) => {
    const internalRef = useRef<HTMLTextAreaElement>(null);

    // Expose the internal textarea ref to parent components
    useImperativeHandle(ref, () => internalRef.current as HTMLTextAreaElement);

    // Recalculate height whenever value changes to match content
    useLayoutEffect(() => {
      const textarea = internalRef.current;
      if (textarea) {
        textarea.style.height = "auto";
        const newHeight = Math.min(textarea.scrollHeight, maxHeight);
        textarea.style.height = `${newHeight}px`;

        // Show scrollbar only if content exceeds maxHeight
        textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
      }
    }, [value, maxHeight]);

    return (
      <textarea
        ref={internalRef}
        value={value}
        className={`overflow-hidden resize-none ${className || ""}`}
        {...props}
      />
    );
  }
);

AutoResizeTextarea.displayName = "AutoResizeTextarea";

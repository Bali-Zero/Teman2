"use client";

import { useLayoutEffect, TextareaHTMLAttributes, forwardRef, useRef, useImperativeHandle } from "react";
import { UI } from "@/constants";

interface AutoResizeTextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  value: string;
  maxHeight?: number;
}

export const AutoResizeTextarea = forwardRef<HTMLTextAreaElement, AutoResizeTextareaProps>(
  ({ value, className, maxHeight = UI.MAX_TEXTAREA_HEIGHT, ...props }, ref) => {
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Provide the underlying textarea element to the forwarded ref
    useImperativeHandle(ref, () => textareaRef.current as HTMLTextAreaElement);

    // useLayoutEffect prevents visual flicker by recalculating height before paint
    useLayoutEffect(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, maxHeight)}px`;
      }
    }, [value, maxHeight]);

    return (
      <textarea
        ref={textareaRef}
        value={value}
        className={`overflow-hidden resize-none ${className || ""}`}
        {...props}
      />
    );
  }
);

AutoResizeTextarea.displayName = "AutoResizeTextarea";

"use client";

import { useRef, useLayoutEffect, TextareaHTMLAttributes } from "react";

interface AutoResizeTextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  value: string;
}

export function AutoResizeTextarea({
  value,
  className,
  ...props
}: AutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // useLayoutEffect elimina il "flicker" visivo ricalcolando l'altezza prima del paint
  useLayoutEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [value]);

  return (
    <textarea
      ref={textareaRef}
      value={value}
      className={`overflow-hidden resize-none ${className || ""}`}
      {...props}
    />
  );
}

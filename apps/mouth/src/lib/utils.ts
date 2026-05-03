import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMessageTime(date: Date): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "numeric",
    hour12: true,
  }).format(date);
}

/**
 * Renderizza un sottoinsieme sicuro di Markdown (Bold, Link, Newlines).
 * Ideale per visualizzare output AI senza rischi XSS completi.
 */
export const renderMiniMarkdown = (text: string | undefined) => {
  if (!text) return { __html: "" };

  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // **Bold** -> <strong>
  html = html.replace(
    /\*\*(.+?)\*\*/g,
    '<strong class="text-white font-semibold">$1</strong>',
  );

  // [Link](url) -> <a> (stilizzato viola Bali Zero)
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-[#6366f1] hover:text-white border-b border-[#6366f1]/40 hover:border-[#6366f1] transition-colors pb-[1px] decoration-0">$1</a>',
  );

  // Newline -> <br>
  html = html.replace(/\n/g, "<br />");
  return { __html: html };
};

export const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

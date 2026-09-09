import { retainedPath } from "../../lib/retained-routes";
import { retainedImage } from "../../lib/retained-assets";
import { isArticleSlug } from "../../lib/article-slug";
import { isJournalCategory } from "../../content/journal-categories";

/** Preserve native article editions and the guarded local tool boundaries. */
export function safeArticleUrl(value: string): string {
  try {
    const url = new URL(value, "https://balizero.com");
    // Authored contact links open a draft in the reader's email app. Decode the
    // recipient before checking it so encoded header delimiters cannot pass.
    if (url.protocol === "mailto:") {
      const recipient = decodeURIComponent(url.pathname);
      return /^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$/.test(recipient) && !url.hash ? url.href : "";
    }
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return "";
    if (value.startsWith("#")) return value;
    if (url.origin === "https://balizero.com") {
      const edition = url.pathname.match(/^\/(en|id|it|fr|ru)\/insights\/([^/]+)\/([^/]+)\/?$/);
      if (edition && isJournalCategory(edition[2]) && isArticleSlug(edition[3])) return `/${edition[2]}/${edition[3]}?lang=${edition[1]}${url.hash}`;
      const path = url.pathname.replace(/^\/insights\//, "/");
      if (retainedPath(path)) return path + url.search + url.hash;
      const parts = path.replace(/\/$/, "").split("/");
      if (isJournalCategory(parts[1]) && (parts.length === 2 || parts.length === 3 && isArticleSlug(parts[2]))) return path + url.search + url.hash;
    }
    return url.href;
  } catch { return ""; }
}
export function safeArticleImage(value: string): string {
  return retainedImage(value)?.src ?? "";
}

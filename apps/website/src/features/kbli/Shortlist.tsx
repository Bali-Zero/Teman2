"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import type { CatalogItem } from "./types";
import styles from "./kbli.module.css";

const KEY = "bz-kbli-shortlist-v1";
const EVENT = "bz-kbli-shortlist";
const EMPTY = "[]";
function subscribe(update: () => void): () => void {
  window.addEventListener(EVENT, update);
  window.addEventListener("storage", update);
  return () => {
    window.removeEventListener(EVENT, update);
    window.removeEventListener("storage", update);
  };
}
function snapshot(): string {
  try {
    return localStorage.getItem(KEY) ?? EMPTY;
  } catch {
    return EMPTY;
  }
}
export function parseShortlist(raw: string): string[] {
  try {
    const codes: unknown = JSON.parse(raw);
    return Array.isArray(codes)
      ? [
          ...new Set(
            codes.filter(
              (code): code is string =>
                typeof code === "string" && /^\d{5}$/.test(code),
            ),
          ),
        ].slice(0, 6)
      : [];
  } catch {
    return [];
  }
}
function update(codes: string[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(codes));
  } catch {
    /* Browsing still works if storage is disabled. */
  }
  window.dispatchEvent(new Event(EVENT));
}
function useCodes(): string[] {
  return parseShortlist(useSyncExternalStore(subscribe, snapshot, () => EMPTY));
}

export function ShortlistButton({ code }: { code: string }) {
  const codes = useCodes();
  const selected = codes.includes(code);
  return (
    <button
      type="button"
      className={styles.save}
      aria-pressed={selected}
      disabled={!selected && codes.length >= 6}
      onClick={() =>
        update(
          selected ? codes.filter((item) => item !== code) : [...codes, code],
        )
      }
    >
      {selected ? "✓ Shortlisted" : "＋ Shortlist"}
    </button>
  );
}

export function Shortlist({ expanded = false }: { expanded?: boolean }) {
  const codes = useCodes();
  const key = codes.join(",");
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [state, setState] = useState("idle");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!expanded || !key) return;
    const controller = new AbortController();
    fetch(`/api/kbli/search?codes=${key}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("unavailable");
        const data = (await response.json()) as { items: CatalogItem[] };
        setItems(data.items);
        setState("ready");
      })
      .catch(() => {
        if (!controller.signal.aborted) setState("error");
      });
    return () => controller.abort();
  }, [key, expanded]);
  const selected = items.filter((item) => codes.includes(item.code));
  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(
        `KBLI research shortlist\n${selected.map((item) => `${item.code} — ${item.title}\nOwnership: ${item.ownership}\nBali: ${item.bali}\nLicensing: ${item.licensingPending ? "Verification pending; indicative rows" : item.licenses.join(", ")}`).join("\n\n")}\n\nActivity scope, ownership, scale and location still need a joint review.`,
      );
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <section className={styles.shortlist} aria-label="Your KBLI shortlist">
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.eyebrow}>Your working selection</span>
          <h2>
            {expanded
              ? "Compare your activities."
              : `${codes.length} of 6 codes shortlisted`}
          </h2>
        </div>
        {!expanded && (
          <a className={styles.textLink} href="/kbli/builder">
            Open comparison →
          </a>
        )}
      </div>
      {!codes.length ? (
        <p>
          Use “Shortlist” on a result or code page. Compare up to six activities
          side by side. Only code numbers are saved in this browser.
        </p>
      ) : (
        <>
          <div className={styles.chips}>
            {codes.map((code) => (
              <button
                key={code}
                className={styles.chip}
                onClick={() => update(codes.filter((item) => item !== code))}
                aria-label={`Remove ${code} from shortlist`}
              >
                {code} ×
              </button>
            ))}
            <button className={styles.textButton} onClick={() => update([])}>
              Clear all
            </button>
          </div>
          {expanded && (
            <>
              {state === "error" ? (
                <p role="alert">
                  The comparison could not load. Open an individual code below
                  or reload this page.
                </p>
              ) : selected.length ? (
                <div className={styles.tableScroll}>
                  <table className={styles.compare}>
                    <caption>
                      Source-backed comparison. A shortlist does not establish
                      licence or ownership eligibility.
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Check</th>
                        {selected.map((item) => (
                          <th key={item.code} scope="col">
                            <a href={`/kbli/${item.code}`}>
                              {item.code}
                              <span>{item.title}</span>
                            </a>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        [
                          "Foreign ownership",
                          (item: CatalogItem) => item.ownership,
                        ],
                        ["Bali", (item: CatalogItem) => item.bali],
                        [
                          "Risk by recorded scale",
                          (item: CatalogItem) =>
                            item.risks.length
                              ? `${item.risks.join(" / ")}${item.licensingPending ? " · verification pending" : ""}`
                              : "No standard risk rows",
                        ],
                        [
                          "Recorded licences",
                          (item: CatalogItem) =>
                            `${item.licenses.join(" / ") || "No standard licensing rows"}${item.licensingInherited.length ? ` · inherited from ${item.licensingInherited.join(", ")}` : ""}`,
                        ],
                      ].map(([label, value]) => (
                        <tr key={label as string}>
                          <th scope="row">{label as string}</th>
                          {selected.map((item) => (
                            <td key={item.code}>
                              {(value as (item: CatalogItem) => string)(item)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p role="status">Loading the selected records…</p>
              )}
              <div className={styles.actions}>
                <button
                  className={styles.secondary}
                  onClick={copy}
                  disabled={!selected.length}
                >
                  {copied ? "Copied" : "Copy research summary"}
                </button>
                <a className={styles.primary} href="/contact?topic=company">
                  Review my activities with Bali Zero →
                </a>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}

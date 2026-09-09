"use client";

import { useId, useState } from "react";
import styles from "./ArticleReader.module.css";

/** Public display strings only; no source component props cross this boundary. */
export function ArticleGlossary({ label, definition, indonesian, related }: { label: string; definition: string; indonesian: string; related: string[] }) {
  const id = useId(), [expanded, setExpanded] = useState(false);
  if (!definition && !indonesian && !related.length) return <dfn>{label}</dfn>;
  return <span className={styles.inlineGlossary} onKeyDown={(event) => { if (event.key === "Escape") setExpanded(false); }}>
    <button type="button" aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(!expanded)}>{label}</button>
    <span id={id} hidden={!expanded} className={styles.inlineDefinition}>
      {" ("}{definition}{indonesian && indonesian !== label && indonesian !== definition ? `${definition ? " · " : ""}${indonesian}` : ""}{related.length ? ` · Related terms: ${related.join(", ")}` : ""}{")"}
    </span>
  </span>;
}

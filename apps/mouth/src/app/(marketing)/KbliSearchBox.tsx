"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const QUICK_TAGS = [
  "Villa rental",
  "Restaurant",
  "Tech startup",
  "Property",
  "Education",
];

export function KbliSearchBox() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function handleSearch(q: string) {
    const term = q.trim();
    if (!term) return;
    router.push(`/kbli?q=${encodeURIComponent(term)}`);
  }

  return (
    <div className="kbli-search-box">
      <span className="kbli-search-label">Search KBLI codes</span>
      <input
        className="kbli-input"
        type="text"
        placeholder="Search KBLI (e.g. villa, restaurant)..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSearch(query)}
      />
      <div className="kbli-tags">
        {QUICK_TAGS.map((tag) => (
          <button
            key={tag}
            className="kbli-tag"
            style={{ cursor: "pointer", border: "none", background: "none" }}
            onClick={() => handleSearch(tag)}
          >
            {tag}
          </button>
        ))}
      </div>
    </div>
  );
}

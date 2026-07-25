"use client";
import { useEffect, useState } from "react";
import { Search } from "lucide-react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function VaultSearchBar({ value, onChange, placeholder }: Props) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  useEffect(() => {
    const t = setTimeout(() => onChange(local), 200);
    return () => clearTimeout(t);
  }, [local, onChange]);
  return (
    <div className="relative">
      <Search
        aria-hidden
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
        style={{ color: "var(--bz-copper)" }}
      />
      <input
        role="searchbox"
        aria-label="Search vault files"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder ?? "Search files…"}
        className="w-full pl-10 pr-3 py-2 rounded border text-sm placeholder:text-[var(--text-tertiary,var(--tx-tertiary))] focus:border-[var(--bz-copper)] focus:outline-none"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
          color: "var(--bz-text-1)",
        }}
      />
    </div>
  );
}

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
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--bz-text-3)]"
      />
      <input
        role="searchbox"
        aria-label="Search vault files"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder ?? "Search files…"}
        className="w-full pl-10 pr-3 py-2 bg-[var(--bz-card)] rounded border border-[var(--bz-border)] text-sm text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-3)] focus-visible:border-[var(--bz-focus-ring)]"
      />
    </div>
  );
}

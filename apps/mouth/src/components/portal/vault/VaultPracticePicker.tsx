"use client";
import type { PortalMatter } from "@/lib/api/portal/portal.types";

interface Props {
  matters: readonly PortalMatter[];
  value: string | null;
  onChange: (id: string | null) => void;
}

export function VaultPracticePicker({ matters, value, onChange }: Props) {
  const mustChoose = matters.length >= 2;
  return (
    <div>
      <label
        htmlFor="vault-upload-practice"
        className="block text-[11px] uppercase tracking-[2px] text-[var(--bz-text-3)] mb-1"
      >
        Upload to practice
        {mustChoose ? " (required)" : ""}
      </label>
      <select
        id="vault-upload-practice"
        value={value ?? ""}
        onChange={(e) =>
          onChange(e.target.value === "" ? null : e.target.value)
        }
        className="w-full rounded-lg border border-[var(--bz-border)] bg-[var(--bz-card)] px-3 py-2 text-sm text-[var(--bz-text-1)] focus:border-[var(--bz-focus-ring)] focus:outline-none"
      >
        {mustChoose ? (
          <option value="">Choose a practice…</option>
        ) : (
          <option value="">No practice (general document)</option>
        )}
        {matters.map((m) => (
          <option key={m.id} value={String(m.id)}>
            {m.title}
          </option>
        ))}
      </select>
    </div>
  );
}

"use client";

interface Props {
  navigateOnSubmit?: boolean;
  autoFocus?: boolean;
}

export function KBLISearch({ navigateOnSubmit, autoFocus }: Props) {
  return (
    <div className="relative">
      <input
        type="text"
        placeholder="Search KBLI codes..."
        className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--background)]"
        autoFocus={autoFocus}
      />
    </div>
  );
}

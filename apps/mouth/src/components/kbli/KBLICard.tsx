interface KBLICode {
  code: string;
  name: string;
  description?: string;
}

interface Props {
  code: KBLICode;
  showTransition?: boolean;
}

export function KBLICard({ code, showTransition }: Props) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-4">
      <div className="font-semibold">{code.code}</div>
      <div className="text-sm text-[var(--foreground-muted)]">{code.name}</div>
    </div>
  );
}

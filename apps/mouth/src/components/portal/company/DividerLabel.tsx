export function DividerLabel({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-4 my-10">
      <div className="flex-1 h-px bg-[var(--kbli-border)]" />
      <span className="text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--kbli-text-muted)] whitespace-nowrap">
        {text}
      </span>
      <div className="flex-1 h-px bg-[var(--kbli-border)]" />
    </div>
  );
}

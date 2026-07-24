"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ProcessStep } from "@/lib/schemas/process";
import { StateBadge } from "./StateBadge";

interface Props {
  step: ProcessStep | null;
  open: boolean;
  onClose: () => void;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

// WS3 slice 4 (GARUDA Day Edition, 2026-07-24): drawer surface reads
// --bz-elevated / --bz-border-accent (was hardcoded #0a0804 + copper hex
// borders — a pitch-black drawer on the warm-paper page); scrim reads
// --surface-scrim; label text reads --bz-copper-text with the slice-1
// fallback; values read --tx-primary.
export function StepDetailDrawer({ step, open, onClose }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 backdrop-blur-sm z-40"
          style={{ background: "var(--surface-scrim, rgba(0,0,0,0.6))" }}
        />
        <Dialog.Content className="fixed right-0 top-0 bottom-0 w-full max-w-[480px] bg-[var(--bz-elevated)] border-l border-[var(--bz-border-accent)] z-50 overflow-y-auto flex flex-col">
          <div className="p-6 flex items-center justify-between border-b border-[var(--bz-border)]">
            <Dialog.Title className="text-lg font-medium text-[var(--tx-pure)]">
              {step?.label ?? "—"}
            </Dialog.Title>
            <Dialog.Close
              className="p-2 rounded hover:bg-[var(--glass-highlight)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent-warm)]"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </Dialog.Close>
          </div>

          {step && (
            <div className="p-6 space-y-4 flex-1">
              <StateBadge state={step.status} label={step.label} />

              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] mb-1">
                    Status
                  </dt>
                  <dd className="text-[var(--tx-primary)]">{step.label}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] mb-1">
                    Completed
                  </dt>
                  <dd className="text-[var(--tx-primary)]">
                    {step.completed ? "Yes" : "No"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] mb-1">
                    Current step
                  </dt>
                  <dd className="text-[var(--tx-primary)]">
                    {step.is_current ? "Yes" : "No"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] mb-1">
                    Changed at
                  </dt>
                  <dd className="text-[var(--tx-primary)]">
                    {formatDate(step.changed_at)}
                  </dd>
                </div>
                {step.changed_by && (
                  <div>
                    <dt className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] mb-1">
                      Changed by
                    </dt>
                    <dd className="text-[var(--tx-primary)]">
                      {step.changed_by}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          <Dialog.Description className="sr-only">
            Detailed information about a step in the practice timeline.
          </Dialog.Description>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

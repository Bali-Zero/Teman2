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

export function StepDetailDrawer({ step, open, onClose }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" />
        <Dialog.Content className="fixed right-0 top-0 bottom-0 w-full max-w-[480px] bg-[#0a0804] border-l border-[#c9a96e]/20 z-50 overflow-y-auto flex flex-col">
          <div className="p-6 flex items-center justify-between border-b border-[#c9a96e]/10">
            <Dialog.Title className="text-lg font-medium text-[#f0ece4]">
              {step?.label ?? "—"}
            </Dialog.Title>
            <Dialog.Close
              className="p-2 rounded hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-[#c9a96e]"
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
                  <dt className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-1">
                    Status
                  </dt>
                  <dd className="text-[#f0ece4]">{step.label}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-1">
                    Completed
                  </dt>
                  <dd className="text-[#f0ece4]">
                    {step.completed ? "Yes" : "No"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-1">
                    Current step
                  </dt>
                  <dd className="text-[#f0ece4]">
                    {step.is_current ? "Yes" : "No"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-1">
                    Changed at
                  </dt>
                  <dd className="text-[#f0ece4]">
                    {formatDate(step.changed_at)}
                  </dd>
                </div>
                {step.changed_by && (
                  <div>
                    <dt className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-1">
                      Changed by
                    </dt>
                    <dd className="text-[#f0ece4]">{step.changed_by}</dd>
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

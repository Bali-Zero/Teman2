"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandPalette, type CommandAction } from "@balizero/core";

/**
 * Workspace-wide Cmd+K command palette for /kita.
 * Actions: navigation + practice-creation shortcuts + external (Prime).
 */
export function KitaCommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const actions: CommandAction[] = useMemo(
    () => [
      {
        id: "go-inbox",
        label: "Vai a Inbox",
        group: "Navigazione",
        run: () => router.push("/inbox"),
      },
      {
        id: "go-clients",
        label: "Clienti",
        group: "Navigazione",
        run: () => router.push("/clients"),
      },
      {
        id: "go-process",
        label: "Pratiche",
        group: "Navigazione",
        run: () => router.push("/process"),
      },
      {
        id: "go-prime",
        label: "Apri Prime 3D",
        group: "Navigazione",
        run: () => window.open("https://prime.balizero.com/", "_blank", "noopener"),
      },
      {
        id: "create-kitas",
        label: "Crea pratica KITAS",
        group: "Pratiche",
        run: () => router.push("/process/new?type=kitas"),
      },
      {
        id: "create-pt",
        label: "Crea pratica PT Setup",
        group: "Pratiche",
        run: () => router.push("/process/new?type=pt_setup"),
      },
      {
        id: "export-lkpm",
        label: "Esporta LKPM Q1",
        group: "Tax",
        run: () => router.push("/lkpm"),
      },
      {
        id: "open-analytics",
        label: "Analytics funnel",
        group: "Analytics",
        run: () => router.push("/analytics/funnel"),
      },
    ],
    [router],
  );

  return (
    <CommandPalette open={open} actions={actions} onClose={() => setOpen(false)} />
  );
}

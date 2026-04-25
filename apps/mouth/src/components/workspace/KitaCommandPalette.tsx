"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandPalette, type CommandAction } from "@balizero/core";
import { useTranslation } from "@/i18n";

/**
 * Workspace-wide Cmd+K command palette for /kita.
 * Actions: navigation + case-creation shortcuts + external (Prime).
 */
export function KitaCommandPalette() {
  const router = useRouter();
  const { t } = useTranslation();
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
        label: t("commandPalette.actions.goInbox"),
        group: t("commandPalette.groups.navigation"),
        run: () => router.push("/inbox"),
      },
      {
        id: "go-clients",
        label: t("commandPalette.actions.goClients"),
        group: t("commandPalette.groups.navigation"),
        run: () => router.push("/clients"),
      },
      {
        id: "go-process",
        label: t("commandPalette.actions.goProcess"),
        group: t("commandPalette.groups.navigation"),
        run: () => router.push("/process"),
      },
      {
        id: "go-prime",
        label: t("commandPalette.actions.goPrime"),
        group: t("commandPalette.groups.navigation"),
        run: () => window.open("https://prime.balizero.com/", "_blank", "noopener"),
      },
      {
        id: "create-kitas",
        label: t("commandPalette.actions.createKitas"),
        group: t("commandPalette.groups.cases"),
        run: () => router.push("/process/new?type=kitas"),
      },
      {
        id: "create-pt",
        label: t("commandPalette.actions.createPtSetup"),
        group: t("commandPalette.groups.cases"),
        run: () => router.push("/process/new?type=pt_setup"),
      },
      {
        id: "export-lkpm",
        label: t("commandPalette.actions.exportLkpm"),
        group: t("commandPalette.groups.tax"),
        run: () => router.push("/lkpm"),
      },
      {
        id: "open-analytics",
        label: t("commandPalette.actions.openAnalytics"),
        group: t("commandPalette.groups.analytics"),
        run: () => router.push("/analytics/funnel"),
      },
    ],
    [router, t],
  );

  return (
    <CommandPalette open={open} actions={actions} onClose={() => setOpen(false)} />
  );
}

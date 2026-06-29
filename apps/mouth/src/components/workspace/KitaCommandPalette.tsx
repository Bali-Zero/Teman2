"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandPalette, type CommandAction } from "@balizero/core";
import { useTranslation } from "@/i18n";
import { api } from "@/lib/api";
import { isCRMAdmin } from "@/lib/crm/admin";

// /inbox is owner-only (Zero) — keep its palette shortcut off everyone else.
const INBOX_OWNER_EMAIL = "zero@balizero.com";

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

  const profile = api.getUserProfile();
  const isInboxOwner =
    (profile?.email || "").toLowerCase() === INBOX_OWNER_EMAIL;
  const isAccountingAdmin = isCRMAdmin(profile);

  const actions: CommandAction[] = useMemo(
    () => [
      ...(isInboxOwner
        ? [
            {
              id: "go-inbox",
              label: t("commandPalette.actions.goInbox"),
              group: t("commandPalette.groups.navigation"),
              run: () => router.push("/inbox"),
            },
          ]
        : []),
      ...(isAccountingAdmin
        ? [
            {
              id: "go-accounting",
              label: "Accounting · Weekly Cashout",
              group: t("commandPalette.groups.navigation"),
              run: () => router.push("/accounting"),
            },
          ]
        : []),
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
        run: () =>
          window.open("https://prime.balizero.com/", "_blank", "noopener"),
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
    [router, t, isInboxOwner, isAccountingAdmin],
  );

  return (
    <CommandPalette
      open={open}
      actions={actions}
      onClose={() => setOpen(false)}
    />
  );
}

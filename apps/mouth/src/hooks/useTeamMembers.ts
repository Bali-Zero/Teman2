"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface TeamMember {
  id: string | null;
  email: string;
  full_name: string;
  name: string;
  role: string;
  avatar_url: string | null;
  avatar: string | null;
}

// Mirrors backend/app/utils/service_accounts.py NON_HUMAN_ROLES — a role that
// is not a client is not automatically a colleague. "monitoring" is the
// login-healthcheck probe: it authenticates like a team member every 5
// minutes and must never appear in a human-facing roster or assignment list.
// Keep in sync with the Python SSOT if a new service role is ever added.
const NON_HUMAN_ROLES = new Set(["client", "monitoring"]);

export function isNonHumanRole(role: string | null | undefined): boolean {
  return NON_HUMAN_ROLES.has((role ?? "").trim().toLowerCase());
}

// Mirrors backend/app/utils/service_accounts.py TEAM_ROLES — the ALLOW-list the
// team gate (require_team_member) admits, normalised. A role absent here is not
// a colleague, whatever else it is. Keep in sync with the Python SSOT; the
// backend tripwire test_service_accounts_ts_sync.py compares both sets.
const TEAM_ROLES = new Set([
  "admin",
  "team",
  "founder",
  "ceo",
  "board member",
  "team leader",
  "supervisor",
  "tax lead",
  "tax manager",
  "tax care",
  "accounting",
  "marketing & accounting",
  "marketing advisory",
  "executive consultant",
  "specialist advisor",
  "junior consultant",
  "consultant",
  "reception",
  "member",
]);

export function isTeamRole(role: string | null | undefined): boolean {
  return TEAM_ROLES.has((role ?? "").trim().toLowerCase());
}

async function fetchTeamMembers(): Promise<TeamMember[]> {
  const res = await api.get<TeamMember[] | { members: TeamMember[] }>(
    "/api/team/members",
  );
  // Backend returns array directly; handle both formats for safety
  return Array.isArray(res) ? res : res.members;
}

export function useTeamMembers() {
  return useQuery({
    queryKey: ["team-members"],
    queryFn: fetchTeamMembers,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

export function useTeamMemberOptions() {
  const { data: members = [], ...rest } = useTeamMembers();
  // Stabilize reference — without useMemo, filter+map creates a new array every render,
  // causing infinite re-render loops in consumers that depend on this in useEffect deps
  const options = useMemo(() => {
    const uniqueMembers = new Map<
      string,
      TeamMember & { normalizedEmail: string; displayName: string }
    >();

    for (const member of members) {
      const normalizedEmail = member.email.trim().toLowerCase();
      if (
        !normalizedEmail ||
        isNonHumanRole(member.role) ||
        uniqueMembers.has(normalizedEmail)
      ) {
        continue;
      }
      uniqueMembers.set(normalizedEmail, {
        ...member,
        normalizedEmail,
        displayName:
          member.full_name?.trim() || member.name?.trim() || normalizedEmail,
      });
    }

    const labelCounts = new Map<string, number>();
    for (const member of uniqueMembers.values()) {
      const key = member.displayName.toLowerCase();
      labelCounts.set(key, (labelCounts.get(key) ?? 0) + 1);
    }

    return Array.from(uniqueMembers.values()).map((member) => ({
      value: member.normalizedEmail,
      label:
        (labelCounts.get(member.displayName.toLowerCase()) ?? 0) > 1
          ? `${member.displayName} (${member.normalizedEmail})`
          : member.displayName,
      avatar: member.avatar_url ?? member.avatar ?? undefined,
    }));
  }, [members]);
  return { options, ...rest };
}

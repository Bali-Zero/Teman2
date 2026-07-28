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
        member.role?.trim().toLowerCase() === "client" ||
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

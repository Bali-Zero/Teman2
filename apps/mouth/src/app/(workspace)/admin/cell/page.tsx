"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSessionState } from "@/hooks/useSessionState";
import { CellDashboard } from "@/components/cell/CellDashboard";

export default function CellPage() {
  const router = useRouter();
  const session = useSessionState();

  useEffect(() => {
    if (session === "anonymous") {
      router.push("/login");
      return;
    }
    if (session !== "authenticated") return;
    if (!api.isAdmin()) {
      router.push("/chat");
      return;
    }
  }, [session, router]);

  return <CellDashboard />;
}

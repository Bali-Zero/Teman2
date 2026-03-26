"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { CellDashboard } from "@/components/cell/CellDashboard";

export default function CellPage() {
  const router = useRouter();

  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push("/login");
      return;
    }
    if (!api.isAdmin()) {
      router.push("/chat");
      return;
    }
  }, [router]);

  return <CellDashboard />;
}

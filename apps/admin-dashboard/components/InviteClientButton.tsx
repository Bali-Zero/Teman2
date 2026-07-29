"use client";

import { useState, useEffect } from "react";
import {
  Send,
  RotateCcw,
  CheckCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Button, Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";

interface Invitation {
  id: number;
  status: "pending" | "used" | "expired";
  created_at: string;
  email: string;
}

interface InviteClientButtonProps {
  clientId: number;
  clientEmail: string;
  clientName?: string;
}

type ButtonState = "idle" | "loading" | "success" | "error" | "already_sent";

const STATUS_COLORS: Record<Invitation["status"], string> = {
  pending: "bg-yellow-100 text-yellow-800",
  used: "bg-green-100 text-green-800",
  expired: "bg-red-100 text-red-800",
};

export function InviteClientButton({
  clientId,
  clientEmail,
}: InviteClientButtonProps) {
  const [state, setState] = useState<ButtonState>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`/api/portal/invite?clientId=${clientId}`);
        if (res.ok) {
          const data = await res.json();
          const list: Invitation[] = data?.data ?? [];
          setInvitations(list);
          if (list.some((i) => i.status === "pending"))
            setState("already_sent");
        }
      } catch (e) {
        logger.error("Failed to load invite history", e);
      } finally {
        setHistoryLoaded(true);
      }
    };
    fetchHistory();
  }, [clientId]);

  const sendInvite = async () => {
    setState("loading");
    setErrorMsg(null);
    try {
      const res = await fetch("/api/portal/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, email: clientEmail }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail ?? data.error ?? "Unknown error");
      }
      setState("success");
      const histRes = await fetch(`/api/portal/invite?clientId=${clientId}`);
      if (histRes.ok) {
        const histData = await histRes.json();
        setInvitations(histData?.data ?? []);
      }
      setTimeout(() => setState("already_sent"), 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to send invitation";
      logger.error("Invite send failed:", e);
      setErrorMsg(msg);
      setState("error");
      setTimeout(
        () =>
          setState(
            invitations.some((i) => i.status === "pending")
              ? "already_sent"
              : "idle",
          ),
        4000,
      );
    }
  };

  if (!historyLoaded) {
    return (
      <Button variant="outline" size="sm" disabled>
        <Loader2 className="h-3 w-3 animate-spin mr-1" />
        <span className="text-xs">Loading...</span>
      </Button>
    );
  }

  if (invitations.some((i) => i.status === "used")) {
    return (
      <Badge className="bg-green-100 text-green-800 text-xs">
        <CheckCircle className="h-3 w-3 mr-1" />
        Portal Active
      </Badge>
    );
  }

  if (state === "success") {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled
        className="text-green-700 border-green-300"
      >
        <CheckCircle className="h-3 w-3 mr-1" />
        <span className="text-xs">Invite Sent!</span>
      </Button>
    );
  }

  if (state === "error") {
    return (
      <div className="flex flex-col gap-1">
        <Button
          variant="outline"
          size="sm"
          onClick={sendInvite}
          className="text-red-700 border-red-300"
        >
          <AlertCircle className="h-3 w-3 mr-1" />
          <span className="text-xs">Retry</span>
        </Button>
        {errorMsg && (
          <span className="text-[10px] text-red-600 max-w-[180px] truncate">
            {errorMsg}
          </span>
        )}
      </div>
    );
  }

  if (state === "already_sent") {
    return (
      <div className="flex items-center gap-2">
        <Badge className={cn("text-xs", STATUS_COLORS.pending)}>Pending</Badge>
        <Button
          variant="outline"
          size="sm"
          onClick={sendInvite}
          title="Resend invite"
        >
          <RotateCcw className="h-3 w-3" />
          <span className="text-xs ml-1">Resend</span>
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={sendInvite}
      disabled={state === "loading"}
      className="hover:border-blue-400 hover:text-blue-700"
    >
      {state === "loading" ? (
        <Loader2 className="h-3 w-3 animate-spin mr-1" />
      ) : (
        <Send className="h-3 w-3 mr-1" />
      )}
      <span className="text-xs">Invite to Portal</span>
    </Button>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, ChevronDown, Loader2, Tag } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Practice } from "@/lib/api/crm/crm.types";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";

/**
 * Shown on an OPEN INQUIRY (practice_type_code === "open_inquiry"): the team
 * opened the process without picking a service and must choose it here
 * before the practice can move to Waiting Documents. The backend enforces
 * the same gate (practice_state_machine.validate_service_selected); this card
 * is the UI path that satisfies it.
 */

interface ServiceItem {
  code: string;
  name: string;
  base_price: number | null;
}

interface ServiceCategory {
  code: string;
  label: string;
  services: ServiceItem[];
}

interface SelectServiceCardProps {
  practiceId: number;
  onSaved: (practice: Practice) => void;
}

const selectClass =
  "w-full rounded-lg px-3 py-2 text-sm appearance-none cursor-pointer pr-10 focus:outline-none";
const selectStyle = {
  border: "1px solid var(--bz-border)",
  background: "var(--bz-card)",
  color: "var(--bz-text-1)",
} as const;

function formatPrice(price: number): string {
  return new Intl.NumberFormat("id-ID").format(price);
}

export function SelectServiceCard({
  practiceId,
  onSaved,
}: SelectServiceCardProps) {
  const [catalog, setCatalog] = useState<ServiceCategory[]>([]);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(true);
  const [category, setCategory] = useState("");
  const [serviceCode, setServiceCode] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.crm
      .getPracticeTypesCatalog()
      .then((data) => {
        if (!cancelled) setCatalog(data.categories);
      })
      .catch((err) => {
        logger.error(
          "Failed to load practice types catalog",
          { component: "SelectServiceCard", action: "loadCatalog" },
          toError(err),
        );
        toast.error("Failed to load service catalog");
      })
      .finally(() => {
        if (!cancelled) setIsLoadingCatalog(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const services = useMemo(
    () => catalog.find((c) => c.code === category)?.services ?? [],
    [catalog, category],
  );
  const selected = useMemo(
    () => services.find((s) => s.code === serviceCode) ?? null,
    [services, serviceCode],
  );

  const save = async () => {
    if (!selected) return;
    setIsSaving(true);
    try {
      const updated = await api.crm.updatePractice(practiceId, {
        practice_type_code: selected.code,
        ...(selected.base_price ? { quoted_price: selected.base_price } : {}),
      });
      onSaved(updated);
      toast.success("Service set", { description: selected.name });
    } catch (err) {
      toast.error("Failed to set service", {
        description: (err as Error).message,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div
      className="rounded-xl p-5 mb-6"
      style={{
        border: "1px solid var(--state-warning)",
        background:
          "color-mix(in srgb, var(--state-warning) 8%, var(--bz-card))",
      }}
      data-testid="select-service-card"
    >
      <div className="flex items-start gap-3 mb-4">
        <AlertCircle
          className="w-5 h-5 mt-0.5 flex-shrink-0"
          style={{ color: "var(--state-warning)" }}
        />
        <div>
          <h2
            className="text-base font-semibold"
            style={{ color: "var(--bz-text-1)" }}
          >
            Open inquiry — service not chosen yet
          </h2>
          <p className="text-sm mt-0.5" style={{ color: "var(--bz-text-2)" }}>
            Pick the service to move this process to Waiting Documents.
          </p>
        </div>
      </div>

      {isLoadingCatalog ? (
        <div
          className="flex items-center gap-2 text-sm py-2"
          style={{ color: "var(--bz-text-2)" }}
        >
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading services...
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
          <div className="relative">
            <Tag
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none"
              style={{ color: "var(--bz-text-2)" }}
            />
            <ChevronDown
              className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none"
              style={{ color: "var(--bz-text-2)" }}
            />
            <select
              aria-label="Service category"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setServiceCode("");
              }}
              className={`${selectClass} pl-9`}
              style={selectStyle}
            >
              <option value="">-- Select category --</option>
              {catalog.map((cat) => (
                <option key={cat.code} value={cat.code}>
                  {cat.label} ({cat.services.length})
                </option>
              ))}
            </select>
          </div>
          <div className="relative">
            <ChevronDown
              className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none"
              style={{ color: "var(--bz-text-2)" }}
            />
            <select
              aria-label="Service"
              value={serviceCode}
              onChange={(e) => setServiceCode(e.target.value)}
              disabled={!category}
              className={`${selectClass} ${!category ? "opacity-50 cursor-not-allowed" : ""}`}
              style={selectStyle}
            >
              <option value="">
                {category ? "-- Select service --" : "Select category first"}
              </option>
              {services.map((svc) => (
                <option key={svc.code} value={svc.code}>
                  {svc.name}
                  {svc.base_price
                    ? ` — Rp ${formatPrice(svc.base_price)}`
                    : " — Quote"}
                </option>
              ))}
            </select>
          </div>
          <Button
            type="button"
            size="sm"
            onClick={save}
            disabled={!selected || isSaving}
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Set service
          </Button>
        </div>
      )}
    </div>
  );
}

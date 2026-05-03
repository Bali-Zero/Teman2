"use client";
import { useEffect, useState } from "react";
import {
  usePrimeNexus,
  type MapLayersState,
} from "@/contexts/PrimeNexusContext";

interface Row {
  key: keyof MapLayersState;
  label: string;
  swatch: string;
}

const ROWS: Row[] = [
  { key: "zoneColors", label: "Zone colors", swatch: "#d4845a" },
  { key: "extrusion", label: "3D extrusion", swatch: "#9fb5c9" },
  { key: "kkop", label: "KKOP (airport)", swatch: "#ff8b3d" },
  { key: "lp2b", label: "LP2B (agri)", swatch: "#5bb05b" },
  { key: "tsunami", label: "Tsunami", swatch: "#4aa3df" },
  { key: "floodRisk", label: "Flood risk", swatch: "#7986cb" },
  { key: "templeBuffer", label: "Temple buffer", swatch: "#c39bd3" },
];

const LS_KEY = "prime.legend.collapsed";

export function PrimeLayerLegend() {
  const ctx = usePrimeNexus();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const v = localStorage.getItem(LS_KEY);
    if (v === "1") setCollapsed(true);
  }, []);

  useEffect(() => {
    localStorage.setItem(LS_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  return (
    <div
      role="group"
      aria-label="Map layers"
      className="absolute top-4 left-4 z-30 rounded-2xl bg-black/85 backdrop-blur-xl border border-white/10 text-white shadow-2xl overflow-hidden"
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <span className="text-xs uppercase tracking-wider text-white/60">
          Layers
        </span>
        <button
          type="button"
          aria-label={collapsed ? "Expand legend" : "Collapse legend"}
          onClick={() => setCollapsed((c) => !c)}
          className="text-white/60 hover:text-white text-sm"
        >
          {collapsed ? "▸" : "▾"}
        </button>
      </div>
      {!collapsed && (
        <ul className="py-1">
          {ROWS.map((row) => {
            const on = ctx.layers[row.key];
            return (
              <li
                key={row.key}
                onMouseEnter={() => ctx.setHoveredLayer(row.key)}
                onMouseLeave={() => ctx.setHoveredLayer(null)}
              >
                <button
                  type="button"
                  role="switch"
                  aria-checked={on}
                  aria-label={row.label}
                  onClick={(e) => {
                    if (e.shiftKey) ctx.isolateLayer(row.key);
                    else ctx.toggleLayer(row.key);
                  }}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-left text-sm hover:bg-white/5 ${
                    on ? "text-white" : "text-white/40"
                  }`}
                >
                  <span
                    className="w-3 h-3 rounded-sm border border-white/20"
                    style={{ backgroundColor: row.swatch }}
                  />
                  <span className="flex-1">{row.label}</span>
                  <span className="text-[10px] uppercase tracking-wider text-white/30">
                    {on ? "on" : "off"}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

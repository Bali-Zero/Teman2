"use client";

import { useEffect, useState } from "react";

type Anomaly = {
  id: number;
  endpoint: string;
  current_model: string;
  proposed_model: string;
  estimated_monthly_saving_usd: number;
  confidence: string;
};

export default function AnomalyBanner() {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  useEffect(() => {
    fetch("/api/llm-costs/anomalies")
      .then((r) => r.json())
      .then((data) => setAnomalies(data.rows ?? []));
  }, []);

  if (anomalies.length === 0) return null;

  return (
    <div className="rounded-lg border border-red-800 bg-red-950/50 p-4 text-red-100">
      <div className="mb-2 text-sm font-semibold uppercase tracking-wider text-red-300">
        🚨 {anomalies.length} active cost spike(s)
      </div>
      <ul className="space-y-1 text-sm">
        {anomalies.map((a) => (
          <li key={a.id}>
            <span className="font-mono">{a.endpoint}</span> · {a.current_model} →{" "}
            <span className="font-semibold">{a.proposed_model}</span> · ~$
            {Number(a.estimated_monthly_saving_usd).toFixed(2)}/mo
          </li>
        ))}
      </ul>
    </div>
  );
}

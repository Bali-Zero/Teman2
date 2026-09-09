"use client";
import { useState } from "react";
import { AnalysisResult, EvidenceFields } from "./AnalysisResult";
import {
  projectAnalysis,
  record,
  textValue,
  numberValue,
  type Fields,
  type PropertyAnalysis,
} from "./property-contract";
import styles from "./tools.module.css";

export function Proposal({ token }: { token: string }) {
  const [state, setState] = useState("idle");
  const [data, setData] = useState<{
    fields: Fields;
    analysis: PropertyAnalysis;
  } | null>(null);
  async function open(): Promise<void> {
    setState("loading");
    try {
      const response = await fetch(
        `/api/prime/v2/proposal/${encodeURIComponent(token)}`,
        {
          method: "POST",
          cache: "no-store",
          signal: AbortSignal.timeout(20_000),
        },
      );
      const raw = record(await response.json());
      if (!response.ok) {
        setState(
          response.status === 410
            ? "expired"
            : response.status === 404
              ? "not_found"
              : "unavailable",
        );
        return;
      }
      setData({
        fields: {
          Zone: textValue(raw.zone_code),
          "Zone name": textValue(raw.zone_name),
          Latitude: numberValue(raw.lat),
          Longitude: numberValue(raw.lng),
          "KBLI code": textValue(raw.kbli_code),
          "Assessment label": textValue(raw.verdict_label),
          "Assessment score": numberValue(raw.verdict_score),
          Created: textValue(raw.created_at),
          Expires: textValue(raw.expires_at),
          Status: textValue(raw.status),
        },
        analysis: projectAnalysis(raw.analysis),
      });
      setState("ready");
    } catch {
      setState("unavailable");
    }
  }
  if (state === "ready" && data)
    return (
      <>
        <section className={styles.section}>
          <h2>The shared property record.</h2>
          <EvidenceFields data={data.fields} />
          <p className={styles.small}>
            A saved assessment reflects the records available when it was
            prepared. Check the expiry and confirm whether the site or plans
            have changed.
          </p>
        </section>
        {data.analysis.zone ? (
          <AnalysisResult result={data.analysis} />
        ) : (
          <p>The proposal has no detailed analysis snapshot.</p>
        )}
      </>
    );
  return (
    <section className={styles.proposal}>
      <p className={styles.eyebrow}>Shared property dossier</p>
      <h2>
        {state === "expired"
          ? "This proposal has expired."
          : state === "not_found"
            ? "This proposal was not found."
            : state === "unavailable"
              ? "The proposal is unavailable."
              : "Open your property proposal."}
      </h2>
      <p>
        {state === "expired" || state === "not_found"
          ? "Ask the team for a current proposal link."
          : state === "unavailable"
            ? "The proposal service is not connected or could not return this record. No proposal content has been inferred."
            : "Opening this shared link requests its saved assessment. The existing proposal service may record that it has been viewed."}
      </p>
      {!["expired", "not_found"].includes(state) && (
        <button
          className={styles.primary}
          onClick={() => void open()}
          disabled={state === "loading"}
        >
          {state === "loading"
            ? "Opening proposal…"
            : state === "unavailable"
              ? "Retry proposal"
              : "Open proposal →"}
        </button>
      )}
      <a className={styles.textLink} href="/contact?topic=property">
        Contact the property team →
      </a>
    </section>
  );
}

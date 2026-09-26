"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { BZLogo } from "@balizero/core";
import { formatIDR } from "@balizero/core/utils";
import { usePricingData } from "@/hooks/usePricingData";
import { useVoaLocale } from "./useVoaLocale";
import { voaCopy, type VoaCopyKey } from "./voa-copy";
import { mergeCheckoutHandoff, readCheckoutHandoff } from "./checkoutHandoff";
import type { OrderState, PracticeState } from "./orders/types";

/**
 * «Il banco» — the counter every VOA screen is served across (BRIEF-v2 §3.3).
 *
 * Mounted ONCE, by `layout.tsx`, around all six routes, so it is literally
 * the same element from the first question to "Delivered": a client-side
 * navigation re-renders the sheet under it and leaves the counter standing.
 * It carries three things and nothing else — the lockup, the named agent
 * (a real staff photo, never a stock face), and the ORDER STRIP: what is
 * being bought, what it costs, and where the visitor is in the purchase.
 *
 * THE PRICE HAS TWO SOURCES AND NEVER A THIRD.
 *   - Before an answer exists: the catalogue's FLOOR, read through the same
 *     path the Second Home Studio reads (`usePricingData` over the parity-
 *     tested pricing snapshot), shown as «from … all-inclusive» — owner
 *     rulings Q6/Q9 of 2026-08-27. No figure is typed in this file.
 *   - From the verdict on: the exact `price_idr` the eligibility check
 *     returned, reported by the screen that received it and kept in the tab's
 *     checkout hand-off, so the upload and checkout screens show it without
 *     asking. A screen reached in a fresh tab (the magic link opens one) asks
 *     the eligibility check again — the same GET the verdict makes, bound by
 *     the same creator cookie — and shows no price until it answers.
 *
 * Pages REPORT what they learn (`useVoaCounter().report`); they never draw
 * the strip themselves. Outside the provider — a page rendered alone in a
 * test — the report is a no-op, so no screen depends on the counter to work.
 */

export const VOA_PRICE_KEY = "B1 Visa on Arrival (VOA)";
export const VOA_PRICE_CATEGORY = "single_entry_visas";

export type VoaStage = "check" | "result" | "passport" | "payment" | "tracking";

const STAGES: { id: VoaStage; key: VoaCopyKey }[] = [
  { id: "check", key: "counter.stage.check" },
  { id: "result", key: "counter.stage.result" },
  { id: "passport", key: "counter.stage.passport" },
  { id: "payment", key: "counter.stage.payment" },
  { id: "tracking", key: "counter.stage.tracking" },
];

/** Every state word the strip can say, spelled out so no key is built at run time. */
const STATE_WORD: Record<OrderState | PracticeState, VoaCopyKey> = {
  created: "counter.state.created",
  awaiting_payment: "counter.state.awaiting_payment",
  paid: "counter.state.paid",
  failed: "counter.state.failed",
  expired: "counter.state.expired",
  refunded: "counter.state.refunded",
  Received: "counter.state.Received",
  "In review": "counter.state.In review",
  Blocked: "counter.state.Blocked",
  Submitted: "counter.state.Submitted",
  Approved: "counter.state.Approved",
  Rejected: "counter.state.Rejected",
  Delivered: "counter.state.Delivered",
};

export interface VoaOrderReport {
  resultId?: string;
  verdict?: "ACCEPT" | "DECLINE";
  priceIdr?: number;
  orderState?: OrderState;
  practiceState?: PracticeState | null;
}

interface VoaPayWording {
  review: string;
  action: string;
}

interface VoaCounterValue {
  order: VoaOrderReport;
  report: (patch: VoaOrderReport) => void;
  /** Worded by the counter, in the counter's language; null until priced. */
  pay: VoaPayWording | null;
}

const VoaCounterContext = createContext<VoaCounterValue>({
  order: {},
  report: () => {},
  pay: null,
});

export function useVoaCounter(): VoaCounterValue {
  return useContext(VoaCounterContext);
}

/** "750.000 IDR" (the snapshot's own shape) → 750000; anything else abstains. */
export function parseSnapshotIdr(price: string | null): number | null {
  if (!price) return null;
  const n = Number(price.replace(/\s*IDR$/i, "").replace(/\./g, ""));
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function stageOf(pathname: string | null): {
  stage: VoaStage;
  resultId: string | null;
} {
  const rest = (pathname ?? "")
    .replace(/^\/visa\/voa\/?/, "")
    .split("/")
    .filter(Boolean);
  const [head, id] = rest;
  if (!head) return { stage: "check", resultId: null };
  if (head === "upload") return { stage: "passport", resultId: id ?? null };
  if (head === "auth") return { stage: "passport", resultId: null };
  if (head === "checkout") return { stage: "payment", resultId: id ?? null };
  if (head === "orders") return { stage: "tracking", resultId: null };
  return { stage: "result", resultId: head };
}

/** The catalogue floor, as a number, or null when the snapshot abstains. */
export function useVoaFloorPrice(): number | null {
  const { price } = usePricingData(VOA_PRICE_KEY, VOA_PRICE_CATEGORY);
  return parseSnapshotIdr(price);
}

/**
 * The checkout's review line and the label of its one action, both carrying
 * the exact price when the counter knows it — null when it does not, so the
 * checkout keeps its own label rather than showing a price it has not got.
 * Worded inside the provider, so a screen reading it needs no router hook.
 */
export function useVoaPayWording(): VoaPayWording | null {
  return useContext(VoaCounterContext).pay;
}

export function VoaCounter({ children }: { children: ReactNode }) {
  const t = voaCopy(useVoaLocale());
  const pathname = usePathname();
  const { stage, resultId } = stageOf(pathname);
  const floor = useVoaFloorPrice();
  const [order, setOrder] = useState<VoaOrderReport>({});

  const report = useCallback((patch: VoaOrderReport) => {
    setOrder((prev) =>
      patch.resultId && patch.resultId !== prev.resultId
        ? { ...patch }
        : { ...prev, ...patch },
    );
    if (patch.resultId && typeof patch.priceIdr === "number") {
      mergeCheckoutHandoff(patch.resultId, { price_idr: patch.priceIdr });
    }
  }, []);

  // Upload and checkout name the check in their path. The tab's hand-off
  // answers first; a fresh tab asks the check itself, once.
  useEffect(() => {
    if (!resultId || (stage !== "passport" && stage !== "payment")) return;
    const handed = readCheckoutHandoff(resultId).price_idr;
    if (typeof handed === "number") {
      setOrder({ resultId, verdict: "ACCEPT", priceIdr: handed });
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(
          `/api/visa/voa/eligibility-checks/${encodeURIComponent(resultId)}`,
          { credentials: "include" },
        );
        if (!res.ok) return;
        const body = (await res.json()) as {
          verdict?: string;
          price_idr?: number;
        };
        if (
          !cancelled &&
          body.verdict === "ACCEPT" &&
          typeof body.price_idr === "number"
        ) {
          report({ resultId, verdict: "ACCEPT", priceIdr: body.price_idr });
        }
      } catch {
        // No price is better than an invented one: the strip simply omits it.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [resultId, stage, report]);

  const exact =
    order.verdict !== "DECLINE" && typeof order.priceIdr === "number"
      ? formatIDR(order.priceIdr)
      : null;
  const payReview = exact
    ? `${t("counter.product")} · ${t("counter.exact", { price: exact })}`
    : null;
  const payAction = exact ? t("counter.pay", { price: exact }) : null;
  const value = useMemo(
    () => ({
      order,
      report,
      pay:
        payReview && payAction
          ? { review: payReview, action: payAction }
          : null,
    }),
    [order, report, payReview, payAction],
  );

  const current = STAGES.findIndex((s) => s.id === stage);
  let priceLine: string | null = null;
  if (stage === "check") {
    priceLine =
      floor !== null ? t("counter.from", { price: formatIDR(floor) }) : null;
  } else if (exact) {
    priceLine = t("counter.exact", { price: exact });
  }
  const stateKey =
    stage === "tracking"
      ? order.orderState === "paid" && order.practiceState
        ? STATE_WORD[order.practiceState]
        : order.orderState
          ? STATE_WORD[order.orderState]
          : null
      : null;

  return (
    <div className="voa-counter" data-voa-stage={stage}>
      <header className="voa-counter__bar">
        <a className="voa-counter__lockup" href="/visa/voa">
          <BZLogo variant="round" size={28} priority />
          <span className="voa-counter__brand">{t("lockup.brand")}</span>
          <span className="voa-counter__product">{t("frame.title")}</span>
        </a>
        <p className="voa-counter__agent">
          {/* eslint-disable-next-line @next/next/no-img-element -- a 40px staff face; the optimiser adds nothing here */}
          <img
            className="voa-counter__face"
            src="/static/team/surya.jpg"
            alt=""
            width={40}
            height={40}
          />
          <span>{t("counter.agent")}</span>
        </p>
      </header>
      <div
        className="voa-counter__strip"
        role="group"
        aria-label={t("counter.aria")}
      >
        <div className="voa-counter__strip-in">
          <p className="voa-counter__line">
            <span className="voa-counter__item">{t("counter.product")}</span>
            {priceLine ? (
              <span className="voa-counter__price">{priceLine}</span>
            ) : null}
            {stateKey ? (
              <span className="voa-counter__state">{t(stateKey)}</span>
            ) : null}
          </p>
          <ol
            className="voa-counter__stages"
            aria-label={t("counter.stages.aria")}
          >
            {STAGES.map((s, i) => (
              <li
                key={s.id}
                className="voa-counter__stage"
                data-state={
                  i < current ? "done" : i === current ? "current" : "todo"
                }
                aria-current={i === current ? "step" : undefined}
              >
                <span className="voa-counter__n" aria-hidden="true">
                  {i + 1}
                </span>
                <span className="voa-counter__stage-label">{t(s.key)}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
      <VoaCounterContext.Provider value={value}>
        <div className="voa-counter__desk">{children}</div>
      </VoaCounterContext.Provider>
    </div>
  );
}

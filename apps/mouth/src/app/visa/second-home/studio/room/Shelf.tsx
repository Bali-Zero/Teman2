"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useOptionalTranslation } from "@/i18n";
import { usePricingData } from "@/hooks/usePricingData";
import {
  CHECKLIST_ITEMS,
  classifyChecklistItem,
} from "@/lib/secondhome-studio/checklist";
import { getCopy } from "@/lib/secondhome-studio/copy";
import {
  COUNTRY_PROGRAMMES,
  MALAYSIA_MM2H_TIERS,
  PORTUGAL_D7_INCOME_FORMULA,
  type CountryProgramme,
  type SourcedCell,
} from "@/lib/secondhome-studio/country-comparator";
import {
  E33_LIVE_PRICE_CATEGORY,
  E33_LIVE_PRICE_KEY,
  E33E_LIVE_PRICE_KEY,
  E33F_OFFSHORE_LIVE_PRICE_KEY,
  E33F_ONSHORE_LIVE_PRICE_KEY,
} from "@/lib/secondhome-studio/pricing-key";
import { evaluatePlan } from "@/lib/secondhome-studio/rules";
import type { PlanState, Verdict } from "@/lib/secondhome-studio/types";
import { E33_FACT_REGISTRY_META } from "../data/e33-facts";
import { shelfFacts } from "./shelf-facts";

export type DrawerId = "facts" | "checklist" | "tariff" | "compare" | "notes";

export const DRAWERS: readonly DrawerId[] = [
  "facts",
  "checklist",
  "tariff",
  "compare",
  "notes",
];

/** The live Indonesian guide (the only E33 article family that is indexed
 *  and hedges its pending facts). The four noIndex E33 families are never
 *  linked from the Studio — see research/secondhome/2026-09-12-e33-editorial-census.md. */
export const LIVE_ID_ARTICLE_HREF = "/visas/second-home-visa-indonesia?lang=id";

/* ── Facts ─────────────────────────────────────────────────────────────── */

function FactsDrawer() {
  const groups = shelfFacts();
  return (
    <>
      <p className="bz-shs-drawer-intro">{getCopy("room.facts.intro")}</p>
      {groups.map(({ group, facts }) => (
        <section key={group} className="bz-shs-drawer-group">
          <h3 className="bz-shs-drawer-subhead">
            {getCopy(`room.facts.groups.${group}`)}
          </h3>
          <ul className="bz-shs-facts">
            {facts.map((fact) => {
              const caveatKey = `room.facts.caveats.${fact.id}`;
              const caveat = getCopy(caveatKey);
              return (
                <li
                  key={fact.id}
                  className="bz-shs-fact"
                  data-fact-id={fact.id}
                  data-status={fact.status}
                >
                  <p className="bz-shs-fact-topic">{fact.topic}</p>
                  <p className="bz-shs-fact-value">{fact.value}</p>
                  {caveat !== caveatKey ? (
                    <p className="bz-shs-fact-caveat">{caveat}</p>
                  ) : null}
                  <p className="bz-shs-fact-meta">
                    <span className="bz-shs-fact-status">
                      {fact.status === "confirmed"
                        ? getCopy("room.facts.statusConfirmed")
                        : getCopy("room.facts.statusPending")}
                    </span>
                    <span>
                      {getCopy(`room.facts.confidence.${fact.confidence}`)}
                    </span>
                    <span>
                      {getCopy("room.facts.checked")} {fact.source_date}
                    </span>
                  </p>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      <p className="bz-shs-drawer-foot">
        {getCopy("room.facts.registry")} {E33_FACT_REGISTRY_META.version}
      </p>
    </>
  );
}

/* ── Checklist ─────────────────────────────────────────────────────────── */

function ChecklistDrawer({
  plan,
  verdict,
}: {
  plan: PlanState;
  verdict: Verdict | null;
}) {
  // Read-only: the drawer classifies, it never ticks (ticking writes the
  // plan, and a drawer must not). evaluatePlan is pure.
  const against = verdict ?? evaluatePlan(plan);
  const classified = CHECKLIST_ITEMS.map((item) => ({
    item,
    applicability: classifyChecklistItem(item.id, plan, against),
  }));
  const lists = [
    { key: "applies", label: getCopy("room.checklistDrawer.applies") },
    { key: "may_apply", label: getCopy("room.checklistDrawer.mayApply") },
  ] as const;
  return (
    <>
      <p className="bz-shs-drawer-intro">
        {getCopy("room.checklistDrawer.intro")}
      </p>
      {lists.map(({ key, label }) => {
        const items = classified.filter((c) => c.applicability === key);
        if (items.length === 0) return null;
        return (
          <section key={key} className="bz-shs-drawer-group">
            <h3 className="bz-shs-drawer-subhead">{label}</h3>
            <ul className="bz-shs-drawer-list">
              {items.map(({ item }) => (
                <li key={item.id} data-applicability={key}>
                  <p className="bz-shs-fact-topic">{getCopy(item.titleKey)}</p>
                  <p className="bz-shs-fact-value">{getCopy(item.whyKey)}</p>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </>
  );
}

/* ── Tariff ────────────────────────────────────────────────────────────── */

const TARIFF_ROWS: ReadonlyArray<{ labelKey: string; priceKey: string }> = [
  { labelKey: "room.tariff.rows.e33", priceKey: E33_LIVE_PRICE_KEY },
  { labelKey: "room.tariff.rows.e33e", priceKey: E33E_LIVE_PRICE_KEY },
  {
    labelKey: "room.tariff.rows.e33eExtend",
    priceKey: "E33E Second Home Senior (Extend)",
  },
  {
    labelKey: "room.tariff.rows.e33fOffshore",
    priceKey: E33F_OFFSHORE_LIVE_PRICE_KEY,
  },
  {
    labelKey: "room.tariff.rows.e33fOnshore",
    priceKey: E33F_ONSHORE_LIVE_PRICE_KEY,
  },
  {
    labelKey: "room.tariff.rows.e33fExtend",
    priceKey: "E33F Second Home Senior (Extend)",
  },
];

function TariffRow({
  labelKey,
  priceKey,
}: {
  labelKey: string;
  priceKey: string;
}) {
  const { price } = usePricingData(priceKey, E33_LIVE_PRICE_CATEGORY);
  return (
    <tr>
      <th scope="row">{getCopy(labelKey)}</th>
      <td className="bz-shs-figure" data-price-key={priceKey}>
        {price ?? (
          <span className="bz-shs-tariff-missing">
            {getCopy("room.tariff.unavailable")}
          </span>
        )}
      </td>
    </tr>
  );
}

function TariffDrawer() {
  return (
    <>
      <p className="bz-shs-drawer-intro">{getCopy("room.tariff.intro")}</p>
      <table className="bz-shs-ledger-table">
        <thead>
          <tr>
            <th scope="col">{getCopy("room.tariff.service")}</th>
            <th scope="col">{getCopy("room.tariff.fee")}</th>
          </tr>
        </thead>
        <tbody>
          {TARIFF_ROWS.map((row) => (
            <TariffRow key={row.priceKey} {...row} />
          ))}
        </tbody>
      </table>
    </>
  );
}

/* ── Compare ───────────────────────────────────────────────────────────── */

const COMPARED: readonly CountryProgramme["id"][] = [
  "indonesia_e33_base",
  "malaysia_mm2h",
  "portugal_d7",
];

const COMPARE_ROWS = [
  "firstGrantValidity",
  "cumulativeCap",
  "incomeRequirement",
  "workRights",
] as const;

function SourceLine({ cell }: { cell: SourcedCell<unknown> }) {
  const external = /^https?:\/\//.test(cell.sourceUrl);
  return (
    <span className="bz-shs-source">
      {getCopy("room.compare.source")}:{" "}
      {external ? (
        <a href={cell.sourceUrl} rel="noopener noreferrer" target="_blank">
          {new URL(cell.sourceUrl).hostname.replace(/^www\./, "")}
        </a>
      ) : (
        getCopy("room.compare.registrySource")
      )}
      , {getCopy("room.compare.read")} {cell.capturedDate}
    </span>
  );
}

/** Portugal D7's income cell is written for developers (it names the
 *  structured constant); the atlas composes the sentence from that
 *  constant's own sourced cells instead. */
function d7IncomeCell(): SourcedCell<string> {
  const f = PORTUGAL_D7_INCOME_FORMULA;
  const rmmg = f.rmmg2026MonthlyEur;
  const year = (rmmg.sourceLastUpdated ?? rmmg.capturedDate).slice(0, 4);
  const value = getCopy("room.compare.d7Income")
    .replace("{principal}", String(f.principalPercentOfRmmg.value))
    .replace("{rmmg}", String(rmmg.value))
    .replace("{year}", year)
    .replace("{adult}", String(f.additionalAdultPercentOfRmmg.value))
    .replace("{child}", String(f.dependentChildPercentOfRmmg.value));
  return { ...rmmg, value, caveat: undefined };
}

function compareCell(
  programme: CountryProgramme,
  row: (typeof COMPARE_ROWS)[number],
): SourcedCell<string> | undefined {
  if (programme.id === "portugal_d7" && row === "incomeRequirement") {
    return d7IncomeCell();
  }
  return programme[row] as SourcedCell<string> | undefined;
}

function CompareDrawer() {
  const programmes = COMPARED.map((id) =>
    COUNTRY_PROGRAMMES.find((p) => p.id === id),
  ).filter((p): p is CountryProgramme => Boolean(p));
  const tierCell = MALAYSIA_MM2H_TIERS[0]?.depositUsd;
  return (
    <>
      <p className="bz-shs-drawer-intro">{getCopy("room.compare.intro")}</p>
      <div className="bz-shs-atlas-scroll">
        <table className="bz-shs-atlas">
          <thead>
            <tr>
              <th scope="col">{getCopy("room.compare.attribute")}</th>
              {programmes.map((p) => (
                <th scope="col" key={p.id}>
                  <span className="bz-shs-atlas-country">{p.country}</span>
                  <span className="bz-shs-atlas-programme">
                    {p.programmeName}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPARE_ROWS.map((row) => (
              <tr key={row}>
                <th scope="row">{getCopy(`room.compare.${row}`)}</th>
                {programmes.map((p) => {
                  const cell = compareCell(p, row);
                  return (
                    <td key={p.id}>
                      {cell ? (
                        <>
                          <span className="bz-shs-atlas-value">
                            {cell.value}
                          </span>
                          {cell.caveat ? (
                            <span className="bz-shs-atlas-caveat">
                              {cell.caveat}
                            </span>
                          ) : null}
                          <SourceLine cell={cell} />
                        </>
                      ) : (
                        <span className="bz-shs-atlas-empty">
                          {getCopy("room.compare.notRecorded")}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3 className="bz-shs-drawer-subhead">
        {getCopy("room.compare.tiersTitle")}
      </h3>
      <table className="bz-shs-ledger-table">
        <thead>
          <tr>
            <th scope="col">{getCopy("room.compare.tier")}</th>
            <th scope="col">{getCopy("room.compare.depositUsd")}</th>
            <th scope="col">{getCopy("room.compare.validityYears")}</th>
          </tr>
        </thead>
        <tbody>
          {MALAYSIA_MM2H_TIERS.map((tier) => (
            <tr key={tier.tierName}>
              <th scope="row">{tier.tierName}</th>
              <td className="bz-shs-figure">
                {tier.depositUsd.value.toLocaleString("en-US")}
              </td>
              <td className="bz-shs-figure">{tier.validityYears.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {tierCell ? (
        <p className="bz-shs-drawer-foot">
          <SourceLine cell={tierCell} />
        </p>
      ) : null}
    </>
  );
}

/* ── Notes ─────────────────────────────────────────────────────────────── */

function NotesDrawer() {
  const i18n = useOptionalTranslation();
  const { price } = usePricingData(E33_LIVE_PRICE_KEY, E33_LIVE_PRICE_CATEGORY);
  // The landing's own FAQ keys, same filter as SecondHomeLanding: the sixth
  // answer quotes the price, so it only appears when the price list has one.
  const items = i18n
    ? [1, 2, 3, 4, 5, 6]
        .filter((n) => n !== 6 || price !== null)
        .map((n) => ({
          n,
          q: i18n.t(`secondHome.faq.q${n}`),
          a: i18n.t(`secondHome.faq.a${n}`, price ? { price } : undefined),
        }))
    : [];
  return (
    <>
      <p className="bz-shs-drawer-intro">{getCopy("room.notes.intro")}</p>
      {items.length > 0 ? (
        <div className="bz-shs-notes">
          {items.map((item) => (
            <details key={item.n} className="bz-shs-note">
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      ) : null}
      <p className="bz-shs-drawer-foot">
        <a className="r19-link" href={LIVE_ID_ARTICLE_HREF} hrefLang="id">
          {getCopy("room.notes.articleLink")}
        </a>
      </p>
    </>
  );
}

/* ── The drawer panel (side panel ≥64rem, bottom sheet below) ──────────── */

const FOCUSABLE =
  'a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';

function DrawerPanel({
  id,
  onClose,
  children,
}: {
  id: DrawerId;
  onClose: () => void;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, []);

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !panelRef.current) return;
    const nodes = Array.from(
      panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE),
    );
    if (nodes.length === 0) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const titleId = `bz-shs-drawer-${id}-title`;
  return (
    <div className="bz-shs-drawer-layer">
      <div
        aria-hidden="true"
        className="bz-shs-drawer-scrim"
        onClick={onClose}
      />
      <section
        ref={panelRef}
        id={`bz-shs-drawer-${id}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="bz-shs-drawer"
        data-drawer={id}
        onKeyDown={onKeyDown}
      >
        <header className="bz-shs-drawer-head">
          <h2 id={titleId} className="bz-shs-drawer-heading">
            {getCopy(`room.shelf.drawers.${id}.title`)}
          </h2>
          <button
            ref={closeRef}
            type="button"
            className="bz-shs-drawer-close"
            onClick={onClose}
          >
            {getCopy("room.shelf.close")}
          </button>
        </header>
        <div className="bz-shs-drawer-body">{children}</div>
      </section>
    </div>
  );
}

/* ── The shelf ─────────────────────────────────────────────────────────── */

export interface ShelfProps {
  plan: PlanState;
  verdict: Verdict | null;
}

/**
 * THE SHELF — five drawers of real material (registry facts, the route's
 * checklist, the live tariff, the sourced country atlas, the landing's
 * notes). Opening a drawer only reads `plan`; there is no path from here
 * back into the plan state.
 */
export function Shelf({ plan, verdict }: ShelfProps) {
  const [open, setOpen] = useState<DrawerId | null>(null);
  const fronts = useRef<Partial<Record<DrawerId, HTMLButtonElement | null>>>(
    {},
  );

  const close = useCallback(() => {
    const front = open ? fronts.current[open] : null;
    setOpen(null);
    // Focus returns to the drawer front that opened it.
    requestAnimationFrame(() => front?.focus());
  }, [open]);

  let content: ReactNode = null;
  if (open === "facts") content = <FactsDrawer />;
  else if (open === "checklist")
    content = <ChecklistDrawer plan={plan} verdict={verdict} />;
  else if (open === "tariff") content = <TariffDrawer />;
  else if (open === "compare") content = <CompareDrawer />;
  else if (open === "notes") content = <NotesDrawer />;

  return (
    <aside
      className="bz-shs-shelf"
      aria-label={getCopy("room.shelf.label")}
      data-drawer-open={open ? "true" : undefined}
    >
      <p className="bz-shs-shelf-title">{getCopy("room.shelf.label")}</p>
      <p className="bz-shs-shelf-intro">{getCopy("room.shelf.intro")}</p>
      <ul className="bz-shs-drawers">
        {DRAWERS.map((id) => (
          <li key={id}>
            <button
              ref={(node) => {
                fronts.current[id] = node;
              }}
              type="button"
              className="bz-shs-drawer-front"
              aria-haspopup="dialog"
              aria-expanded={open === id}
              onClick={() => setOpen(id)}
            >
              <span className="bz-shs-drawer-front-title">
                {getCopy(`room.shelf.drawers.${id}.title`)}
              </span>
              <span className="bz-shs-drawer-front-blurb">
                {getCopy(`room.shelf.drawers.${id}.blurb`)}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {open ? (
        <DrawerPanel id={open} onClose={close}>
          {content}
        </DrawerPanel>
      ) : null}
    </aside>
  );
}

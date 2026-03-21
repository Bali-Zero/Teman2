import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ZeroRoleWidget } from "../ZeroRoleWidget";
import { TeamRoleWidget } from "../TeamRoleWidget";
import { TaxRoleWidget } from "../TaxRoleWidget";
import { MarketingRoleWidget } from "../MarketingRoleWidget";
import { AccountingRoleWidget } from "../AccountingRoleWidget";

describe("ZeroRoleWidget", () => {
  it("renders revenue amount", () => {
    render(
      <ZeroRoleWidget
        metrics={{
          revenue_mtd: 48200,
          visti_scadenza: 3,
          fatture_overdue: 2,
          agenti_count: 46,
          fly_uptime: 99.9,
        }}
        alerts={[]}
      />,
    );
    expect(screen.getByText(/48/)).toBeInTheDocument();
  });
  it("renders critical alert for visti_scadenza > 0", () => {
    render(
      <ZeroRoleWidget
        metrics={{
          revenue_mtd: 0,
          visti_scadenza: 3,
          fatture_overdue: 0,
          agenti_count: 0,
          fly_uptime: 100,
        }}
        alerts={[]}
      />,
    );
    expect(screen.getByText(/3 visti/)).toBeInTheDocument();
  });
});

describe("TeamRoleWidget", () => {
  it("renders assigned practices count", () => {
    render(
      <TeamRoleWidget
        metrics={{
          pratiche_assegnate: 7,
          prossima_scadenza: "2026-03-20",
          doc_mancanti: 2,
          clienti_assegnati: 4,
          stalled_count: 1,
        }}
        alerts={[]}
      />,
    );
    expect(screen.getByText("7")).toBeInTheDocument();
  });
  it("renders next deadline when present", () => {
    render(
      <TeamRoleWidget
        metrics={{
          pratiche_assegnate: 0,
          prossima_scadenza: "2026-03-20",
          doc_mancanti: 0,
          clienti_assegnati: 0,
          stalled_count: 0,
        }}
        alerts={[]}
      />,
    );
    expect(screen.getByText(/2026-03-20/)).toBeInTheDocument();
  });
});

describe("TaxRoleWidget", () => {
  it("renders next tax deadline", () => {
    render(
      <TaxRoleWidget
        metrics={{
          clienti_compliant: 12,
          scadenze_7gg: 3,
          dichiarazioni_pending: 5,
          alert_pajak: 1,
          prossima_scadenza: "31 mar",
        }}
        alerts={[]}
      />,
    );
    expect(screen.getByText(/31 mar/)).toBeInTheDocument();
  });
});

describe("MarketingRoleWidget", () => {
  it("renders subscriber delta", () => {
    render(
      <MarketingRoleWidget
        metrics={{
          articoli_pubblicati: 8,
          articoli_in_review: 3,
          subscriber_delta: 42,
          lead_nuovi: 5,
        }}
        alerts={[]}
      />,
    );
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });
});

describe("AccountingRoleWidget", () => {
  it("renders overdue total", () => {
    render(
      <AccountingRoleWidget
        metrics={{
          fatture_pagate_mtd: 10,
          fatture_overdue: 2,
          fatture_pending: 5,
          ricavi_mtd: 50000,
          overdue_total: 12400,
        }}
        alerts={[]}
      />,
    );
    expect(screen.getByText(/12/)).toBeInTheDocument(); // 12400 → 12.4K
  });
});

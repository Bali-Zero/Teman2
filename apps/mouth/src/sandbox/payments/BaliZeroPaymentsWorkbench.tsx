"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import {
  ArrowRightLeft,
  Building2,
  CreditCard,
  FileText,
  Link2,
  Receipt,
  Wallet,
} from "lucide-react";

export type BaliZeroPaymentStatus =
  | "draft"
  | "issued"
  | "partial"
  | "paid"
  | "overdue";

export interface BaliZeroPracticeSummary {
  id: string;
  title: string;
  clientName: string;
  category: string;
  crmStage: string;
  progress: number;
  assignee: string;
  nextMilestone: string;
}

export interface BaliZeroInvoiceLineItem {
  id: string;
  label: string;
  quantity: number;
  unitAmount: number;
}

export interface BaliZeroInvoiceSummary {
  id: string;
  practiceId: string;
  invoiceNumber: string;
  issuedAt: string;
  dueAt: string;
  currency: "USD" | "IDR";
  status: BaliZeroPaymentStatus;
  paidAmount: number;
  totalAmount: number;
  lineItems: BaliZeroInvoiceLineItem[];
}

export interface BaliZeroPaymentMethod {
  id: string;
  label: string;
  provider: string;
  type: "card" | "bank_transfer" | "wallet";
  settlementWindow: string;
  feeLabel: string;
  recommended?: boolean;
}

export interface BaliZeroPaymentEvent {
  id: string;
  invoiceId: string;
  title: string;
  detail: string;
  at: string;
  actor: string;
}

export interface BaliZeroPaymentsWorkbenchProps {
  practices: BaliZeroPracticeSummary[];
  invoices: BaliZeroInvoiceSummary[];
  paymentMethods: BaliZeroPaymentMethod[];
  events: BaliZeroPaymentEvent[];
  initialInvoiceId?: string;
  onCreatePaymentLink?: (payload: {
    invoiceId: string;
    practiceId: string;
    paymentMethodId: string;
  }) => void;
  onSendReminder?: (invoiceId: string) => void;
  onRecordOfflinePayment?: (invoiceId: string) => void;
}

const statusTone: Record<BaliZeroPaymentStatus, string> = {
  draft: "secondary",
  issued: "default",
  partial: "outline",
  paid: "secondary",
  overdue: "destructive",
};

const currencyFormatter = (currency: "USD" | "IDR"): Intl.NumberFormat =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "IDR" ? 0 : 2,
  });

const formatCurrency = (value: number, currency: "USD" | "IDR"): string =>
  currencyFormatter(currency).format(value);

const formatDate = (value: string): string =>
  new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));

const getDaysToDue = (dueAt: string): number => {
  const today = new Date();
  const dueDate = new Date(dueAt);
  const millisecondsPerDay = 1000 * 60 * 60 * 24;

  return Math.ceil((dueDate.getTime() - today.getTime()) / millisecondsPerDay);
};

const methodIcon = (type: BaliZeroPaymentMethod["type"]) => {
  switch (type) {
    case "card":
      return CreditCard;
    case "bank_transfer":
      return ArrowRightLeft;
    case "wallet":
      return Wallet;
  }
};

const getStatusLabel = (status: BaliZeroPaymentStatus): string => {
  switch (status) {
    case "draft":
      return "Draft";
    case "issued":
      return "Issued";
    case "partial":
      return "Partial";
    case "paid":
      return "Paid";
    case "overdue":
      return "Overdue";
  }
};

export function BaliZeroPaymentsWorkbench({
  practices,
  invoices,
  paymentMethods,
  events,
  initialInvoiceId,
  onCreatePaymentLink,
  onSendReminder,
  onRecordOfflinePayment,
}: BaliZeroPaymentsWorkbenchProps) {
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string>(
    initialInvoiceId ?? invoices[0]?.id ?? "",
  );
  const [selectedMethodId, setSelectedMethodId] = useState<string>(
    paymentMethods.find((method) => method.recommended)?.id ??
      paymentMethods[0]?.id ??
      "",
  );

  const selectedInvoice =
    invoices.find((invoice) => invoice.id === selectedInvoiceId) ?? invoices[0];
  const linkedPractice = practices.find(
    (practice) => practice.id === selectedInvoice?.practiceId,
  );
  const selectedMethod = paymentMethods.find(
    (method) => method.id === selectedMethodId,
  );

  const kpis = useMemo(() => {
    const totalOutstanding = invoices.reduce(
      (sum, invoice) => sum + Math.max(invoice.totalAmount - invoice.paidAmount, 0),
      0,
    );
    const paymentReadyCount = invoices.filter(
      (invoice) => invoice.status !== "paid",
    ).length;
    const activePractices = new Set(invoices.map((invoice) => invoice.practiceId))
      .size;

    return {
      totalOutstanding,
      paymentReadyCount,
      activePractices,
    };
  }, [invoices]);

  const invoiceEvents = events.filter(
    (event) => event.invoiceId === selectedInvoice?.id,
  );

  if (!selectedInvoice || !linkedPractice || !selectedMethod) {
    return (
      <Card className="border-dashed">
        <CardHeader>
          <CardTitle>Sandbox payments prototype unavailable</CardTitle>
          <CardDescription>
            Provide at least one practice, one invoice, and one payment method.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const amountDue = Math.max(
    selectedInvoice.totalAmount - selectedInvoice.paidAmount,
    0,
  );
  const collectionRate =
    selectedInvoice.totalAmount === 0
      ? 0
      : Math.round((selectedInvoice.paidAmount / selectedInvoice.totalAmount) * 100);
  const dueInDays = getDaysToDue(selectedInvoice.dueAt);

  return (
    <section
      className="grid gap-6 text-slate-100 md:grid-cols-[320px_minmax(0,1fr)]"
      aria-label="Bali Zero payments sandbox"
    >
      <div className="space-y-6">
        <Card className="border-slate-800 bg-slate-950">
          <CardHeader>
            <CardDescription>Sandbox overview</CardDescription>
            <CardTitle className="text-xl">Payments control tower</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <MetricCard
              icon={Receipt}
              label="Outstanding"
              value={formatCurrency(kpis.totalOutstanding, selectedInvoice.currency)}
            />
            <MetricCard
              icon={Link2}
              label="Invoices in flight"
              value={String(kpis.paymentReadyCount)}
            />
            <MetricCard
              icon={Building2}
              label="CRM practices linked"
              value={String(kpis.activePractices)}
            />
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-950">
          <CardHeader>
            <CardDescription>Invoices</CardDescription>
            <CardTitle className="text-lg">Select a billing thread</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {invoices.map((invoice) => {
              const practice = practices.find(
                (item) => item.id === invoice.practiceId,
              );
              const isSelected = invoice.id === selectedInvoice.id;

              return (
                <button
                  key={invoice.id}
                  type="button"
                  onClick={() => setSelectedInvoiceId(invoice.id)}
                  className={cn(
                    "w-full rounded-xl border p-4 text-left transition",
                    isSelected
                      ? "border-emerald-400 bg-emerald-500/10"
                      : "border-slate-800 bg-slate-900 hover:border-slate-600",
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium">{invoice.invoiceNumber}</p>
                      <p className="text-sm text-slate-400">
                        {practice?.title ?? "Unlinked practice"}
                      </p>
                    </div>
                    <Badge variant={statusTone[invoice.status] as never}>
                      {getStatusLabel(invoice.status)}
                    </Badge>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-sm text-slate-300">
                    <span>{formatCurrency(invoice.totalAmount, invoice.currency)}</span>
                    <span>Due {formatDate(invoice.dueAt)}</span>
                  </div>
                </button>
              );
            })}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        <Card className="border-slate-800 bg-slate-950">
          <CardHeader className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <CardDescription>Invoice to practice mapping</CardDescription>
              <CardTitle className="text-2xl">{selectedInvoice.invoiceNumber}</CardTitle>
              <p className="mt-2 text-sm text-slate-400">
                {linkedPractice.clientName} · {linkedPractice.category} · {linkedPractice.crmStage}
              </p>
            </div>
            <Badge variant={statusTone[selectedInvoice.status] as never}>
              {getStatusLabel(selectedInvoice.status)}
            </Badge>
          </CardHeader>
          <CardContent className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-3">
                <SummaryTile
                  label="Amount due"
                  value={formatCurrency(amountDue, selectedInvoice.currency)}
                />
                <SummaryTile
                  label="Collected"
                  value={formatCurrency(
                    selectedInvoice.paidAmount,
                    selectedInvoice.currency,
                  )}
                />
                <SummaryTile
                  label="Due in"
                  value={dueInDays >= 0 ? `${dueInDays} days` : `${Math.abs(dueInDays)} late`}
                />
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Practice progress</span>
                  <span>{linkedPractice.progress}%</span>
                </div>
                <Progress
                  className="mt-3 h-2 bg-slate-800"
                  indicatorClassName="bg-emerald-400"
                  value={linkedPractice.progress}
                />
                <p className="mt-3 text-sm text-slate-400">
                  Next milestone: {linkedPractice.nextMilestone}
                </p>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="mb-4 flex items-center gap-2">
                  <FileText className="h-4 w-4 text-emerald-300" />
                  <h3 className="font-medium">Invoice lines</h3>
                </div>
                <div className="space-y-3">
                  {selectedInvoice.lineItems.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-xl border border-slate-800 px-3 py-3 text-sm"
                    >
                      <div>
                        <p>{item.label}</p>
                        <p className="text-slate-500">Qty {item.quantity}</p>
                      </div>
                      <span>
                        {formatCurrency(
                          item.quantity * item.unitAmount,
                          selectedInvoice.currency,
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-5">
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-400">Payment rail</p>
                    <h3 className="font-medium">Online collection</h3>
                  </div>
                  <span className="text-sm text-emerald-300">
                    {collectionRate}% recovered
                  </span>
                </div>
                <div className="mt-4 space-y-3">
                  {paymentMethods.map((method) => {
                    const Icon = methodIcon(method.type);
                    const isSelected = method.id === selectedMethod.id;

                    return (
                      <button
                        key={method.id}
                        type="button"
                        onClick={() => setSelectedMethodId(method.id)}
                        className={cn(
                          "flex w-full items-start gap-3 rounded-xl border px-3 py-3 text-left transition",
                          isSelected
                            ? "border-sky-400 bg-sky-500/10"
                            : "border-slate-800 hover:border-slate-600",
                        )}
                      >
                        <Icon className="mt-0.5 h-4 w-4 text-sky-300" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{method.label}</p>
                            {method.recommended ? (
                              <Badge variant="secondary">Recommended</Badge>
                            ) : null}
                          </div>
                          <p className="text-sm text-slate-400">
                            {method.provider} · {method.feeLabel} ·{" "}
                            {method.settlementWindow}
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <Button
                    onClick={() =>
                      onCreatePaymentLink?.({
                        invoiceId: selectedInvoice.id,
                        practiceId: linkedPractice.id,
                        paymentMethodId: selectedMethod.id,
                      })
                    }
                  >
                    Generate link
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => onSendReminder?.(selectedInvoice.id)}
                  >
                    Send reminder
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => onRecordOfflinePayment?.(selectedInvoice.id)}
                  >
                    Record manual
                  </Button>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="mb-4 flex items-center gap-2">
                  <Link2 className="h-4 w-4 text-amber-300" />
                  <h3 className="font-medium">CRM sync summary</h3>
                </div>
                <dl className="space-y-3 text-sm">
                  <DetailRow label="Practice" value={linkedPractice.title} />
                  <DetailRow label="Assignee" value={linkedPractice.assignee} />
                  <DetailRow
                    label="Issued"
                    value={formatDate(selectedInvoice.issuedAt)}
                  />
                  <DetailRow label="Due" value={formatDate(selectedInvoice.dueAt)} />
                </dl>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-950">
          <CardHeader>
            <CardDescription>Ledger activity</CardDescription>
            <CardTitle className="text-lg">Recent payment events</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {invoiceEvents.map((event) => (
              <div
                key={event.id}
                className="rounded-xl border border-slate-800 bg-slate-900 px-4 py-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{event.title}</p>
                  <span className="text-xs text-slate-500">
                    {formatDate(event.at)}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-400">{event.detail}</p>
                <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-500">
                  {event.actor}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

interface MetricCardProps {
  icon: typeof Receipt;
  label: string;
  value: string;
}

function MetricCard({ icon: Icon, label, value }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-center gap-2 text-slate-400">
        <Icon className="h-4 w-4" />
        <span className="text-sm">{label}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

interface SummaryTileProps {
  label: string;
  value: string;
}

function SummaryTile({ label, value }: SummaryTileProps) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-xl font-semibold">{value}</p>
    </div>
  );
}

interface DetailRowProps {
  label: string;
  value: string;
}

function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-800 pb-3 last:border-b-0 last:pb-0">
      <dt className="text-slate-400">{label}</dt>
      <dd className="text-right text-slate-100">{value}</dd>
    </div>
  );
}

export const baliZeroPaymentsFixture: BaliZeroPaymentsWorkbenchProps = {
  practices: [
    {
      id: "practice-pt-pma-01",
      title: "PT PMA setup · Atlas Advisory",
      clientName: "Atlas Advisory",
      category: "Company Setup",
      crmStage: "Waiting payment",
      progress: 62,
      assignee: "Ops Team",
      nextMilestone: "Akta notaris booking",
    },
    {
      id: "practice-kitas-02",
      title: "Investor KITAS · Sofia Marchetti",
      clientName: "Sofia Marchetti",
      category: "Immigration",
      crmStage: "Documents approved",
      progress: 84,
      assignee: "Visa Desk",
      nextMilestone: "Biometric appointment",
    },
  ],
  invoices: [
    {
      id: "invoice-01",
      practiceId: "practice-pt-pma-01",
      invoiceNumber: "INV-2026-017",
      issuedAt: "2026-03-24",
      dueAt: "2026-04-02",
      currency: "USD",
      status: "issued",
      paidAmount: 0,
      totalAmount: 2900,
      lineItems: [
        {
          id: "line-01",
          label: "Company incorporation service fee",
          quantity: 1,
          unitAmount: 2400,
        },
        {
          id: "line-02",
          label: "Government filing buffer",
          quantity: 1,
          unitAmount: 500,
        },
      ],
    },
    {
      id: "invoice-02",
      practiceId: "practice-kitas-02",
      invoiceNumber: "INV-2026-021",
      issuedAt: "2026-03-26",
      dueAt: "2026-04-06",
      currency: "USD",
      status: "partial",
      paidAmount: 400,
      totalAmount: 1350,
      lineItems: [
        {
          id: "line-03",
          label: "Investor KITAS processing",
          quantity: 1,
          unitAmount: 1100,
        },
        {
          id: "line-04",
          label: "Courier and delivery",
          quantity: 1,
          unitAmount: 250,
        },
      ],
    },
  ],
  paymentMethods: [
    {
      id: "pm-card",
      label: "Card checkout",
      provider: "Stripe-like gateway",
      type: "card",
      settlementWindow: "T+2 settlement",
      feeLabel: "2.9% + fixed fee",
      recommended: true,
    },
    {
      id: "pm-bank",
      label: "Virtual account",
      provider: "Local bank rails",
      type: "bank_transfer",
      settlementWindow: "Instant confirmation",
      feeLabel: "Flat admin fee",
    },
    {
      id: "pm-wallet",
      label: "E-wallet collection",
      provider: "QRIS / wallet bridge",
      type: "wallet",
      settlementWindow: "Near real-time",
      feeLabel: "1.5% blended fee",
    },
  ],
  events: [
    {
      id: "event-01",
      invoiceId: "invoice-01",
      title: "Invoice issued",
      detail: "Draft converted to live invoice and linked to CRM milestone gate.",
      at: "2026-03-24",
      actor: "billing-ops",
    },
    {
      id: "event-02",
      invoiceId: "invoice-01",
      title: "Reminder scheduled",
      detail: "Auto-reminder queued 48 hours before due date.",
      at: "2026-03-27",
      actor: "automation",
    },
    {
      id: "event-03",
      invoiceId: "invoice-02",
      title: "Partial payment captured",
      detail: "Deposit received and practice remains blocked until balance clears.",
      at: "2026-03-27",
      actor: "payments-api",
    },
  ],
};

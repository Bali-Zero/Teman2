"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  FileText,
  Loader2,
  MessageSquareText,
  RefreshCw,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  approveWhatsAppExportReview,
  getWhatsAppExportYopoCase,
  listWhatsAppExportBatches,
  listWhatsAppExportContacts,
  listWhatsAppExportDocuments,
  listWhatsAppExportMessages,
  rejectWhatsAppExportReview,
  type WhatsAppExportCounts,
  type WhatsAppExportReviewBatch,
  type WhatsAppExportReviewItem,
  type WhatsAppExportReviewKind,
  type WhatsAppExportYopoCase,
} from "@/lib/api/whatsapp-export-review";
import { cn } from "@/lib/utils";

type ReviewTab = "overview" | "contacts" | "documents" | "yopo";

const REVIEW_TABS: Array<{ value: ReviewTab; label: string }> = [
  { value: "overview", label: "Overview" },
  { value: "contacts", label: "Contacts" },
  { value: "documents", label: "Documents" },
  { value: "yopo", label: "YOPO" },
];

const SENSITIVE_PATTERNS = [
  /[A-Z]\d{7,8}/gi,
  /\b\d{9,18}\b/g,
  /\b(?:jid|lid|baileys|remoteJid|participant)\b[:=]?\S*/gi,
  /(?:[A-Za-z]:)?(?:\/|\\)(?:Users|private|var|tmp|Volumes|home)[^\s]*/gi,
];

function sanitizeText(value: unknown, fallback: string = "—"): string {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  if (!trimmed) return fallback;
  return SENSITIVE_PATTERNS.reduce(
    (current, pattern) => current.replace(pattern, "[redacted]"),
    trimmed,
  );
}

function sanitizeBasename(value: unknown): string {
  const sanitized = sanitizeText(value);
  if (sanitized === "—") return sanitized;
  const parts = sanitized.split(/[\\/]/);
  return parts[parts.length - 1] || "—";
}

function sanitizePhone(value: unknown): string {
  if (typeof value !== "string") return "—";
  const digits = value.replace(/\D/g, "");
  if (digits.length < 4) return sanitizeText(value);
  const tail = digits.slice(-4);
  return `•••• ${tail}`;
}

function formatConfidence(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  const normalized = value <= 1 ? value * 100 : value;
  return `${Math.round(normalized)}%`;
}

function statusVariant(
  status?: string | null,
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "approved" || status === "completed") return "default";
  if (status === "rejected" || status === "failed" || status === "archived")
    return "destructive";
  if (status === "pending" || status === "reviewing" || status === "parsed")
    return "secondary";
  return "outline";
}

function countValue(
  counts: WhatsAppExportCounts | null | undefined,
  key: keyof WhatsAppExportCounts,
): number {
  return counts?.[key] ?? 0;
}

function aggregateCounts(
  batches: WhatsAppExportReviewBatch[],
): Required<WhatsAppExportCounts> {
  return batches.reduce(
    (total, batch) => ({
      contacts:
        total.contacts +
        countValue(batch.counts, "contacts") +
        (batch.total_contacts ?? 0),
      documents:
        total.documents +
        countValue(batch.counts, "documents") +
        (batch.total_documents ?? 0),
      messages:
        total.messages +
        countValue(batch.counts, "messages") +
        (batch.total_messages ?? 0),
      yopo_cases: total.yopo_cases + countValue(batch.counts, "yopo_cases"),
      pending: total.pending + countValue(batch.counts, "pending"),
      approved: total.approved + countValue(batch.counts, "approved"),
      rejected: total.rejected + countValue(batch.counts, "rejected"),
    }),
    {
      contacts: 0,
      documents: 0,
      messages: 0,
      yopo_cases: 0,
      pending: 0,
      approved: 0,
      rejected: 0,
    },
  );
}

export default function WhatsAppExportReviewPage() {
  const [activeTab, setActiveTab] = useState<ReviewTab>("overview");
  const [batches, setBatches] = useState<WhatsAppExportReviewBatch[]>([]);
  const [contacts, setContacts] = useState<WhatsAppExportReviewItem[]>([]);
  const [documents, setDocuments] = useState<WhatsAppExportReviewItem[]>([]);
  const [messages, setMessages] = useState<WhatsAppExportReviewItem[]>([]);
  const [yopoCase, setYopoCase] = useState<WhatsAppExportYopoCase | null>(null);
  const [selectedBatchId, setSelectedBatchId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionKey, setActionKey] = useState<string | null>(null);

  const selectedBatch = useMemo(
    () =>
      batches.find((batch) => String(batch.id) === selectedBatchId) ??
      batches[0],
    [batches, selectedBatchId],
  );

  const totals = useMemo(() => aggregateCounts(batches), [batches]);

  const loadReview = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextBatches = await listWhatsAppExportBatches({ limit: 50 });
      const batchId = selectedBatchId || String(nextBatches[0]?.id ?? "");
      const params = batchId ? { batchId, limit: 100 } : { limit: 100 };
      const [nextContacts, nextDocuments, nextMessages, nextYopoCase] =
        await Promise.all([
          listWhatsAppExportContacts(params),
          listWhatsAppExportDocuments(params),
          listWhatsAppExportMessages(params),
          getWhatsAppExportYopoCase(params),
        ]);

      setBatches(nextBatches);
      setSelectedBatchId(batchId);
      setContacts(nextContacts);
      setDocuments(nextDocuments);
      setMessages(nextMessages);
      setYopoCase(nextYopoCase);
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "WhatsApp export review API unavailable",
      );
      setBatches([]);
      setContacts([]);
      setDocuments([]);
      setMessages([]);
      setYopoCase(null);
    } finally {
      setIsLoading(false);
    }
  }, [selectedBatchId]);

  useEffect(() => {
    loadReview();
  }, [loadReview]);

  const handleAction = async (
    kind: "contacts" | "documents",
    item: WhatsAppExportReviewItem,
    action: "approve" | "reject",
  ): Promise<void> => {
    const key = `${kind}:${item.id}:${action}`;
    setActionKey(key);
    try {
      if (action === "approve") {
        await approveWhatsAppExportReview({
          kind,
          id: item.id,
          approvedClientId: item.suggested_client_id,
          approvedPracticeId: item.suggested_practice_id,
        });
      } else {
        await rejectWhatsAppExportReview({ kind, id: item.id });
      }
      await loadReview();
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : `Failed to ${action} review item`,
      );
    } finally {
      setActionKey(null);
    }
  };

  return (
    <main className="h-[calc(100vh-8rem)] -m-4 md:-m-6 lg:-m-8 overflow-hidden bg-[var(--background)] text-[var(--foreground)]">
      <div className="flex h-full flex-col">
        <header className="border-b border-[var(--border)] px-5 py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-[var(--accent)]" />
                <h1 className="text-xl font-semibold">
                  WhatsApp Export Review
                </h1>
                <Badge variant="outline">Internal</Badge>
              </div>
              <p className="mt-1 text-sm text-[var(--foreground-muted)]">
                Staged contacts, document hints, and YOPO candidates awaiting
                review.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <BatchSelector
                batches={batches}
                selectedBatchId={selectedBatchId}
                onChange={setSelectedBatchId}
              />
              <Button
                size="sm"
                variant="outline"
                onClick={loadReview}
                disabled={isLoading}
              >
                <RefreshCw
                  className={cn("h-4 w-4", isLoading && "animate-spin")}
                />
                Refresh
              </Button>
            </div>
          </div>
        </header>

        {error ? <ErrorState message={error} onRetry={loadReview} /> : null}

        <Tabs
          defaultValue="overview"
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as ReviewTab)}
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="border-b border-[var(--border)] px-5 py-3">
            <TabsList className="h-9 bg-[var(--background-secondary)]">
              {REVIEW_TABS.map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className="h-7 text-xs"
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>

          <div className="min-h-0 flex-1 overflow-auto px-5 py-4">
            {isLoading ? (
              <LoadingState />
            ) : (
              <>
                <TabsContent value="overview" className="mt-0">
                  <Overview
                    batches={batches}
                    selectedBatch={selectedBatch}
                    totals={totals}
                  />
                </TabsContent>
                <TabsContent value="contacts" className="mt-0">
                  <ReviewTable
                    kind="contacts"
                    title="Contacts"
                    icon={UserRound}
                    items={contacts}
                    actionKey={actionKey}
                    onAction={handleAction}
                  />
                </TabsContent>
                <TabsContent value="documents" className="mt-0">
                  <ReviewTable
                    kind="documents"
                    title="Documents"
                    icon={FileText}
                    items={documents}
                    actionKey={actionKey}
                    onAction={handleAction}
                  />
                </TabsContent>
                <TabsContent value="yopo" className="mt-0 space-y-4">
                  <ReviewTable
                    kind="messages"
                    title="Message Signals"
                    icon={MessageSquareText}
                    items={messages}
                    actionKey={actionKey}
                    onAction={handleAction}
                  />
                  <YopoPanel yopoCase={yopoCase} />
                </TabsContent>
              </>
            )}
          </div>
        </Tabs>
      </div>
    </main>
  );
}

function BatchSelector({
  batches,
  selectedBatchId,
  onChange,
}: {
  batches: WhatsAppExportReviewBatch[];
  selectedBatchId: string;
  onChange: (value: string) => void;
}) {
  if (batches.length === 0) {
    return (
      <span className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--foreground-muted)]">
        No batches
      </span>
    );
  }

  return (
    <select
      value={selectedBatchId}
      onChange={(event) => onChange(event.target.value)}
      className="h-8 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 text-xs text-[var(--foreground)] outline-none"
      aria-label="Select export batch"
    >
      {batches.map((batch) => (
        <option key={batch.id} value={String(batch.id)}>
          {sanitizeText(batch.source_label, "Batch")} ·{" "}
          {sanitizeBasename(batch.source_basename)}
        </option>
      ))}
    </select>
  );
}

function Overview({
  batches,
  selectedBatch,
  totals,
}: {
  batches: WhatsAppExportReviewBatch[];
  selectedBatch?: WhatsAppExportReviewBatch;
  totals: Required<WhatsAppExportCounts>;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <section className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
        <h2 className="text-sm font-semibold">Batch Snapshot</h2>
        {selectedBatch ? (
          <div className="mt-4 space-y-3 text-sm">
            <SafeField label="Source" value={selectedBatch.source_label} />
            <SafeField
              label="File"
              value={sanitizeBasename(selectedBatch.source_basename)}
            />
            <SafeField
              label="Confidence"
              value={formatConfidence(selectedBatch.confidence)}
            />
            <div className="flex items-center justify-between gap-3">
              <span className="text-[var(--foreground-muted)]">Status</span>
              <Badge variant={statusVariant(selectedBatch.review_status)}>
                {sanitizeText(selectedBatch.review_status, "pending")}
              </Badge>
            </div>
            <ReasonList reasons={selectedBatch.reasons} />
          </div>
        ) : (
          <EmptyState label="No staged WhatsApp export batches." />
        )}
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Batches" value={batches.length} />
        <Metric label="Contacts" value={totals.contacts} />
        <Metric label="Documents" value={totals.documents} />
        <Metric label="Messages" value={totals.messages} />
        <Metric label="YOPO" value={totals.yopo_cases} />
        <Metric label="Pending" value={totals.pending} />
        <Metric label="Approved" value={totals.approved} />
        <Metric label="Rejected" value={totals.rejected} />
      </section>
    </div>
  );
}

function ReviewTable({
  kind,
  title,
  icon: Icon,
  items,
  actionKey,
  onAction,
}: {
  kind: WhatsAppExportReviewKind;
  title: string;
  icon: typeof UserRound;
  items: WhatsAppExportReviewItem[];
  actionKey: string | null;
  onAction: (
    kind: "contacts" | "documents",
    item: WhatsAppExportReviewItem,
    action: "approve" | "reject",
  ) => Promise<void>;
}) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold">{title}</h2>
          <Badge variant="outline">{items.length}</Badge>
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState label={`No ${title.toLowerCase()} ready for review.`} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-left text-xs">
            <thead className="border-b border-[var(--border)] text-[var(--foreground-muted)]">
              <tr>
                <th className="px-4 py-2 font-medium">Source</th>
                <th className="px-4 py-2 font-medium">Phone</th>
                <th className="px-4 py-2 font-medium">Display name</th>
                <th className="px-4 py-2 font-medium">Suggested client</th>
                <th className="px-4 py-2 font-medium">Practice</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Reasons</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium">Review</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-[var(--border)]/70"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium">
                      {sanitizeText(item.source_label)}
                    </div>
                    <div className="text-[var(--foreground-muted)]">
                      {sanitizeBasename(item.source_basename)}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {sanitizePhone(item.masked_phone)}
                  </td>
                  <td className="px-4 py-3">
                    {sanitizeText(item.display_name ?? item.body_excerpt)}
                  </td>
                  <td className="px-4 py-3">
                    {sanitizeText(
                      item.suggested_client ?? item.suggested_client_id,
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {sanitizeText(
                      item.suggested_practice ?? item.suggested_practice_id,
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {formatConfidence(item.confidence)}
                  </td>
                  <td className="max-w-[220px] px-4 py-3">
                    <ReasonList
                      reasons={
                        item.reasons ??
                        (item.body_excerpt ? [item.body_excerpt] : [])
                      }
                      compact
                    />
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={statusVariant(item.review_status)}>
                      {sanitizeText(item.review_status, "pending")}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <ActionButtons
                      kind={kind}
                      item={item}
                      actionKey={actionKey}
                      onAction={onAction}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function YopoPanel({ yopoCase }: { yopoCase: WhatsAppExportYopoCase | null }) {
  const contacts = yopoCase?.contacts ?? [];
  const documents = yopoCase?.documents ?? [];
  const messages = yopoCase?.messages ?? [];
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
      <div className="mb-4 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-[var(--accent)]" />
        <h2 className="text-sm font-semibold">YOPO Case Candidate</h2>
      </div>
      {yopoCase ? (
        <div className="grid gap-3 lg:grid-cols-3">
          <SafeField
            label="Contacts"
            value={String(yopoCase.recap?.contact_count ?? contacts.length)}
          />
          <SafeField
            label="Documents"
            value={String(yopoCase.recap?.document_count ?? documents.length)}
          />
          <SafeField
            label="Messages"
            value={String(yopoCase.recap?.message_count ?? messages.length)}
          />
          <SafeField
            label="Status"
            value={yopoCase.recap?.review_status ?? "pending"}
          />
          <SafeField label="Lead contact" value={contacts[0]?.display_name} />
          <SafeField
            label="Lead document"
            value={documents[0]?.display_name ?? documents[0]?.source_basename}
          />
          <div className="lg:col-span-3 rounded-md border border-[var(--border)] p-3 text-xs text-[var(--foreground-muted)]">
            Review contacts, documents, and message signals in their tabs before
            approving individual rows.
          </div>
        </div>
      ) : (
        <EmptyState label="No YOPO case candidate returned by the staging API." />
      )}
    </section>
  );
}

function SafeField({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-[var(--border)] p-3">
      <span className="text-xs text-[var(--foreground-muted)]">{label}</span>
      <span className="max-w-[220px] truncate text-right text-sm">
        {sanitizeText(value)}
      </span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
      <p className="text-xs text-[var(--foreground-muted)]">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function ReasonList({
  reasons,
  compact = false,
}: {
  reasons?: string[] | null;
  compact?: boolean;
}) {
  const safeReasons = (reasons ?? [])
    .slice(0, compact ? 2 : 4)
    .map((reason) => sanitizeText(reason));
  if (safeReasons.length === 0)
    return <span className="text-[var(--foreground-muted)]">—</span>;
  return (
    <ul
      className={cn(
        "space-y-1 text-xs text-[var(--foreground-muted)]",
        compact && "truncate",
      )}
    >
      {safeReasons.map((reason, index) => (
        <li key={`${reason}-${index}`} className="truncate">
          {reason}
        </li>
      ))}
    </ul>
  );
}

function ActionButtons({
  kind,
  item,
  actionKey,
  onAction,
}: {
  kind: WhatsAppExportReviewKind;
  item: WhatsAppExportReviewItem;
  actionKey: string | null;
  onAction: (
    kind: "contacts" | "documents",
    item: WhatsAppExportReviewItem,
    action: "approve" | "reject",
  ) => Promise<void>;
}) {
  if (kind !== "contacts" && kind !== "documents") {
    return <span className="text-[var(--foreground-muted)]">—</span>;
  }

  const approveKey = `${kind}:${item.id}:approve`;
  const rejectKey = `${kind}:${item.id}:reject`;
  const approveDisabled =
    Boolean(actionKey) || (kind === "contacts" && !item.suggested_client_id);
  return (
    <div className="flex justify-end gap-2">
      <Button
        size="sm"
        variant="outline"
        onClick={() => onAction(kind, item, "approve")}
        disabled={approveDisabled}
        aria-label="Approve review item"
      >
        {actionKey === approveKey ? (
          <Loader2 className="animate-spin" />
        ) : (
          <Check />
        )}
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => onAction(kind, item, "reject")}
        disabled={Boolean(actionKey)}
        aria-label="Reject review item"
      >
        {actionKey === rejectKey ? <Loader2 className="animate-spin" /> : <X />}
      </Button>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex min-h-[280px] items-center justify-center gap-2 text-sm text-[var(--foreground-muted)]">
      <Loader2 className="h-4 w-4 animate-spin" />
      Loading staged review data
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex min-h-[140px] items-center justify-center px-4 text-sm text-[var(--foreground-muted)]">
      {label}
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="mx-5 mt-4 flex items-center justify-between gap-3 rounded-md border border-[var(--warning)]/40 bg-[var(--warning)]/10 px-4 py-3 text-sm">
      <div className="flex min-w-0 items-center gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--warning)]" />
        <span className="truncate text-[var(--foreground)]">
          {sanitizeText(message)}
        </span>
      </div>
      <Button size="sm" variant="outline" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

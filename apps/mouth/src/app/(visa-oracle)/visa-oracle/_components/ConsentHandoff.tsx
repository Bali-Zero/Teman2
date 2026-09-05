"use client";

import { useEffect, useMemo, useState } from "react";
import { MessageCircle } from "lucide-react";
import QRCode from "qrcode";
import {
  emitVisaOracleTelemetry,
  nonReversibleHash,
  type VisaOracleTelemetryState,
} from "../_lib/telemetry";
import {
  clearLocalConsentReceipt,
  createLocalConsentReceipt,
  loadLocalConsentReceipt,
  saveLocalConsentReceipt,
  sameConsentScope,
  type LocalConsentReceipt,
  type ConsentScope,
} from "../_lib/consent-store";

const WHATSAPP_NUMBER_PATTERN = /^\d{8,15}$/;
const PUBLIC_DECISION_ID_PATTERN = /^[a-z0-9]{16,20}$/;
const systemNow = () => new Date();
const systemReceiptId = () => crypto.randomUUID();

type HandoffLanguage = "en" | "id";

interface SharedHandoffProps {
  language: HandoffLanguage;
  guardianConsentRequired?: boolean;
  whatsappNumber?: string;
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">;
  now?: () => Date;
  createReceiptId?: () => string;
}

export type ConsentHandoffProps = SharedHandoffProps &
  (
    | { context: "CONSULTATION"; state?: never; assessmentReference?: never }
    | {
        /** Omitted by existing result callers. */
        context?: "ASSESSMENT";
        state: VisaOracleTelemetryState;
        /** Engine-generated opaque reference only; never facts or candidate copy. */
        assessmentReference?: string | null;
      }
  );

const COPY = {
  en: {
    title: "Continue with Bali Zero",
    consent:
      "I consent to open WhatsApp with a minimal Visa Oracle receipt. My interview answers are not included.",
    consultationConsent:
      "I consent to open WhatsApp to speak with a Bali Zero consultant. My interview answers are not included.",
    guardian:
      "I confirm that I am the parent or legal guardian and consent to this handoff for the minor.",
    guardianFirst:
      "Confirm parent or guardian authority before WhatsApp consent.",
    localReceipt:
      "This consent receipt stays in this browser session for up to 2 hours. No CRM record is created by this screen.",
    open: "Open WhatsApp",
    unavailable:
      "WhatsApp handoff is not configured. You can still print or save this result.",
    consultationUnavailable: "WhatsApp contact is not configured.",
    qr: "QR code for the consented WhatsApp handoff",
    message: "Hello Bali Zero. I consent to discuss my Visa Oracle result.",
    consultationMessage:
      "Hello Bali Zero. I would like to speak with a consultant about Visa Oracle.",
    state: "Result state",
    reference: "Assessment reference",
    privacy: "No interview answers are included in this message.",
  },
  id: {
    title: "Lanjutkan dengan Bali Zero",
    consent:
      "Saya setuju membuka WhatsApp dengan tanda terima Visa Oracle yang minimal. Jawaban wawancara saya tidak disertakan.",
    consultationConsent:
      "Saya setuju membuka WhatsApp untuk berbicara dengan konsultan Bali Zero. Jawaban wawancara saya tidak disertakan.",
    guardian:
      "Saya mengonfirmasi bahwa saya adalah orang tua atau wali sah dan menyetujui handoff ini untuk anak.",
    guardianFirst:
      "Konfirmasikan kewenangan orang tua atau wali sebelum persetujuan WhatsApp.",
    localReceipt:
      "Tanda terima persetujuan ini tersimpan di sesi browser ini hingga 2 jam. Layar ini tidak membuat catatan CRM.",
    open: "Buka WhatsApp",
    unavailable:
      "Pengalihan WhatsApp belum dikonfigurasi. Anda tetap dapat mencetak atau menyimpan hasil ini.",
    consultationUnavailable: "Kontak WhatsApp belum dikonfigurasi.",
    qr: "Kode QR untuk pengalihan WhatsApp yang telah disetujui",
    message: "Halo Bali Zero. Saya setuju membahas hasil Visa Oracle saya.",
    consultationMessage:
      "Halo Bali Zero. Saya ingin berbicara dengan konsultan tentang Visa Oracle.",
    state: "Status hasil",
    reference: "Referensi asesmen",
    privacy: "Pesan ini tidak menyertakan jawaban wawancara.",
  },
} as const;

function configuredWhatsAppNumber(value: string | undefined): string | null {
  if (!value) return null;
  const normalized = value.replace(/^\+/, "").trim();
  return WHATSAPP_NUMBER_PATTERN.test(normalized) ? normalized : null;
}

function validatedAssessmentReference(
  value: string | null | undefined,
): string | null {
  return typeof value === "string" && PUBLIC_DECISION_ID_PATTERN.test(value)
    ? value
    : null;
}

function buildMinimalMessage(
  language: HandoffLanguage,
  scope: ConsentScope,
): string {
  const copy = COPY[language];
  if (scope.context === "CONSULTATION") {
    return `${copy.consultationMessage}\n${copy.privacy}`;
  }
  return [
    copy.message,
    `${copy.state}: ${scope.state}`,
    scope.assessmentReference
      ? `${copy.reference}: ${scope.assessmentReference}`
      : undefined,
    copy.privacy,
  ]
    .filter((line): line is string => typeof line === "string")
    .join("\n");
}

function useQrPath(value: string): { size: number; path: string } {
  return useMemo(() => {
    const qr = QRCode.create(value, { errorCorrectionLevel: "M" });
    const { size, data } = qr.modules;
    let path = "";
    for (let row = 0; row < size; row += 1) {
      for (let column = 0; column < size; column += 1) {
        if (data[row * size + column]) {
          path += `M${column},${row}h1v1h-1z`;
        }
      }
    }
    return { size, path };
  }, [value]);
}

function ConsentQr({ value, label }: { value: string; label: string }) {
  const { size, path } = useQrPath(value);
  return (
    <div className="oracle-qr-wrap oracle-no-print">
      <svg
        className="oracle-qr"
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={label}
        data-qr-value={value}
        shapeRendering="crispEdges"
      >
        <rect width={size} height={size} fill="#ffffff" />
        <path d={path} fill="#000000" />
      </svg>
    </div>
  );
}

export function ConsentHandoff({
  language,
  context,
  state,
  assessmentReference,
  guardianConsentRequired = false,
  whatsappNumber = process.env.NEXT_PUBLIC_VISA_ORACLE_WHATSAPP_NUMBER,
  storage,
  now = systemNow,
  createReceiptId = systemReceiptId,
}: ConsentHandoffProps) {
  const [receipt, setReceipt] = useState<LocalConsentReceipt | null>(null);
  const [guardianConfirmed, setGuardianConfirmed] = useState(false);
  const number = configuredWhatsAppNumber(whatsappNumber);
  const copy = COPY[language];
  const publicReference = validatedAssessmentReference(assessmentReference);
  const scope = useMemo<ConsentScope>(
    () =>
      context === "CONSULTATION"
        ? { context: "CONSULTATION" }
        : {
            context: "ASSESSMENT",
            state,
            assessmentReference: publicReference,
          },
    [context, publicReference, state],
  );
  const activeReceipt =
    receipt && sameConsentScope(receipt.scope, scope) ? receipt : null;

  useEffect(() => {
    if (guardianConsentRequired) {
      clearLocalConsentReceipt({ storage });
      setReceipt(null);
      setGuardianConfirmed(false);
      return;
    }
    setReceipt(loadLocalConsentReceipt(scope, { storage, now: now() }));
  }, [guardianConsentRequired, now, scope, storage]);

  useEffect(() => {
    if (!activeReceipt) return;

    const scheduledReceiptId = activeReceipt.receiptId;
    const expiresAt = Date.parse(activeReceipt.expiresAtIso);
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const expireOrReschedule = () => {
      if (cancelled) return;

      const currentNow = now();
      const currentTime = currentNow.getTime();
      if (!Number.isFinite(expiresAt) || !Number.isFinite(currentTime)) {
        clearLocalConsentReceipt({ storage });
        setReceipt((currentReceipt) =>
          currentReceipt?.receiptId === scheduledReceiptId
            ? null
            : currentReceipt,
        );
        return;
      }

      const remainingMs = expiresAt - currentTime;
      if (remainingMs > 0) {
        timer = setTimeout(expireOrReschedule, remainingMs);
        return;
      }

      const persistedReceipt = loadLocalConsentReceipt(scope, {
        storage,
        now: currentNow,
      });
      setReceipt((currentReceipt) =>
        currentReceipt?.receiptId === scheduledReceiptId
          ? persistedReceipt
          : currentReceipt,
      );
    };

    expireOrReschedule();
    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
    };
  }, [activeReceipt, now, scope, storage]);

  const message = useMemo(
    () => buildMinimalMessage(language, scope),
    [language, scope],
  );
  const whatsappUrl =
    number && activeReceipt
      ? `https://wa.me/${number}?text=${encodeURIComponent(message)}`
      : null;

  const setGranted = (granted: boolean) => {
    if (!granted) {
      setReceipt(null);
      clearLocalConsentReceipt({ storage });
      return;
    }

    if (guardianConsentRequired && !guardianConfirmed) return;

    const nextReceipt = createLocalConsentReceipt(
      now(),
      createReceiptId(),
      scope,
    );
    saveLocalConsentReceipt(nextReceipt, { storage });
    setReceipt(nextReceipt);
    void nonReversibleHash(nextReceipt.receiptId)
      .then((correlationHash) => {
        emitVisaOracleTelemetry({
          event: "visa_oracle_v2_consent_granted",
          ...(scope.context === "ASSESSMENT" ? { state: scope.state } : {}),
          correlationHash,
        });
      })
      .catch(() => {
        // No telemetry is safer than a reversible fallback correlator.
      });
  };

  const trackOpen = () => {
    if (!activeReceipt) return;
    void nonReversibleHash(activeReceipt.receiptId)
      .then((correlationHash) => {
        emitVisaOracleTelemetry({
          event: "visa_oracle_v2_handoff_opened",
          ...(scope.context === "ASSESSMENT" ? { state: scope.state } : {}),
          correlationHash,
        });
      })
      .catch(() => {
        // No telemetry is safer than a reversible fallback correlator.
      });
  };

  return (
    <section className="oracle-no-print" aria-labelledby="oracle-handoff-title">
      <h2 id="oracle-handoff-title" className="oracle-outcome__section-title">
        {copy.title}
      </h2>
      {number === null ? (
        <p
          role="status"
          style={{ margin: 0, color: "var(--oracle-ink-muted)" }}
        >
          {scope.context === "CONSULTATION"
            ? copy.consultationUnavailable
            : copy.unavailable}
        </p>
      ) : (
        <>
          {guardianConsentRequired ? (
            <label className="oracle-checklist__item">
              <input
                type="checkbox"
                checked={guardianConfirmed}
                onChange={(event) => {
                  const confirmed = event.currentTarget.checked;
                  setGuardianConfirmed(confirmed);
                  if (!confirmed) {
                    setReceipt(null);
                    clearLocalConsentReceipt({ storage });
                  }
                }}
              />
              {copy.guardian}
            </label>
          ) : null}
          <label className="oracle-checklist__item">
            <input
              type="checkbox"
              checked={activeReceipt !== null}
              disabled={guardianConsentRequired && !guardianConfirmed}
              onChange={(event) => setGranted(event.currentTarget.checked)}
              aria-describedby="oracle-handoff-receipt-note"
            />
            {scope.context === "CONSULTATION"
              ? copy.consultationConsent
              : copy.consent}
          </label>
          <p
            id="oracle-handoff-receipt-note"
            className="oracle-question__hint"
            style={{ marginTop: "var(--space-2)" }}
          >
            {guardianConsentRequired && !guardianConfirmed
              ? copy.guardianFirst
              : copy.localReceipt}
          </p>
          {whatsappUrl ? (
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "var(--space-4)",
                alignItems: "center",
              }}
            >
              <a
                className="oracle-whatsapp-cta"
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                onClick={trackOpen}
              >
                <MessageCircle aria-hidden="true" size={18} />
                {copy.open}
              </a>
              <ConsentQr value={whatsappUrl} label={copy.qr} />
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

import { toSafeExternalHref, type SafeExternalHref } from "./safe-href";

const BALI_ZERO_WHATSAPP_NUMBER = "628213454721";
const BALI_ZERO_CONTACT_EMAIL = "zantara@balizero.com";

export interface WhatsAppIntent {
  topic: string;
  contactName?: string;
}

export interface EmailIntent {
  subject: string;
  body?: string;
}

function normalizedIntentText(value: string, field: string): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (!normalized) {
    throw new TypeError(`${field} is required.`);
  }
  return normalized;
}

export function buildWhatsAppIntent({
  topic,
  contactName,
}: WhatsAppIntent): SafeExternalHref {
  const normalizedTopic = normalizedIntentText(topic, "Topic");
  const normalizedContact = contactName
    ? normalizedIntentText(contactName, "Contact name")
    : undefined;
  const contactPhrase = normalizedContact ? ` with ${normalizedContact}` : "";
  const message = `Hello Bali Zero, I would like to discuss ${normalizedTopic}${contactPhrase}.`;

  return toSafeExternalHref(
    `https://wa.me/${BALI_ZERO_WHATSAPP_NUMBER}?text=${encodeURIComponent(message)}`,
  );
}

export function buildEmailIntent({
  subject,
  body,
}: EmailIntent): SafeExternalHref {
  const normalizedSubject = normalizedIntentText(subject, "Subject");
  const parameters = new URLSearchParams({ subject: normalizedSubject });
  if (body) parameters.set("body", normalizedIntentText(body, "Body"));

  return toSafeExternalHref(
    `mailto:${BALI_ZERO_CONTACT_EMAIL}?${parameters.toString()}`,
  );
}

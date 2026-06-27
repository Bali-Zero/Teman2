import { NextResponse } from "next/server";
import { canAccessVoiceConcierge } from "./auth";

export const runtime = "nodejs";

type ConciergeIntent =
  | "visa"
  | "company"
  | "tax"
  | "property"
  | "operations"
  | "unknown";

type ConciergeRisk = "low" | "medium" | "high";
type SupportedLocale = "en" | "it" | "id" | "fr" | "ru";

type ConciergeNextAction =
  | "answer_only"
  | "collect_non_pii_context"
  | "handoff_team"
  | "open_booking";

interface VoiceConciergeRequest {
  message?: string;
  locale?: SupportedLocale;
  history?: { role: "user" | "assistant"; content: string }[];
}

interface SafeHistoryTurn {
  role: "user" | "assistant";
  content: string;
}

interface VoiceConciergeResponse {
  answer: string;
  spoken_answer?: string;
  intent: ConciergeIntent;
  risk_level: ConciergeRisk;
  next_action: ConciergeNextAction;
  quick_replies: string[];
  safety_note: string;
  mode: "demo" | "gemini";
  provider: "local-demo" | "google-ai-studio";
  model?: string;
}

interface GeminiCandidate {
  content?: {
    parts?: { text?: string }[];
  };
}

interface GeminiResponse {
  candidates?: GeminiCandidate[];
}

const DEFAULT_MODEL = "gemini-2.5-flash";
const MAX_MESSAGE_LENGTH = 1200;
const MAX_HISTORY_ITEMS = 4;
const MAX_SPOKEN_ANSWER_LENGTH = 96;
const TEXT_PROVIDER_TIMEOUT_MS = 15_000;
const SUPPORTED_LOCALES = new Set<SupportedLocale>([
  "en",
  "it",
  "id",
  "fr",
  "ru",
]);

const SYSTEM_PROMPT = [
  "You are the Bali Zero voice concierge prototype.",
  "Handle public, non-PII questions about Indonesian visas, PT PMA setup, tax basics, property due diligence, and operations.",
  "Do not ask for passports, KTP, NPWP, phone numbers, emails, exact client names, document numbers, or private WhatsApp/CRM details.",
  "If the user needs case-specific advice, collect only non-PII context and suggest a team handoff.",
  "Never quote prices. Tell the user that pricing must be checked through the Bali Zero pricing tool/team.",
  "Also return spoken_answer: one short sentence for local TTS, max 96 characters, no PII.",
  "Return only JSON that matches the requested schema.",
].join("\n");

const RESPONSE_SCHEMA = {
  type: "object",
  properties: {
    answer: { type: "string" },
    spoken_answer: { type: "string" },
    intent: {
      type: "string",
      enum: ["visa", "company", "tax", "property", "operations", "unknown"],
    },
    risk_level: { type: "string", enum: ["low", "medium", "high"] },
    next_action: {
      type: "string",
      enum: [
        "answer_only",
        "collect_non_pii_context",
        "handoff_team",
        "open_booking",
      ],
    },
    quick_replies: {
      type: "array",
      items: { type: "string" },
    },
  },
  required: [
    "answer",
    "spoken_answer",
    "intent",
    "risk_level",
    "next_action",
    "quick_replies",
  ],
};

function getApiKey(): string | undefined {
  return process.env.GOOGLE_AI_STUDIO_API_KEY || process.env.GEMINI_API_KEY;
}

function getModel(): string {
  return process.env.GOOGLE_AI_STUDIO_MODEL || DEFAULT_MODEL;
}

function isPrototypeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" ||
    process.env.VOICE_CONCIERGE_LAB_ENABLED === "true"
  );
}

function isCloudTextAllowed(): boolean {
  return process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT === "true";
}

function containsObviousPii(message: string): boolean {
  const patterns = [
    /\b[A-Z][0-9]{7,8}\b/i, // common passport-like format
    /\b\d{16}\b/, // KTP-like digit count
    /\b\d{15,16}\b/, // NPWP-like digit count
    /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
    /(?:\+?\d[\s.-]?){9,}/,
    /\b(?:my|our|the)\s+(?:client|customer|applicant|beneficiary|investor|director|shareholder|employee|lead|prospect)\s+(?:is|called|named)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b/,
    /\b(?:client|customer|applicant|beneficiary|investor|director|shareholder|employee|lead|prospect)\s+(?:name\s+)?(?:is|called|named|:)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b/,
    /\b(?:cliente|richiedente|investitore|direttore|socio|dipendente)\s+(?:si\s+chiama|e|:)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b/i,
    /\b(?:klien|pelanggan|pemohon|investor|direktur|pemegang\s+saham|karyawan)\s+(?:bernama|adalah|:)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b/i,
    /\b[A-Z][a-z]{1,30}(?:\s+[A-Z][a-z]{1,30}){1,3}\s+(?:wants?|needs?|asked|requires?|owns?|has|is|plans?|would\s+like|will)\b/,
    /\b(?:for|about|regarding|re)\s+[A-Z][a-z]{1,30}(?:\s+[A-Z][a-z]{1,30}){1,3}\b/,
    /\bPT\s+(?!PMA\b|PMDN\b)[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,5}\b/,
    /\b(?:address|alamat|domicile|domisili|indirizzo)\s*(?:is|adalah|e|:)\s*[^,.]{6,}/i,
    /\b(?:jalan|jl\.?|street|road|avenue|gang|banjar|desa|kelurahan|kecamatan|kabupaten)\s+[A-Z0-9][^,.]{4,}/i,
    /\b(?:villa|land|plot|property|company|societa|azienda|proprieta|tanah|properti)\s+(?:is|called|named|si\s+chiama|denominata|bernama|adalah|:)\s+[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,5}\b/i,
    /\b(?:SHM|HGB|AJB|IMB|PBG)\s*(?:no\.?|number|nomor|:)?\s*[A-Z0-9./-]{4,}\b/i,
  ];
  return patterns.some((pattern) => pattern.test(message));
}

function isSafeHistoryTurn(turn: unknown): turn is SafeHistoryTurn {
  if (!turn || typeof turn !== "object") return false;
  const candidate = turn as Partial<SafeHistoryTurn>;
  return (
    (candidate.role === "user" || candidate.role === "assistant") &&
    typeof candidate.content === "string"
  );
}

function getSafeHistory(body: VoiceConciergeRequest): SafeHistoryTurn[] {
  return (Array.isArray(body.history) ? body.history : [])
    .filter(isSafeHistoryTurn)
    .slice(-MAX_HISTORY_ITEMS)
    .map((turn) => ({
      role: turn.role,
      content: turn.content.slice(0, MAX_MESSAGE_LENGTH),
    }));
}

function containsRequestPii(
  body: VoiceConciergeRequest,
  message: string,
): boolean {
  if (containsObviousPii(message)) return true;
  return getSafeHistory(body).some((turn) => containsObviousPii(turn.content));
}

function inferLocaleFromText(message: string): SupportedLocale {
  const normalized = message.toLowerCase();
  if (/[а-яё]/i.test(message)) return "ru";
  if (
    /(?:\bper una\b|\bciao\b|\bvorrei\b|\bposso\b|\baprire\b|\bsocieta\b|\bazienda\b|\bvisto\b|\bpermesso\b|\bquanto\b|\bcome\b|\bdevo\b|\bserve\b|\btasse\b|\bfiscale\b|\bproprieta\b|\blavorare\b|\binvestire\b|\bparti\b|\biniziamo\b|\bdal\b|\bdalla\b)/.test(
      normalized,
    )
  ) {
    return "it";
  }
  if (
    /\b(halo|saya|bisa|izin|pajak|perusahaan|properti|apakah|untuk|tinggal|kerja|membuka)\b/.test(
      normalized,
    )
  ) {
    return "id";
  }
  if (
    /\b(bonjour|puis-je|societe|impot|propriete|ouvrir|travailler)\b/.test(
      normalized,
    )
  ) {
    return "fr";
  }
  return "en";
}

function getLocale(
  body: VoiceConciergeRequest,
  message: string,
): SupportedLocale {
  return body.locale && SUPPORTED_LOCALES.has(body.locale)
    ? body.locale
    : inferLocaleFromText(message);
}

function inferIntent(message: string): ConciergeIntent {
  const normalized = message.toLowerCase();
  if (
    /\b(visa|visto|permesso|kitas|kitap|e33|e28|golden visa|immigration|immigrazione)\b/.test(
      normalized,
    )
  ) {
    return "visa";
  }
  if (
    /\b(pt pma|company|kbli|oss|business|cafe|restaurant|societa|azienda|attivita|perusahaan|usaha|membuka)\b/.test(
      normalized,
    )
  ) {
    return "company";
  }
  if (
    /\b(tax|tasse|fiscale|pajak|npwp|ppn|vat|spt|coretax)\b/.test(normalized)
  ) {
    return "tax";
  }
  if (
    /\b(property|proprieta|villa|land|terreno|zoning|lease|hgb|hak pakai|properti)\b/.test(
      normalized,
    )
  ) {
    return "property";
  }
  if (
    /\b(bpjs|payroll|employee|dipendenti|karyawan|permit|operations|operazioni|compliance|workflow)\b/.test(
      normalized,
    )
  ) {
    return "operations";
  }
  return "unknown";
}

function compactForSpeech(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= MAX_SPOKEN_ANSWER_LENGTH) return normalized;

  const firstSentence = normalized.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim();
  if (firstSentence && firstSentence.length <= MAX_SPOKEN_ANSWER_LENGTH) {
    return firstSentence;
  }

  const candidate = normalized.slice(0, MAX_SPOKEN_ANSWER_LENGTH + 1);
  const lastSpace = candidate.lastIndexOf(" ");
  const endIndex =
    lastSpace >= Math.floor(MAX_SPOKEN_ANSWER_LENGTH * 0.6)
      ? lastSpace
      : MAX_SPOKEN_ANSWER_LENGTH;
  return `${normalized.slice(0, endIndex).replace(/[,:;.\-\s]+$/, "")}.`;
}

function demoResponse(
  message: string,
  locale: SupportedLocale,
  safetyNote?: string,
): VoiceConciergeResponse {
  const intent = inferIntent(message);
  const byLocale: Record<
    "en" | "it" | "id",
    Record<ConciergeIntent, string>
  > = {
    en: {
      visa: "I can help triage the visa path, but keep this non-PII. Tell me your broad goal, nationality region, expected stay length, and whether this is work, investment, family, or retirement.",
      company:
        "For a PT PMA, the first useful checks are business activity, KBLI fit, foreign ownership limits, address/zoning, and whether the activity needs extra permits. Keep names and document numbers out for now.",
      tax: "For tax questions, we should separate personal residency, company obligations, VAT/PPN, payroll, and annual filing. Share only the scenario, not NPWP or client identifiers.",
      property:
        "For property, the first screen is legal title, zoning, access, building permits, lease/HGB structure, and buyer profile. Do not share parcel documents or owner names in this prototype.",
      operations:
        "For operations, I can classify the workflow and suggest the next Bali Zero team step. Keep employee names, phone numbers, and private case details out of the voice test.",
      unknown:
        "I can help route the question into visa, company, tax, property, or operations. Ask in plain language and avoid personal or document identifiers.",
    },
    it: {
      visa: "Posso aiutarti a fare triage sul percorso visa, restando fuori dai dati personali. Dimmi solo obiettivo generale, area di nazionalita, durata prevista e se riguarda lavoro, investimento, famiglia o retirement.",
      company:
        "Per una PT PMA, i primi controlli utili sono attivita, KBLI, limiti di proprieta straniera, indirizzo/zoning e permessi extra. Non inserire nomi o numeri documento in questo prototipo.",
      tax: "Per le tasse conviene separare residenza personale, obblighi societari, VAT/PPN, payroll e dichiarazione annuale. Descrivi solo lo scenario, senza NPWP o identificativi cliente.",
      property:
        "Per property, il primo filtro e titolo, zoning, accesso, permessi edilizi, struttura lease/HGB e profilo acquirente. Non condividere documenti catastali o nomi proprietari qui.",
      operations:
        "Per operations posso classificare il workflow e suggerire il prossimo step del team Bali Zero. Tieni fuori nomi dipendenti, telefoni e dettagli privati del case.",
      unknown:
        "Posso instradare la domanda su visa, company, tax, property o operations. Chiedi in linguaggio naturale ed evita identificativi personali o documentali.",
    },
    id: {
      visa: "Saya bisa membantu triage jalur visa tanpa data pribadi. Beri konteks umum: tujuan, wilayah kewarganegaraan, lama tinggal, dan apakah untuk kerja, investasi, keluarga, atau pensiun.",
      company:
        "Untuk PT PMA, pemeriksaan awalnya adalah aktivitas usaha, KBLI, batas kepemilikan asing, alamat/zoning, dan izin tambahan. Jangan masukkan nama atau nomor dokumen di prototipe ini.",
      tax: "Untuk pajak, pisahkan dulu residensi pribadi, kewajiban perusahaan, VAT/PPN, payroll, dan laporan tahunan. Bagikan skenario saja, tanpa NPWP atau identitas klien.",
      property:
        "Untuk properti, layar awalnya adalah status hak, zoning, akses, izin bangunan, struktur lease/HGB, dan profil pembeli. Jangan unggah dokumen tanah atau nama pemilik di sini.",
      operations:
        "Untuk operations, saya bisa mengklasifikasikan workflow dan menyarankan langkah tim Bali Zero berikutnya. Hindari nama karyawan, nomor telepon, dan detail case privat.",
      unknown:
        "Saya bisa mengarahkan pertanyaan ke visa, company, tax, property, atau operations. Tanyakan dengan bahasa natural tanpa identitas pribadi atau nomor dokumen.",
    },
  };
  const spokenByLocale: Record<
    "en" | "it" | "id",
    Record<ConciergeIntent, string>
  > = {
    en: {
      visa: "Visa triage ready. Share only broad, non-private context.",
      company: "PMA triage ready. Start with KBLI and zoning.",
      tax: "Tax triage ready. Keep NPWP and client IDs out.",
      property: "Property triage ready. Start with title and zoning.",
      operations: "Workflow triage ready. I can route the next team step.",
      unknown: "I can route this into visa, company, tax, property, or ops.",
    },
    it: {
      visa: "Triage visa pronto. Usa solo contesto generale, non privato.",
      company: "Triage PMA pronto. Parti da KBLI e zoning.",
      tax: "Triage fiscale pronto. Tieni fuori NPWP e dati cliente.",
      property: "Triage property pronto. Parti da titolo e zoning.",
      operations: "Triage workflow pronto. Posso instradare il prossimo step.",
      unknown: "Posso instradare su visa, company, tax, property o ops.",
    },
    id: {
      visa: "Triage visa siap. Pakai konteks umum saja.",
      company: "Triage PMA siap. Mulai dari KBLI dan zoning.",
      tax: "Triage pajak siap. Jangan masukkan NPWP atau identitas klien.",
      property: "Triage properti siap. Mulai dari status hak dan zoning.",
      operations: "Triage workflow siap. Saya bisa arahkan langkah tim.",
      unknown: "Saya bisa arahkan ke visa, company, tax, property, atau ops.",
    },
  };
  const byIntent = byLocale[locale === "it" || locale === "id" ? locale : "en"];
  const spokenByIntent =
    spokenByLocale[locale === "it" || locale === "id" ? locale : "en"];

  return {
    answer: byIntent[intent],
    spoken_answer: spokenByIntent[intent],
    intent,
    risk_level: intent === "unknown" ? "low" : "medium",
    next_action:
      intent === "unknown" ? "answer_only" : "collect_non_pii_context",
    quick_replies: [
      "What context can I share safely?",
      "Route this to the team",
      "Try another question",
    ],
    safety_note:
      safetyNote ??
      "Demo mode: no Gemini call was made because GOOGLE_AI_STUDIO_API_KEY or GEMINI_API_KEY is not configured.",
    mode: "demo",
    provider: "local-demo",
  };
}

function normalizeResponse(
  parsed: Partial<VoiceConciergeResponse>,
  model: string,
): VoiceConciergeResponse {
  const intent = parsed.intent ?? "unknown";
  const riskLevel = parsed.risk_level ?? "medium";
  const nextAction = parsed.next_action ?? "collect_non_pii_context";
  const answer =
    parsed.answer ??
    "I can help, but I need a clearer non-PII question before routing this.";
  const quickReplies = Array.isArray(parsed.quick_replies)
    ? parsed.quick_replies.slice(0, 4).filter((reply) => reply.trim())
    : [];

  return {
    answer,
    spoken_answer: compactForSpeech(parsed.spoken_answer ?? answer),
    intent,
    risk_level: riskLevel,
    next_action: nextAction,
    quick_replies:
      quickReplies.length > 0
        ? quickReplies
        : ["Add non-PII context", "Handoff to team"],
    safety_note:
      "Prototype guardrail: do not share passports, KTP, NPWP, phone numbers, emails, client names, or private CRM/WhatsApp details.",
    mode: "gemini",
    provider: "google-ai-studio",
    model,
  };
}

function parseGeminiJson(text: string): Partial<VoiceConciergeResponse> {
  const trimmed = text
    .trim()
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/```$/i, "")
    .trim();
  return JSON.parse(trimmed) as Partial<VoiceConciergeResponse>;
}

function buildContents(body: VoiceConciergeRequest, message: string) {
  return [
    {
      role: "user",
      parts: [
        {
          text: [
            `Locale preference: ${body.locale ?? "en"}`,
            "User voice turn:",
            message,
          ].join("\n"),
        },
      ],
    },
  ];
}

export async function POST(request: Request): Promise<NextResponse> {
  if (!isPrototypeEnabled()) {
    return NextResponse.json(
      { error: "voice_concierge_disabled" },
      { status: 404 },
    );
  }

  if (
    !(await canAccessVoiceConcierge(request, {
      technicalTokenEnv: "VOICE_CONCIERGE_TEXT_TOKEN",
    }))
  ) {
    return NextResponse.json(
      { error: "voice_concierge_forbidden" },
      { status: 403 },
    );
  }

  const body = (await request
    .json()
    .catch(() => ({}))) as VoiceConciergeRequest;
  const message = body.message?.trim().slice(0, MAX_MESSAGE_LENGTH);

  if (!message) {
    return NextResponse.json({ error: "message required" }, { status: 400 });
  }

  if (containsRequestPii(body, message)) {
    return NextResponse.json(
      {
        error: "pii_not_allowed",
        safety_note:
          "Remove passports, KTP, NPWP, phone numbers, emails, names, and document identifiers before using the voice concierge prototype.",
      },
      { status: 400 },
    );
  }

  const locale = getLocale(body, message);

  if (!isCloudTextAllowed()) {
    return NextResponse.json(
      demoResponse(
        message,
        locale,
        "Cloud text concierge disabled, so no Gemini call was made.",
      ),
    );
  }

  const apiKey = getApiKey();
  if (!apiKey) {
    return NextResponse.json(demoResponse(message, locale));
  }

  const model = getModel();
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
    model,
  )}:generateContent?key=${encodeURIComponent(apiKey)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(TEXT_PROVIDER_TIMEOUT_MS),
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
        contents: buildContents({ ...body, locale }, message),
        generationConfig: {
          temperature: 0.4,
          maxOutputTokens: 700,
          responseMimeType: "application/json",
          responseSchema: RESPONSE_SCHEMA,
        },
      }),
    });
  } catch {
    return NextResponse.json(
      { error: "gemini_request_failed" },
      { status: 502 },
    );
  }

  if (!response.ok) {
    return NextResponse.json(
      {
        error: "gemini_request_failed",
        status: response.status,
      },
      { status: 502 },
    );
  }

  const data = (await response.json()) as GeminiResponse;
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    return NextResponse.json(
      { error: "gemini_empty_response" },
      { status: 502 },
    );
  }

  try {
    return NextResponse.json(normalizeResponse(parseGeminiJson(text), model));
  } catch {
    return NextResponse.json({ error: "gemini_invalid_json" }, { status: 502 });
  }
}

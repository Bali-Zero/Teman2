import { query } from "./pg.js";
import { jidToPhone, parseJid } from "./filters.js";
import { normalizePhone } from "./phone.js";

export type Direction = "inbound" | "outbound";
export type ChatType = "direct" | "group";

export type MediaType =
  | "text"
  | "image"
  | "document"
  | "audio"
  | "video"
  | "sticker"
  | "location";

export type WaMirrorAccount = {
  phone: string;
  name: string;
};

export type CapturedMessageRecord = {
  baileysMessageId: string;
  direction: Direction;
  teamMemberPhone: string;
  counterpartPhone: string;
  body: string;
  timestamp: Date;
  mediaType: MediaType;
  mediaMime: string | null;
  mediaUrl: string | null;
  rawBaileysEvent: unknown;
  chatType: ChatType;
  groupJid: string | null;
  groupSubject: string | null;
  senderPhone: string | null;
  senderLid: string | null;
  senderJid: string | null;
  senderPushName: string | null;
};

export type PersistedMessageContext = CapturedMessageRecord & {
  id: number;
  clientId: number | null;
  practiceId: number | null;
  mediaStoredPath: string | null;
  ocrResult: unknown | null;
};

export type MessageContextStore = {
  upsertMessage(
    row: Omit<PersistedMessageContext, "id" | "mediaStoredPath" | "ocrResult">,
  ): Promise<{
    id: number;
    row: PersistedMessageContext;
  }>;
  updateMediaStoredPath(
    id: number,
    mediaStoredPath: string,
    ocrResult?: unknown | null,
  ): Promise<void>;
};

export type PersistDeps = {
  store: MessageContextStore;
  resolveClientId: (phone: string) => Promise<number | null>;
  resolvePracticeId: (clientId: number) => Promise<number | null>;
};

type BaileysMessageLike = {
  key?: {
    id?: string | null;
    fromMe?: boolean | null;
    remoteJid?: string | null;
    participant?: string | null;
    participantPn?: string | null;
    participantLid?: string | null;
  } | null;
  messageTimestamp?: number | string | { toNumber?: () => number } | null;
  message?: unknown;
  pushName?: string | null;
};

type MessageShape = {
  conversation?: string;
  extendedTextMessage?: { text?: string | null };
  imageMessage?: MediaMessageShape & { caption?: string | null };
  videoMessage?: MediaMessageShape & { caption?: string | null };
  documentMessage?: MediaMessageShape & {
    caption?: string | null;
    fileName?: string | null;
  };
  audioMessage?: MediaMessageShape;
  stickerMessage?: MediaMessageShape;
  locationMessage?: {
    degreesLatitude?: number | null;
    degreesLongitude?: number | null;
    name?: string | null;
    address?: string | null;
  };
};

type MediaMessageShape = {
  mimetype?: string | null;
  url?: string | null;
  directPath?: string | null;
};

export class PgMessageContextStore implements MessageContextStore {
  async upsertMessage(
    row: Omit<PersistedMessageContext, "id" | "mediaStoredPath" | "ocrResult">,
  ): Promise<{ id: number; row: PersistedMessageContext }> {
    const counterpartPhoneOrNull =
      row.counterpartPhone === "" ? null : row.counterpartPhone;
    const phoneNumberOrNull = counterpartPhoneOrNull;

    const result = await query<{ id: number }>(
      `INSERT INTO whatsapp_message_context
         (client_id, practice_id, direction, team_member_phone,
          counterpart_phone, body, message_text, phone_number, message_date,
          media_type, media_mime, media_url, raw_baileys_event,
          baileys_message_id, team_member_email, source,
          chat_type, group_jid, group_subject_snapshot,
          sender_phone, sender_lid, sender_jid, sender_push_name_snapshot)
       VALUES
         ($1, $2, $3, $4, $5, $6, $6, $14, $7, $8, $9, $10,
          $11::jsonb, $12, $4, 'wa_mirror',
          $13, $15, $16,
          $17, $18, $19, $20)
       ON CONFLICT (baileys_message_id) WHERE baileys_message_id IS NOT NULL
       DO UPDATE SET
         client_id = EXCLUDED.client_id,
         practice_id = EXCLUDED.practice_id,
         direction = EXCLUDED.direction,
         team_member_phone = EXCLUDED.team_member_phone,
         counterpart_phone = EXCLUDED.counterpart_phone,
         body = EXCLUDED.body,
         message_text = EXCLUDED.message_text,
         phone_number = EXCLUDED.phone_number,
         message_date = EXCLUDED.message_date,
         media_type = EXCLUDED.media_type,
         media_mime = EXCLUDED.media_mime,
         media_url = EXCLUDED.media_url,
         raw_baileys_event = EXCLUDED.raw_baileys_event,
         chat_type = EXCLUDED.chat_type,
         group_jid = EXCLUDED.group_jid,
         group_subject_snapshot = COALESCE(EXCLUDED.group_subject_snapshot, whatsapp_message_context.group_subject_snapshot),
         sender_phone = EXCLUDED.sender_phone,
         sender_lid = EXCLUDED.sender_lid,
         sender_jid = EXCLUDED.sender_jid,
         sender_push_name_snapshot = EXCLUDED.sender_push_name_snapshot,
         updated_at = NOW()
       RETURNING id`,
      [
        row.clientId,
        row.practiceId,
        row.direction,
        row.teamMemberPhone,
        counterpartPhoneOrNull,
        row.body,
        row.timestamp.toISOString(),
        row.mediaType,
        row.mediaMime,
        row.mediaUrl,
        safeJson(row.rawBaileysEvent),
        row.baileysMessageId,
        row.chatType,
        phoneNumberOrNull,
        row.groupJid,
        row.groupSubject,
        row.senderPhone,
        row.senderLid,
        row.senderJid,
        row.senderPushName,
      ],
    );
    const id = result.rows[0].id;
    return {
      id,
      row: {
        ...row,
        id,
        mediaStoredPath: null,
        ocrResult: null,
      },
    };
  }

  async updateMediaStoredPath(
    id: number,
    mediaStoredPath: string,
    ocrResult: unknown | null = null,
  ): Promise<void> {
    await query(
      `UPDATE whatsapp_message_context
          SET media_stored_path = $2,
              ocr_result = COALESCE($3::jsonb, ocr_result),
              updated_at = NOW()
        WHERE id = $1`,
      [id, mediaStoredPath, ocrResult === null ? null : safeJson(ocrResult)],
    );
  }
}

export class InMemoryMessageContextStore implements MessageContextStore {
  readonly rows: PersistedMessageContext[] = [];
  #nextId = 1;

  async upsertMessage(
    row: Omit<PersistedMessageContext, "id" | "mediaStoredPath" | "ocrResult">,
  ): Promise<{ id: number; row: PersistedMessageContext }> {
    const existing = this.rows.find(
      (candidate) => candidate.baileysMessageId === row.baileysMessageId,
    );
    if (existing) {
      Object.assign(existing, row);
      return { id: existing.id, row: existing };
    }

    const inserted: PersistedMessageContext = {
      ...row,
      id: this.#nextId,
      mediaStoredPath: null,
      ocrResult: null,
    };
    this.#nextId += 1;
    this.rows.push(inserted);
    return { id: inserted.id, row: inserted };
  }

  async updateMediaStoredPath(
    id: number,
    mediaStoredPath: string,
    ocrResult: unknown | null = null,
  ): Promise<void> {
    const row = this.rows.find((candidate) => candidate.id === id);
    if (!row) return;
    row.mediaStoredPath = mediaStoredPath;
    row.ocrResult = ocrResult;
  }
}

export async function persistCapturedMessage(
  message: CapturedMessageRecord,
  deps: PersistDeps,
): Promise<{ id: number; row: PersistedMessageContext }> {
  const clientId = await deps.resolveClientId(message.counterpartPhone);
  const practiceId =
    clientId === null ? null : await deps.resolvePracticeId(clientId);

  return deps.store.upsertMessage({
    ...message,
    clientId,
    practiceId,
  });
}

export function extractMessageRecord(
  raw: BaileysMessageLike,
  account: WaMirrorAccount,
): CapturedMessageRecord | null {
  const message = raw.message;
  if (!message) return null;

  const teamMemberPhone = normalizePhone(account.phone);
  if (!teamMemberPhone) return null;

  const remoteJid = raw.key?.remoteJid ?? null;
  const parsed = parseJid(remoteJid);

  if (parsed.kind === "group") {
    const participantRaw = raw.key?.participant ?? null;
    const participantParsed = parseJid(participantRaw);
    const senderPhoneFromPn = raw.key?.participantPn
      ? normalizePhone(jidToPhone(raw.key.participantPn))
      : "";
    const senderPhone =
      senderPhoneFromPn ||
      (participantParsed.kind === "phone" ? participantParsed.phone : "") ||
      null;
    const senderLid =
      (raw.key?.participantLid ? parseJid(raw.key.participantLid).lid : "") ||
      (participantParsed.kind === "lid" ? participantParsed.lid : "") ||
      null;

    const media = extractMedia(message);
    const body = extractBody(message, media.mediaType);
    const timestamp = parseTimestamp(raw.messageTimestamp);
    const direction: Direction = raw.key?.fromMe ? "outbound" : "inbound";
    const groupJid = remoteJid ?? "";
    const messageId =
      raw.key?.id ??
      `${teamMemberPhone}:group:${groupJid}:${timestamp.getTime()}:${direction}`;

    return {
      baileysMessageId: messageId,
      direction,
      teamMemberPhone,
      counterpartPhone: "",
      body,
      timestamp,
      mediaType: media.mediaType,
      mediaMime: media.mediaMime,
      mediaUrl: media.mediaUrl,
      rawBaileysEvent: raw,
      chatType: "group",
      groupJid,
      groupSubject: null,
      senderPhone,
      senderLid,
      senderJid: participantRaw,
      senderPushName: raw.pushName ?? null,
    };
  }

  const counterpartPhone = normalizePhone(jidToPhone(remoteJid));
  if (!counterpartPhone) return null;
  if (counterpartPhone === teamMemberPhone) return null;

  const media = extractMedia(message);
  const body = extractBody(message, media.mediaType);
  const timestamp = parseTimestamp(raw.messageTimestamp);
  const direction: Direction = raw.key?.fromMe ? "outbound" : "inbound";
  const messageId =
    raw.key?.id ??
    `${teamMemberPhone}:${counterpartPhone}:${timestamp.getTime()}:${direction}`;

  return {
    baileysMessageId: messageId,
    direction,
    teamMemberPhone,
    counterpartPhone,
    body,
    timestamp,
    mediaType: media.mediaType,
    mediaMime: media.mediaMime,
    mediaUrl: media.mediaUrl,
    rawBaileysEvent: raw,
    chatType: "direct",
    groupJid: null,
    groupSubject: null,
    senderPhone: null,
    senderLid: null,
    senderJid: null,
    senderPushName: raw.pushName ?? null,
  };
}

function extractBody(message: unknown, mediaType: MediaType): string {
  const m = (message ?? {}) as MessageShape;
  if (typeof m.conversation === "string" && m.conversation.length > 0) {
    return m.conversation;
  }
  if (m.extendedTextMessage?.text) return m.extendedTextMessage.text;
  if (m.imageMessage?.caption) return m.imageMessage.caption;
  if (m.videoMessage?.caption) return m.videoMessage.caption;
  if (m.documentMessage?.caption) return m.documentMessage.caption;
  if (mediaType === "text") return "";
  return "";
}

function extractMedia(message: unknown): {
  mediaType: MediaType;
  mediaMime: string | null;
  mediaUrl: string | null;
} {
  const m = (message ?? {}) as MessageShape;
  if (m.imageMessage) return mediaMeta("image", m.imageMessage);
  if (m.documentMessage) return mediaMeta("document", m.documentMessage);
  if (m.audioMessage) return mediaMeta("audio", m.audioMessage);
  if (m.videoMessage) return mediaMeta("video", m.videoMessage);
  if (m.stickerMessage) return mediaMeta("sticker", m.stickerMessage);
  if (m.locationMessage) {
    return { mediaType: "location", mediaMime: null, mediaUrl: null };
  }
  return { mediaType: "text", mediaMime: null, mediaUrl: null };
}

function mediaMeta(
  mediaType: MediaType,
  media: MediaMessageShape,
): {
  mediaType: MediaType;
  mediaMime: string | null;
  mediaUrl: string | null;
} {
  return {
    mediaType,
    mediaMime: media.mimetype ?? null,
    mediaUrl: media.url ?? media.directPath ?? null,
  };
}

function parseTimestamp(value: BaileysMessageLike["messageTimestamp"]): Date {
  if (typeof value === "number") return new Date(value * 1000);
  if (typeof value === "string") return new Date(Number(value) * 1000);
  if (value && typeof value.toNumber === "function") {
    return new Date(value.toNumber() * 1000);
  }
  return new Date();
}

function safeJson(value: unknown): string {
  return JSON.stringify(value, (_key, item: unknown) => {
    if (typeof item === "bigint") return item.toString();
    if (item instanceof Uint8Array) {
      return Buffer.from(item).toString("base64");
    }
    return item;
  });
}

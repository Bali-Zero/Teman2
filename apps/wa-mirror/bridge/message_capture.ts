import { query } from "./pg.js";
import { jidToPhone, parseJid } from "./filters.js";
import { normalizePhone } from "./phone.js";
import { getGroupSubject } from "./group_subject.js";

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
  /**
   * FIX 4 (2026-05-26): team_member_email separated from team_member_phone.
   * Pre-fix: SQL `team_member_email = $4` reused the phone param, so CRM
   * joins on @balizero.com email broke. Empty string means "unknown email"
   * — caller may default to "" when manifest does not provide it.
   */
  email?: string;
};

export type CapturedMessageRecord = {
  baileysMessageId: string;
  direction: Direction;
  teamMemberPhone: string;
  /**
   * FIX 4 (2026-05-26): explicit email, distinct from phone. Default "" when
   * manifest does not declare it (CRM join handles "" as "unmapped team
   * member"). Pre-fix SQL reused $4 (phone) for team_member_email which
   * broke joins on @balizero.com.
   */
  teamMemberEmail: string;
  counterpartPhone: string;
  // CICATRIX 2026-05-25: direct messages on WA Multi-Device arrive as `@lid`
  // (Linked Identity) without a phone yet. Pre-fix the bridge silently dropped
  // 100% of LID-only direct chats (group cipher = SenderKey still worked, only
  // direct Signal pairwise sessions surfaced as @lid). Async resolver maps
  // counterpart_lid → phone later via wa_lid_phone_resolution materialized view.
  counterpartLid: string | null;
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
  /**
   * FIX 3 (2026-05-26): optional Baileys `signalRepository.lidMapping.getPNForLID`
   * reverse-lookup. When `counterpartPhone` is empty but `counterpartLid` is set
   * (direct-LID messages from privacy-shielded contacts), this resolver fills
   * the phone synchronously inline so the CRM `findClientByPhone` join can run
   * on the same persist. Returns null when the LID has never been observed
   * (Baileys mapping cache miss) — caller falls back to the existing
   * `counterpartPhone === ""` behaviour and the async resolver picks up later.
   */
  resolveLidToPhone?: (lid: string) => Promise<string | null>;
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

    // FIX 4 (2026-05-26): team_member_email moved off $4 (phone). Now a
    // dedicated $21 param sourced from row.teamMemberEmail. Default "" is
    // accepted by the column.
    // MERGE 2026-05-26: keep counterpart_lid from main (932573ae7) as $22
    // (was $21 in main pre-merge; renumbered because $21 is now email).
    const result = await query<{ id: number }>(
      `INSERT INTO whatsapp_message_context
         (client_id, practice_id, direction, team_member_phone,
          counterpart_phone, body, message_text, phone_number, message_date,
          media_type, media_mime, media_url, raw_baileys_event,
          baileys_message_id, team_member_email, source,
          chat_type, group_jid, group_subject_snapshot,
          sender_phone, sender_lid, sender_jid, sender_push_name_snapshot,
          counterpart_lid)
       VALUES
         ($1, $2, $3, $4, $5, $6, $6, $14, $7, $8, $9, $10,
          $11::jsonb, $12, $21, 'wa_mirror',
          $13, $15, $16,
          $17, $18, $19, $20,
          $22)
       ON CONFLICT (baileys_message_id) WHERE baileys_message_id IS NOT NULL
       DO UPDATE SET
         client_id = EXCLUDED.client_id,
         practice_id = EXCLUDED.practice_id,
         direction = EXCLUDED.direction,
         team_member_phone = EXCLUDED.team_member_phone,
         counterpart_phone = EXCLUDED.counterpart_phone,
         counterpart_lid = COALESCE(EXCLUDED.counterpart_lid, whatsapp_message_context.counterpart_lid),
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
        row.teamMemberEmail ?? "", // $21
        row.counterpartLid, // $22
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
  // FIX 3 (2026-05-26): LID→phone reverse-lookup via Baileys lidMapping.
  // Resolves CRM client_id for direct-LID messages (privacy-shielded
  // contacts). When the resolver returns a phone, mutate the message in
  // place so the persisted row carries the resolved counterpartPhone /
  // senderPhone — otherwise the row only ever holds the LID and the JOIN
  // to clients (which is keyed on phone) keeps missing.
  if (deps.resolveLidToPhone) {
    if (!message.counterpartPhone && message.counterpartLid) {
      const resolvedPhone = await deps.resolveLidToPhone(
        message.counterpartLid,
      );
      if (resolvedPhone) {
        message.counterpartPhone = resolvedPhone;
      }
    }
    if (!message.senderPhone && message.senderLid) {
      const resolvedSender = await deps.resolveLidToPhone(message.senderLid);
      if (resolvedSender) {
        message.senderPhone = resolvedSender;
      }
    }
  }

  // FIX 3 (2026-05-26): on group messages counterpartPhone is always "" (the
  // chat is identified by groupJid, not by a single phone). The CRM lookup
  // must use the SENDER phone to attribute the message to a client.
  const lookupPhone =
    message.chatType === "group"
      ? (message.senderPhone ?? "")
      : message.counterpartPhone;
  const clientId = lookupPhone ? await deps.resolveClientId(lookupPhone) : null;
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

  // FIX 2 (2026-05-26): skip protocol/reaction/poll-update envelopes that
  // carry no user-facing body. Persisting them produced row-noise downstream
  // (empty body, NULL media, no clientId match attempt makes sense).
  const ctrlMsg = message as {
    protocolMessage?: unknown;
    reactionMessage?: unknown;
    pollUpdateMessage?: unknown;
  };
  if (
    ctrlMsg.protocolMessage ||
    ctrlMsg.reactionMessage ||
    ctrlMsg.pollUpdateMessage
  ) {
    return null;
  }

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
      teamMemberEmail: account.email ?? "",
      counterpartPhone: "",
      counterpartLid: null,
      body,
      timestamp,
      mediaType: media.mediaType,
      mediaMime: media.mediaMime,
      mediaUrl: media.mediaUrl,
      rawBaileysEvent: raw,
      chatType: "group",
      groupJid,
      // FIX (2026-06-30): group name comes from Baileys group metadata, never
      // from the message envelope. The group_subject cache is hydrated on
      // connection open (session.ts) + kept fresh by groups.update listeners.
      // Falls back to null (prior behaviour) when the subject isn't cached yet;
      // the INSERT's COALESCE(EXCLUDED, existing) preserves any earlier value.
      groupSubject: getGroupSubject(groupJid),
      senderPhone,
      senderLid,
      senderJid: participantRaw,
      senderPushName: raw.pushName ?? null,
    };
  }

  // === CICATRIX 2026-05-25 + FIX 1 2026-05-26 — DIRECT branch w/ @lid fallback ===
  // 932573ae7 (main): accept kind === "lid" → store counterpart_lid; async
  //   attribution via wa_lid_phone_resolution materialized view.
  // 4c071cf48 (this PR): preserve self-note outbound (counterpartPhone ===
  //   teamMemberPhone && raw.key.fromMe === true) as legitimate, only drop
  //   when fromMe=false (echo).
  // Merge: main's counterpartLid + self-note nuance from 4c071cf48.
  const isPhone = parsed.kind === "phone";
  const isLid = parsed.kind === "lid";
  if (!isPhone && !isLid) return null;

  const counterpartPhone = isPhone ? normalizePhone(parsed.phone) : "";
  const counterpartLid = isLid ? parsed.lid : null;
  if (isPhone && !counterpartPhone) return null;
  // FIX 1 (2026-05-26): self-note outbound (fromMe=true on own JID) is legit.
  if (
    counterpartPhone &&
    counterpartPhone === teamMemberPhone &&
    raw.key?.fromMe === false
  ) {
    return null;
  }
  // directSenderLid kept as alias for senderLid persistence below (parity
  // with main's senderJid=remoteJid binding when chat is LID-direct).
  const directSenderLid: string | null = counterpartLid;

  const media = extractMedia(message);
  const body = extractBody(message, media.mediaType);
  const timestamp = parseTimestamp(raw.messageTimestamp);
  const direction: Direction = raw.key?.fromMe ? "outbound" : "inbound";
  // Stable conv key for messageId fallback (prefer phone, else lid)
  const convKey =
    counterpartPhone || (counterpartLid ? `lid:${counterpartLid}` : "unknown");
  const messageId =
    raw.key?.id ??
    `${teamMemberPhone}:${convKey}:${timestamp.getTime()}:${direction}`;

  return {
    baileysMessageId: messageId,
    direction,
    teamMemberPhone,
    teamMemberEmail: account.email ?? "",
    counterpartPhone,
    counterpartLid,
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
    senderLid: directSenderLid,
    senderJid: remoteJid,
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
  // FIX 12 (2026-05-26): fallback to now() when the string is not numeric.
  // Pre-fix `Number(value)` could return NaN → `new Date(NaN)` produces
  // an Invalid Date that crashes ISO serialization downstream.
  if (typeof value === "string") {
    const n = Number(value);
    if (!Number.isFinite(n)) return new Date();
    return new Date(n * 1000);
  }
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

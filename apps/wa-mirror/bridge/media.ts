import { downloadMediaMessage } from "@whiskeysockets/baileys";
import type { WASocket } from "@whiskeysockets/baileys";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import pino from "pino";

import type {
  CapturedMessageRecord,
  MessageContextStore,
} from "./message_capture.js";
import { phonePathSegment } from "./phone.js";

// Module-level logger for helpers that do not receive a pino.Logger from
// the caller (e.g. scanRoutersForOcrEndpoint). Inherits log level from env.
const mlogger = pino({
  level: process.env.WA_MIRROR_LOG_LEVEL ?? "info",
  base: { component: "media" },
});

const DEFAULT_MEDIA_ROOT = path.join(homedir(), "wa-mirror-media");
let ocrEndpointExists: Promise<boolean> | null = null;

export function queueMediaDownload(opts: {
  sock: WASocket;
  rawMessage: unknown;
  messageContextId: number;
  record: CapturedMessageRecord;
  store: MessageContextStore;
  logger: pino.Logger;
}): void {
  if (
    opts.record.mediaType === "text" ||
    opts.record.mediaType === "location"
  ) {
    return;
  }

  setImmediate(() => {
    void downloadWithRetry(opts);
  });
}

// FIX (2026-06-30): the previous `.catch(() => warn("failed"))` swallowed the
// real error (no err.message, no mediaType, no retry) — a silent ~2% media
// loss that read as healthy (cicatrix #2 "Esiste≠Armato"). Now: one retry with
// backoff for transient failures (network flap, reupload-request races), and a
// structured warn carrying the actual error + mediaType so failures are
// observable and triageable. Permanent failures (expired WhatsApp CDN media,
// ~14-day TTL) still fail — but now visibly, with the reason.
const MEDIA_DOWNLOAD_RETRIES = 1;
const MEDIA_RETRY_BACKOFF_MS = 2000;

async function downloadWithRetry(opts: {
  sock: WASocket;
  rawMessage: unknown;
  messageContextId: number;
  record: CapturedMessageRecord;
  store: MessageContextStore;
  logger: pino.Logger;
}): Promise<void> {
  for (let attempt = 0; attempt <= MEDIA_DOWNLOAD_RETRIES; attempt++) {
    try {
      await downloadAndStoreMedia(opts);
      if (attempt > 0) {
        opts.logger.info(
          {
            messageContextId: opts.messageContextId,
            mediaType: opts.record.mediaType,
            attempt,
          },
          "wa-mirror media download recovered on retry",
        );
      }
      return;
    } catch (err) {
      const isLast = attempt === MEDIA_DOWNLOAD_RETRIES;
      opts.logger.warn(
        {
          messageContextId: opts.messageContextId,
          mediaType: opts.record.mediaType,
          attempt,
          willRetry: !isLast,
          err: (err as Error).message,
        },
        "wa-mirror media download failed",
      );
      if (isLast) return;
      await new Promise((r) =>
        setTimeout(r, MEDIA_RETRY_BACKOFF_MS * (attempt + 1)),
      );
    }
  }
}

async function downloadAndStoreMedia(opts: {
  sock: WASocket;
  rawMessage: unknown;
  messageContextId: number;
  record: CapturedMessageRecord;
  store: MessageContextStore;
  logger: pino.Logger;
}): Promise<void> {
  const buffer = await downloadMediaMessage(
    opts.rawMessage as never,
    "buffer",
    {},
    {
      logger: opts.logger,
      reuploadRequest: opts.sock.updateMediaMessage,
    },
  );

  const mediaRoot = process.env.WA_MIRROR_MEDIA_ROOT ?? DEFAULT_MEDIA_ROOT;
  const isGroup = opts.record.chatType === "group" && !!opts.record.groupJid;
  const segment = isGroup
    ? "groups/" + (opts.record.groupJid ?? "").replace(/[^a-zA-Z0-9_.-]/g, "_")
    : phonePathSegment(opts.record.counterpartPhone);
  const contactDir = path.join(mediaRoot, segment);
  await mkdir(contactDir, { recursive: true });

  const ext = extensionForMime(opts.record.mediaMime, opts.record.mediaType);
  const safeId = opts.record.baileysMessageId.replace(/[^a-zA-Z0-9_.-]/g, "_");
  const filePath = path.join(contactDir, `${safeId}.${ext}`);
  await writeFile(filePath, buffer);

  const ocrResult = await maybeRunOcr(
    filePath,
    opts.record.mediaMime,
    opts.logger,
  );
  await opts.store.updateMediaStoredPath(
    opts.messageContextId,
    filePath,
    ocrResult,
  );
}

export function extensionForMime(
  mime: string | null,
  mediaType: string,
): string {
  switch (mime) {
    case "image/jpeg":
      return "jpg";
    case "image/png":
      return "png";
    case "application/pdf":
      return "pdf";
    case "audio/ogg":
      return "ogg";
    case "audio/mpeg":
      return "mp3";
    case "video/mp4":
      return "mp4";
    case "image/webp":
      return "webp";
    default:
      // FIX 8 (2026-05-26): explicit extension defaults per mediaType so
      // unknown/missing MIME does not write `audio` / `sticker` / `video`
      // as the extension on disk (which broke any downstream tool that
      // routes by file extension).
      switch (mediaType) {
        case "audio":
          return "ogg";
        case "sticker":
          return "webp";
        case "video":
          return "mp4";
        case "image":
          return "jpg";
        case "document":
          return "bin";
        default:
          return "bin";
      }
  }
}

async function maybeRunOcr(
  filePath: string,
  mime: string | null,
  logger: pino.Logger,
): Promise<unknown | null> {
  if (!["image/jpeg", "image/png", "application/pdf"].includes(mime ?? "")) {
    return null;
  }

  if (!(await hasOcrEndpoint())) {
    logger.info({ mime }, "wa-mirror OCR endpoint not found; skipping");
    return null;
  }

  const baseUrl = process.env.WA_MIRROR_BACKEND_URL ?? "http://127.0.0.1:8000";
  const endpoint =
    process.env.WA_MIRROR_OCR_ENDPOINT ?? `${baseUrl}/api/ocr/extract`;

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ file_path: filePath }),
    });
    if (!response.ok) {
      logger.warn({ status: response.status }, "wa-mirror OCR request failed");
      return null;
    }
    return response.json();
  } catch (err) {
    logger.warn({ err: (err as Error).message }, "wa-mirror OCR request threw");
    return null;
  }
}

async function hasOcrEndpoint(): Promise<boolean> {
  if (process.env.WA_MIRROR_FORCE_OCR === "1") return true;
  if (process.env.WA_MIRROR_DISABLE_OCR === "1") return false;
  ocrEndpointExists ??= scanRoutersForOcrEndpoint();
  return ocrEndpointExists;
}

async function scanRoutersForOcrEndpoint(): Promise<boolean> {
  const repoRoot =
    process.env.WA_MIRROR_REPO_ROOT ?? path.resolve(process.cwd(), "../..");
  const routersDir = path.join(
    repoRoot,
    "apps/backend-rag/backend/app/routers",
  );
  try {
    const files = await listPythonFiles(routersDir);
    for (const file of files) {
      const content = await readFile(file, "utf8");
      if (
        content.includes("/api/ocr/extract") ||
        content.includes("ocr/extract")
      ) {
        return true;
      }
    }
  } catch (err) {
    mlogger.warn(
      { err: (err as Error).message, routersDir },
      "wa-mirror scanRoutersForOcrEndpoint failed",
    );
    return false;
  }
  return false;
}

async function listPythonFiles(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listPythonFiles(fullPath)));
    } else if (entry.isFile() && entry.name.endsWith(".py")) {
      files.push(fullPath);
    }
  }
  return files;
}

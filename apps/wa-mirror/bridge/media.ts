import { downloadMediaMessage } from "@whiskeysockets/baileys";
import type { WASocket } from "@whiskeysockets/baileys";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import type pino from "pino";

import type {
  CapturedMessageRecord,
  MessageContextStore,
} from "./message_capture.js";
import { phonePathSegment } from "./phone.js";

const DEFAULT_MEDIA_ROOT = path.join(homedir(), "wa-mirror-media");
let ocrEndpointExists: Promise<boolean> | null = null;

function errorType(err: unknown): string {
  return err instanceof Error && err.name ? err.name : typeof err;
}

export function queueMediaDownload(opts: {
  sock: WASocket;
  rawMessage: unknown;
  messageContextId: number;
  record: CapturedMessageRecord;
  store: MessageContextStore;
  logger: pino.Logger;
}): void {
  if (opts.record.mediaType === "text" || opts.record.mediaType === "location") {
    return;
  }

  setImmediate(() => {
    downloadAndStoreMedia(opts).catch((err) => {
      opts.logger.warn(
        {
          errorType: errorType(err),
          messageContextId: opts.messageContextId,
        },
        "wa-mirror media download failed"
      );
    });
  });
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
    }
  );

  const mediaRoot = process.env.WA_MIRROR_MEDIA_ROOT ?? DEFAULT_MEDIA_ROOT;
  const contactDir = path.join(
    mediaRoot,
    phonePathSegment(opts.record.counterpartPhone)
  );
  await mkdir(contactDir, { recursive: true });

  const ext = extensionForMime(opts.record.mediaMime, opts.record.mediaType);
  const safeId = opts.record.baileysMessageId.replace(/[^a-zA-Z0-9_.-]/g, "_");
  const filePath = path.join(contactDir, `${safeId}.${ext}`);
  await writeFile(filePath, buffer);

  const ocrResult = await maybeRunOcr(filePath, opts.record.mediaMime, opts.logger);
  await opts.store.updateMediaStoredPath(
    opts.messageContextId,
    filePath,
    ocrResult
  );
}

export function extensionForMime(
  mime: string | null,
  mediaType: string
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
      return mediaType === "document" ? "bin" : mediaType;
  }
}

async function maybeRunOcr(
  filePath: string,
  mime: string | null,
  logger: pino.Logger
): Promise<unknown | null> {
  if (!["image/jpeg", "image/png", "application/pdf"].includes(mime ?? "")) {
    return null;
  }

  if (!(await hasOcrEndpoint())) {
    logger.info({ mime }, "wa-mirror OCR endpoint not found; skipping");
    return null;
  }

  const baseUrl =
    process.env.WA_MIRROR_BACKEND_URL ?? "http://127.0.0.1:8000";
  const endpoint =
    process.env.WA_MIRROR_OCR_ENDPOINT ?? `${baseUrl}/api/ocr/extract`;

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ file_path: filePath }),
    });
    if (!response.ok) {
      logger.warn(
        { status: response.status },
        "wa-mirror OCR request failed"
      );
      return null;
    }
    return response.json();
  } catch (err) {
    logger.warn({ errorType: errorType(err) }, "wa-mirror OCR request threw");
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
    "apps/backend-rag/backend/app/routers"
  );
  try {
    const files = await listPythonFiles(routersDir);
    for (const file of files) {
      const content = await readFile(file, "utf8");
      if (content.includes("/api/ocr/extract") || content.includes("ocr/extract")) {
        return true;
      }
    }
  } catch {
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

import { NextResponse } from "next/server";
import {
  canAccessVoiceConcierge,
  getVoiceConciergeBackendBaseUrl,
  getVoiceConciergeInternalApiKey,
} from "../auth";

export const runtime = "nodejs";

const DEFAULT_AUDIO_MAX_BYTES = 10 * 1024 * 1024;
const MULTIPART_OVERHEAD_ALLOWANCE = 64 * 1024;
const BACKEND_TRANSCRIBE_TIMEOUT_MS = 35_000;

const ALLOWED_AUDIO_TYPES = new Set([
  "audio/wav",
  "audio/x-wav",
  "audio/mpeg",
  "audio/mp3",
  "audio/mp4",
  "audio/webm",
  "audio/ogg",
]);

function isPrototypeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" ||
    process.env.VOICE_CONCIERGE_LAB_ENABLED === "true"
  );
}

function isLocalAudioEnabled(): boolean {
  return (
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO === "true" ||
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO_ENABLED === "true"
  );
}

function getAudioMaxBytes(): number {
  const configured = Number.parseInt(
    process.env.VOICE_CONCIERGE_AUDIO_MAX_BYTES ?? "",
    10,
  );
  return Number.isFinite(configured) && configured > 0
    ? configured
    : DEFAULT_AUDIO_MAX_BYTES;
}

function mediaType(contentType: string): string {
  return contentType.split(";")[0]?.trim().toLowerCase() ?? "";
}

function isFilePart(value: FormDataEntryValue): value is File {
  return (
    typeof value === "object" &&
    value !== null &&
    "name" in value &&
    typeof value.name === "string" &&
    "size" in value &&
    typeof value.size === "number" &&
    "type" in value &&
    typeof value.type === "string" &&
    "arrayBuffer" in value &&
    typeof value.arrayBuffer === "function"
  );
}

function rejectDeclaredOversizedRequest(
  request: Request,
  maxAudioBytes: number,
): NextResponse | undefined {
  const contentLength = request.headers.get("content-length");
  if (!contentLength) {
    return NextResponse.json(
      { error: "content_length_required" },
      { status: 411 },
    );
  }

  const declaredBytes = Number.parseInt(contentLength, 10);
  if (
    !Number.isFinite(declaredBytes) ||
    declaredBytes < 0 ||
    declaredBytes.toString() !== contentLength.trim()
  ) {
    return NextResponse.json(
      { error: "invalid_content_length" },
      { status: 400 },
    );
  }

  if (declaredBytes > maxAudioBytes + MULTIPART_OVERHEAD_ALLOWANCE) {
    return NextResponse.json(
      { error: "audio_payload_too_large" },
      { status: 413 },
    );
  }

  return undefined;
}

function getSingleAudioFile(form: FormData): File | NextResponse {
  const files = Array.from(form.entries()).filter(
    (entry): entry is [string, File] => isFilePart(entry[1]),
  );

  if (files.length !== 1 || files[0]?.[0] !== "file") {
    return NextResponse.json(
      { error: "exactly_one_audio_file_required" },
      { status: 400 },
    );
  }

  const file = files[0][1];
  if (file.size === 0) {
    return NextResponse.json({ error: "empty_audio_file" }, { status: 422 });
  }

  if (!ALLOWED_AUDIO_TYPES.has(mediaType(file.type))) {
    return NextResponse.json(
      { error: "unsupported_audio_content_type" },
      { status: 415 },
    );
  }

  return file;
}

function getLanguage(form: FormData): string | undefined {
  const language = form.get("language");
  if (typeof language !== "string") return undefined;

  const trimmed = language.trim();
  return trimmed ? trimmed : undefined;
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
      technicalTokenEnv: "VOICE_CONCIERGE_TRANSCRIBE_TOKEN",
    }))
  ) {
    return NextResponse.json(
      { error: "voice_concierge_transcribe_forbidden" },
      { status: 403 },
    );
  }

  if (!isLocalAudioEnabled()) {
    return NextResponse.json(
      { error: "local_audio_disabled" },
      { status: 503 },
    );
  }

  const apiKey = getVoiceConciergeInternalApiKey();
  if (!apiKey) {
    return NextResponse.json(
      { error: "internal_api_key_missing" },
      { status: 503 },
    );
  }

  const backendBaseUrl = getVoiceConciergeBackendBaseUrl();
  if (!backendBaseUrl) {
    return NextResponse.json({ error: "backend_url_missing" }, { status: 503 });
  }

  const maxAudioBytes = getAudioMaxBytes();
  const sizeRejection = rejectDeclaredOversizedRequest(request, maxAudioBytes);
  if (sizeRejection) return sizeRejection;

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "exactly_one_audio_file_required" },
      { status: 400 },
    );
  }

  const file = getSingleAudioFile(form);
  if (file instanceof NextResponse) return file;

  if (file.size > maxAudioBytes) {
    return NextResponse.json(
      { error: "audio_payload_too_large" },
      { status: 413 },
    );
  }

  const forwardedForm = new FormData();
  const forwardedBlob = new Blob([await file.arrayBuffer()], {
    type: file.type,
  });
  forwardedForm.append("file", forwardedBlob, file.name);
  const language = getLanguage(form);
  if (language) forwardedForm.append("language", language);

  try {
    const response = await fetch(
      `${backendBaseUrl}/api/voice/local-audio/transcribe`,
      {
        method: "POST",
        headers: { "X-API-Key": apiKey },
        redirect: "error",
        signal: AbortSignal.timeout(BACKEND_TRANSCRIBE_TIMEOUT_MS),
        body: forwardedForm,
      },
    );

    if (!response.ok) {
      return NextResponse.json(
        { error: "backend_transcribe_failed" },
        { status: 502 },
      );
    }

    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json(
      { error: "backend_transcribe_failed" },
      { status: 502 },
    );
  }
}

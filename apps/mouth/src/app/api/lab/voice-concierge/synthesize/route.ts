import { NextResponse } from "next/server";
import {
  canAccessVoiceConcierge,
  getVoiceConciergeBackendBaseUrl,
  getVoiceConciergeInternalApiKey,
} from "../auth";

export const runtime = "nodejs";

const DEFAULT_TTS_MAX_CHARS = 1200;
const DEFAULT_TTS_AUDIO_MAX_BYTES = 10 * 1024 * 1024;
const DEFAULT_BACKEND_SYNTHESIZE_TIMEOUT_MS = 240_000;

interface SynthesizeRequestBody {
  text?: unknown;
  language?: unknown;
}

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

function getTtsMaxChars(): number {
  const configured = Number.parseInt(
    process.env.VOICE_CONCIERGE_TTS_MAX_CHARS ?? "",
    10,
  );
  return Number.isFinite(configured) && configured > 0
    ? configured
    : DEFAULT_TTS_MAX_CHARS;
}

function getTtsAudioMaxBytes(): number {
  const configured = Number.parseInt(
    process.env.VOICE_CONCIERGE_TTS_AUDIO_MAX_BYTES ?? "",
    10,
  );
  return Number.isFinite(configured) && configured > 0
    ? configured
    : DEFAULT_TTS_AUDIO_MAX_BYTES;
}

function getBackendSynthesizeTimeoutMs(): number {
  const configured = Number.parseInt(
    process.env.VOICE_CONCIERGE_SYNTHESIZE_TIMEOUT_MS ?? "",
    10,
  );
  return Number.isFinite(configured) && configured > 0
    ? configured
    : DEFAULT_BACKEND_SYNTHESIZE_TIMEOUT_MS;
}

function getOptionalString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed || undefined;
}

function audioHeaders(response: Response): Headers {
  const headers = new Headers({
    "Cache-Control": "no-store",
    "Content-Type": response.headers.get("Content-Type") ?? "audio/wav",
  });

  const provider = response.headers.get("X-Voice-Provider");
  if (provider) headers.set("X-Voice-Provider", provider);

  const constraints = response.headers.get("X-Voice-Constraints");
  if (constraints) headers.set("X-Voice-Constraints", constraints);

  return headers;
}

function getDeclaredContentLength(response: Response): number | undefined {
  const raw = response.headers.get("Content-Length");
  if (!raw) return undefined;

  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

export async function POST(request: Request): Promise<Response> {
  if (!isPrototypeEnabled()) {
    return NextResponse.json(
      { error: "voice_concierge_disabled" },
      { status: 404 },
    );
  }

  if (
    !(await canAccessVoiceConcierge(request, {
      technicalTokenEnv: "VOICE_CONCIERGE_SYNTHESIZE_TOKEN",
    }))
  ) {
    return NextResponse.json(
      { error: "voice_concierge_synthesize_forbidden" },
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

  const body = (await request
    .json()
    .catch(() => null)) as SynthesizeRequestBody | null;
  const text = getOptionalString(body?.text);
  if (!text) {
    return NextResponse.json({ error: "tts_text_required" }, { status: 422 });
  }

  if (text.length > getTtsMaxChars()) {
    return NextResponse.json({ error: "tts_text_too_large" }, { status: 413 });
  }

  const payload: { text: string; voice?: string } = { text };
  const language = getOptionalString(body?.language);
  if (language) payload.voice = language;

  try {
    const response = await fetch(
      `${backendBaseUrl}/api/voice/local-audio/synthesize`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        redirect: "error",
        signal: AbortSignal.timeout(getBackendSynthesizeTimeoutMs()),
        body: JSON.stringify(payload),
      },
    );

    if (!response.ok) {
      return NextResponse.json(
        { error: "backend_synthesize_failed" },
        { status: 502 },
      );
    }

    const maxAudioBytes = getTtsAudioMaxBytes();
    const declaredContentLength = getDeclaredContentLength(response);
    if (
      declaredContentLength !== undefined &&
      declaredContentLength > maxAudioBytes
    ) {
      return NextResponse.json(
        { error: "tts_audio_too_large" },
        { status: 413 },
      );
    }

    const audio = await response.arrayBuffer();
    if (audio.byteLength > maxAudioBytes) {
      return NextResponse.json(
        { error: "tts_audio_too_large" },
        { status: 413 },
      );
    }

    return new Response(audio, {
      status: 200,
      headers: audioHeaders(response),
    });
  } catch {
    return NextResponse.json(
      { error: "backend_synthesize_failed" },
      { status: 502 },
    );
  }
}

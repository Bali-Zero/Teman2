import { NextResponse } from "next/server";
import {
  canAccessVoiceConcierge,
  getVoiceConciergeBackendBaseUrl,
  getVoiceConciergeInternalApiKey,
} from "../auth";

export const runtime = "nodejs";

const BACKEND_STATUS_TIMEOUT_MS = 8_000;
const TTS_PROFILE_HIGH_QUALITY = "high_quality_offline";
const TTS_PROFILE_BROWSER_REALTIME = "browser_realtime";

type ProviderKey = "stt" | "vad" | "tts";
type TtsProfileId =
  | typeof TTS_PROFILE_HIGH_QUALITY
  | typeof TTS_PROFILE_BROWSER_REALTIME;

interface ProviderPolicy {
  requires_network: boolean;
  allows_cloud_fallback: boolean;
  pii_boundary: "local_only" | string;
}

interface LocalAudioProviderStatus {
  name: string;
  available: boolean;
  detail: string;
  policy: ProviderPolicy;
}

interface TtsProfileEntry {
  profile: TtsProfileId;
  provider: string;
  quality: "high_quality" | "realtime";
  latency_class: "offline" | "interactive";
  available: boolean;
  detail: string;
  policy: ProviderPolicy;
}

interface TtsProfileStatus {
  active_profile: TtsProfileId;
  active_provider: string;
  quality: "high_quality" | "realtime";
  latency_class: "offline" | "interactive";
  fallback_policy: "fail_closed";
  profiles: Record<TtsProfileId, TtsProfileEntry>;
}

interface BackendLocalAudioStatus {
  enabled: boolean;
  ready: boolean;
  roundtrip_ready: boolean;
  turn_detection_ready: boolean;
  providers: Record<ProviderKey, LocalAudioProviderStatus>;
  tts_profile?: TtsProfileStatus;
  constraints: string[];
}

interface LabLocalAudioStatus extends BackendLocalAudioStatus {
  source: "disabled" | "backend" | "misconfigured" | "unreachable";
  error?: string;
}

interface VoiceConciergeLabStatus {
  browser_speech_provider: "disabled" | "web-speech-local";
  text_concierge_provider: "local-demo" | "google-ai-studio";
  local_audio: LabLocalAudioStatus;
  tts_profile: TtsProfileStatus;
}

const DISABLED_POLICY: ProviderPolicy = {
  requires_network: false,
  allows_cloud_fallback: false,
  pii_boundary: "local_only",
};

const DISABLED_PROVIDERS: Record<ProviderKey, LocalAudioProviderStatus> = {
  stt: {
    name: "whisper.cpp",
    available: false,
    detail: "local audio disabled",
    policy: DISABLED_POLICY,
  },
  vad: {
    name: "silero-vad",
    available: false,
    detail: "local audio disabled",
    policy: DISABLED_POLICY,
  },
  tts: {
    name: "chatterbox-v3",
    available: false,
    detail: "local audio disabled",
    policy: DISABLED_POLICY,
  },
};

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

function getTextConciergeProvider(): "local-demo" | "google-ai-studio" {
  return process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT === "true" &&
    (process.env.GOOGLE_AI_STUDIO_API_KEY || process.env.GEMINI_API_KEY)
    ? "google-ai-studio"
    : "local-demo";
}

function getConfiguredTtsProfile(): TtsProfileId {
  const rawValue = (process.env.VOICE_CONCIERGE_TTS_PROFILE ?? "")
    .trim()
    .toLowerCase()
    .replaceAll(" ", "_")
    .replaceAll("-", "_");
  if (rawValue === "browser_realtime" || rawValue === "realtime") {
    return TTS_PROFILE_BROWSER_REALTIME;
  }
  return TTS_PROFILE_HIGH_QUALITY;
}

function getRealtimeTtsProvider(): string {
  return (
    process.env.VOICE_CONCIERGE_REALTIME_TTS_PROVIDER?.trim() ||
    "browser-web-speech-local"
  );
}

function buildTtsProfileStatus(
  localAudio: Pick<BackendLocalAudioStatus, "providers">,
): TtsProfileStatus {
  const activeProfile = getConfiguredTtsProfile();
  const highQualityProvider = localAudio.providers.tts;
  const profiles: Record<TtsProfileId, TtsProfileEntry> = {
    high_quality_offline: {
      profile: TTS_PROFILE_HIGH_QUALITY,
      provider: highQualityProvider.name,
      quality: "high_quality",
      latency_class: "offline",
      available: highQualityProvider.available,
      detail: highQualityProvider.detail,
      policy: highQualityProvider.policy,
    },
    browser_realtime: {
      profile: TTS_PROFILE_BROWSER_REALTIME,
      provider: getRealtimeTtsProvider(),
      quality: "realtime",
      latency_class: "interactive",
      available: false,
      detail: "client must confirm a browser localService voice",
      policy: DISABLED_POLICY,
    },
  };
  const active = profiles[activeProfile];
  return {
    active_profile: active.profile,
    active_provider: active.provider,
    quality: active.quality,
    latency_class: active.latency_class,
    fallback_policy: "fail_closed",
    profiles,
  };
}

function baseStatus(localAudio: LabLocalAudioStatus): VoiceConciergeLabStatus {
  const ttsProfile =
    localAudio.tts_profile ?? buildTtsProfileStatus(localAudio);
  return {
    browser_speech_provider:
      ttsProfile.active_profile === TTS_PROFILE_BROWSER_REALTIME
        ? "web-speech-local"
        : "disabled",
    text_concierge_provider: getTextConciergeProvider(),
    local_audio: localAudio,
    tts_profile: ttsProfile,
  };
}

function disabledLocalAudioStatus(): LabLocalAudioStatus {
  return {
    enabled: false,
    ready: false,
    roundtrip_ready: false,
    turn_detection_ready: false,
    source: "disabled",
    providers: DISABLED_PROVIDERS,
    constraints: [
      "local_only",
      "no_cloud_audio_fallback",
      "no_raw_audio_persistence",
      "no_pii",
    ],
  };
}

export async function GET(request: Request): Promise<NextResponse> {
  if (!isPrototypeEnabled()) {
    return NextResponse.json(
      { error: "voice_concierge_disabled" },
      { status: 404 },
    );
  }

  if (
    !(await canAccessVoiceConcierge(request, {
      technicalTokenEnv: "VOICE_CONCIERGE_STATUS_TOKEN",
    }))
  ) {
    return NextResponse.json(
      { error: "voice_concierge_status_forbidden" },
      { status: 403 },
    );
  }

  if (!isLocalAudioEnabled()) {
    return NextResponse.json(baseStatus(disabledLocalAudioStatus()));
  }

  const apiKey = getVoiceConciergeInternalApiKey();
  if (!apiKey) {
    return NextResponse.json(
      baseStatus({
        ...disabledLocalAudioStatus(),
        enabled: true,
        source: "misconfigured",
        error: "internal_api_key_missing",
      }),
      { status: 503 },
    );
  }

  const backendBaseUrl = getVoiceConciergeBackendBaseUrl();
  if (!backendBaseUrl) {
    return NextResponse.json(
      baseStatus({
        ...disabledLocalAudioStatus(),
        enabled: true,
        source: "misconfigured",
        error: "backend_url_missing",
      }),
      { status: 503 },
    );
  }

  try {
    const response = await fetch(
      `${backendBaseUrl}/api/voice/local-audio/status`,
      {
        method: "GET",
        headers: { "X-API-Key": apiKey },
        signal: AbortSignal.timeout(BACKEND_STATUS_TIMEOUT_MS),
      },
    );

    if (!response.ok) {
      return NextResponse.json(
        baseStatus({
          ...disabledLocalAudioStatus(),
          enabled: true,
          source: "unreachable",
          error: "backend_status_failed",
        }),
        { status: 502 },
      );
    }

    const localAudio = (await response.json()) as BackendLocalAudioStatus;
    return NextResponse.json(
      baseStatus({
        ...localAudio,
        source: "backend",
      }),
    );
  } catch {
    return NextResponse.json(
      baseStatus({
        ...disabledLocalAudioStatus(),
        enabled: true,
        source: "unreachable",
        error: "backend_status_unreachable",
      }),
      { status: 502 },
    );
  }
}

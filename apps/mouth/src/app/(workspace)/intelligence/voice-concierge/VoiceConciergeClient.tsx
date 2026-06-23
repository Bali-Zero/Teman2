"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  Bot,
  Loader2,
  Mic,
  Send,
  ShieldCheck,
  Volume2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

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

interface ConciergeMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ConciergeResponse {
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

interface ConciergeErrorResponse {
  error?: string;
  safety_note?: string;
}

interface LocalAudioTranscribeResponse {
  text?: string;
  language?: string | null;
  duration_seconds?: number | null;
  provider?: string;
  constraints?: string[];
  error?: string;
}

interface LocalAudioProviderStatus {
  name: string;
  available: boolean;
  detail: string;
  policy: {
    requires_network: boolean;
    allows_cloud_fallback: boolean;
    pii_boundary: string;
  };
}

interface VoiceConciergeLabStatus {
  browser_speech_provider: "disabled";
  text_concierge_provider: "local-demo" | "google-ai-studio";
  local_audio: {
    enabled: boolean;
    ready: boolean;
    roundtrip_ready: boolean;
    turn_detection_ready: boolean;
    source: "disabled" | "backend" | "misconfigured" | "unreachable";
    providers: {
      stt: LocalAudioProviderStatus;
      vad: LocalAudioProviderStatus;
      tts: LocalAudioProviderStatus;
    };
    constraints: string[];
    error?: string;
  };
}

function getStatusLabel(response: ConciergeResponse | null): string {
  if (!response) return "Ready";
  return response.mode === "gemini" ? "Gemini" : "Demo";
}

function getAudioStackLabel(status: VoiceConciergeLabStatus | null): string {
  if (!status) return "Checking audio";
  if (status.local_audio.ready) return "Local audio ready";
  if (status.local_audio.roundtrip_ready) return "Local audio roundtrip ready";
  if (status.local_audio.enabled) return "Local audio gated";
  return "Audio gated";
}

function isConciergeResponse(
  payload: ConciergeResponse | ConciergeErrorResponse,
): payload is ConciergeResponse {
  return "answer" in payload;
}

function getSpeechText(response: ConciergeResponse): string {
  return (response.spoken_answer?.trim() || response.answer).trim();
}

function canUseBrowserRecorder(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof MediaRecorder !== "undefined"
  );
}

function getRecorderMimeType(): string | undefined {
  if (
    typeof MediaRecorder === "undefined" ||
    typeof MediaRecorder.isTypeSupported !== "function"
  ) {
    return undefined;
  }

  return [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ].find((mimeType) => MediaRecorder.isTypeSupported(mimeType));
}

function getAudioFileExtension(contentType: string): string {
  const mediaType = contentType.split(";")[0]?.trim().toLowerCase();
  if (mediaType === "audio/mp4") return "mp4";
  if (mediaType === "audio/ogg") return "ogg";
  if (mediaType === "audio/wav" || mediaType === "audio/x-wav") return "wav";
  return "webm";
}

function stopMediaStream(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop());
}

function inferLocaleFromText(text: string): SupportedLocale {
  const normalized = text.toLowerCase();
  if (/[а-яё]/i.test(text)) return "ru";
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

export function VoiceConciergeClient(): React.JSX.Element {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ConciergeMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<ConciergeResponse | null>(
    null,
  );
  const [labStatus, setLabStatus] = useState<VoiceConciergeLabStatus | null>(
    null,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isStartingRecording, setIsStartingRecording] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isStoppingRecording, setIsStoppingRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(false);
  const isStartingRecordingRef = useRef(false);
  const stopPendingRef = useRef(false);
  const recordingSessionRef = useRef(0);
  const speechSessionRef = useRef(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const speechAudioRef = useRef<HTMLAudioElement | null>(null);
  const speechObjectUrlRef = useRef<string | null>(null);
  const isManualAudioReady = Boolean(labStatus?.local_audio.roundtrip_ready);
  const hasBrowserRecorder = canUseBrowserRecorder();

  const stopSpeechPlayback = useCallback(
    (options: { invalidate?: boolean; updateState?: boolean } = {}) => {
      if (options.invalidate !== false) {
        speechSessionRef.current += 1;
      }

      const audio = speechAudioRef.current;
      speechAudioRef.current = null;
      if (audio) {
        audio.onended = null;
        audio.onerror = null;
        audio.pause();
      }

      const objectUrl = speechObjectUrlRef.current;
      speechObjectUrlRef.current = null;
      if (
        objectUrl &&
        typeof URL !== "undefined" &&
        typeof URL.revokeObjectURL === "function"
      ) {
        URL.revokeObjectURL(objectUrl);
      }

      if (options.updateState !== false && isMountedRef.current) {
        setIsSpeaking(false);
      }
    },
    [],
  );

  const playLocalSpeech = useCallback(
    async (text: string, options: { reportError?: boolean } = {}) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      if (!isManualAudioReady) {
        if (options.reportError) {
          setError("Local TTS is not ready");
        }
        return;
      }

      if (
        typeof Audio === "undefined" ||
        typeof URL === "undefined" ||
        typeof URL.createObjectURL !== "function"
      ) {
        if (options.reportError) {
          setError("Local audio playback is not available");
        }
        return;
      }

      let sessionId: number | undefined;
      try {
        sessionId = speechSessionRef.current + 1;
        speechSessionRef.current = sessionId;
        stopSpeechPlayback({ invalidate: false });
        setIsSpeaking(true);
        const response = await fetch("/api/lab/voice-concierge/synthesize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: trimmed,
            language: inferLocaleFromText(trimmed),
          }),
        });

        if (!response.ok) {
          throw new Error("Local speech synthesis failed");
        }

        const audioBlob = await response.blob();
        if (!audioBlob.size) {
          throw new Error("Local speech synthesis returned empty audio");
        }

        if (!isMountedRef.current || speechSessionRef.current !== sessionId) {
          return;
        }

        const objectUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(objectUrl);
        speechObjectUrlRef.current = objectUrl;
        speechAudioRef.current = audio;
        audio.onended = () => {
          if (
            speechSessionRef.current === sessionId &&
            speechAudioRef.current === audio
          ) {
            stopSpeechPlayback({ invalidate: false });
          }
        };
        audio.onerror = () => {
          if (
            speechSessionRef.current === sessionId &&
            speechAudioRef.current === audio
          ) {
            stopSpeechPlayback();
            if (options.reportError && isMountedRef.current) {
              setError("Local speech synthesis failed");
            }
          }
        };
        await audio.play();
      } catch {
        const isCurrentSpeech =
          sessionId !== undefined && speechSessionRef.current === sessionId;
        if (isCurrentSpeech) {
          stopSpeechPlayback();
          if (options.reportError && isMountedRef.current) {
            setError("Local speech synthesis failed");
          }
        }
      }
    },
    [isManualAudioReady, stopSpeechPlayback],
  );

  const stopAudioStream = useCallback(() => {
    stopMediaStream(streamRef.current);
    streamRef.current = null;
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    let cancelled = false;

    async function loadLabStatus(): Promise<void> {
      try {
        const response = await fetch("/api/lab/voice-concierge/status");
        const payload = (await response.json()) as
          | VoiceConciergeLabStatus
          | ConciergeErrorResponse;
        if (!cancelled && "local_audio" in payload) {
          setLabStatus(payload);
        }
      } catch {
        if (!cancelled) {
          setLabStatus(null);
        }
      }
    }

    void loadLabStatus();

    return () => {
      isMountedRef.current = false;
      cancelled = true;
      recordingSessionRef.current += 1;
      isStartingRecordingRef.current = false;
      stopPendingRef.current = true;

      const recorder = recorderRef.current;
      recorderRef.current = null;
      if (recorder && recorder.state !== "inactive") {
        recorder.ondataavailable = null;
        recorder.onstop = null;
        recorder.stop();
      }
      stopAudioStream();
      stopSpeechPlayback({ updateState: false });
    };
  }, [stopAudioStream, stopSpeechPlayback]);

  const providerRows = [
    { label: "STT", provider: labStatus?.local_audio.providers.stt },
    { label: "VAD", provider: labStatus?.local_audio.providers.vad },
    { label: "TTS", provider: labStatus?.local_audio.providers.tts },
  ];

  const submitTurn = useCallback(
    async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || isSubmitting) return;

      const userMessage: ConciergeMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
      };
      const nextMessages = [...messages, userMessage].slice(-6);
      setMessages(nextMessages);
      setInput("");
      setError(null);
      setIsSubmitting(true);

      try {
        const response = await fetch("/api/lab/voice-concierge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: trimmed,
            locale: inferLocaleFromText(trimmed),
            history: messages.slice(-4).map((turn) => ({
              role: turn.role,
              content: turn.content,
            })),
          }),
        });

        const payload = (await response.json()) as
          | ConciergeResponse
          | ConciergeErrorResponse;

        if (!response.ok || !isConciergeResponse(payload)) {
          const errorPayload = payload as ConciergeErrorResponse;
          const nextError =
            errorPayload.safety_note ??
            errorPayload.error ??
            "Voice concierge request failed";
          setError(nextError);
          return;
        }

        const assistantMessage: ConciergeMessage = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: payload.answer,
        };
        setLastResponse(payload);
        setMessages([...nextMessages, assistantMessage].slice(-6));
        void playLocalSpeech(getSpeechText(payload));
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Voice concierge request failed",
        );
      } finally {
        setIsSubmitting(false);
      }
    },
    [isSubmitting, messages, playLocalSpeech],
  );

  const transcribeAudio = useCallback(
    async (audioBlob: Blob) => {
      if (!audioBlob.size) return;

      setIsTranscribing(true);
      setError(null);

      try {
        const form = new FormData();
        const contentType = audioBlob.type || "audio/webm";
        form.append(
          "file",
          audioBlob,
          `voice-concierge.${getAudioFileExtension(contentType)}`,
        );

        const response = await fetch("/api/lab/voice-concierge/transcribe", {
          method: "POST",
          body: form,
        });
        const payload = (await response.json()) as LocalAudioTranscribeResponse;
        const transcript = payload.text?.trim();

        if (!response.ok || !transcript) {
          setError(payload.error ?? "Local transcription failed");
          return;
        }

        setInput(transcript);
        await submitTurn(transcript);
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Local transcription failed",
        );
      } finally {
        setIsTranscribing(false);
      }
    },
    [submitTurn],
  );

  const handleVoiceInput = useCallback(async () => {
    if (isRecording || recorderRef.current) {
      const recorder = recorderRef.current;
      if (
        !recorder ||
        recorder.state === "inactive" ||
        stopPendingRef.current
      ) {
        return;
      }
      stopPendingRef.current = true;
      setIsStoppingRecording(true);
      recorder.stop();
      return;
    }

    if (
      isStartingRecordingRef.current ||
      !isManualAudioReady ||
      !hasBrowserRecorder ||
      isSubmitting ||
      isTranscribing
    ) {
      return;
    }

    const sessionId = recordingSessionRef.current + 1;
    recordingSessionRef.current = sessionId;
    isStartingRecordingRef.current = true;
    stopPendingRef.current = false;
    setIsStartingRecording(true);

    let capturedStream: MediaStream | null = null;
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      capturedStream = stream;

      if (!isMountedRef.current || recordingSessionRef.current !== sessionId) {
        stopMediaStream(stream);
        return;
      }

      streamRef.current = stream;
      const chunks: Blob[] = [];

      const mimeType = getRecorderMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };
      recorder.onstop = () => {
        const contentType = recorder.mimeType || mimeType || "audio/webm";
        const audioBlob = new Blob(chunks, { type: contentType });
        const isCurrentSession = recordingSessionRef.current === sessionId;

        if (recorderRef.current === recorder) {
          recorderRef.current = null;
        }
        if (streamRef.current === stream) {
          streamRef.current = null;
        }
        stopMediaStream(stream);
        stopPendingRef.current = false;

        if (isMountedRef.current && isCurrentSession) {
          setIsRecording(false);
          setIsStoppingRecording(false);
          void transcribeAudio(audioBlob);
        }
      };

      recorder.start();
      isStartingRecordingRef.current = false;
      if (isMountedRef.current && recordingSessionRef.current === sessionId) {
        setIsStartingRecording(false);
        setIsRecording(true);
      }
    } catch (captureError) {
      stopMediaStream(capturedStream);
      if (streamRef.current === capturedStream) {
        streamRef.current = null;
      }
      recorderRef.current = null;
      isStartingRecordingRef.current = false;
      stopPendingRef.current = false;
      if (isMountedRef.current && recordingSessionRef.current === sessionId) {
        setIsStartingRecording(false);
        setIsStoppingRecording(false);
        setIsRecording(false);
        setError(
          captureError instanceof Error
            ? captureError.message
            : "Microphone capture failed",
        );
      }
    }
  }, [
    hasBrowserRecorder,
    isRecording,
    isSubmitting,
    isTranscribing,
    isManualAudioReady,
    transcribeAudio,
  ]);

  const voiceButtonLabel = isRecording
    ? "Stop voice input"
    : isStartingRecording
      ? "Starting voice input"
      : isManualAudioReady && hasBrowserRecorder
        ? "Start voice input"
        : "Voice input gated until local audio roundtrip is wired";
  const voiceButtonText = isRecording
    ? isStoppingRecording
      ? "Stopping"
      : "Stop voice"
    : isStartingRecording
      ? "Starting"
      : isTranscribing
        ? "Transcribing"
        : isManualAudioReady && hasBrowserRecorder
          ? "Voice"
          : "Voice gated";
  const voiceButtonDisabled =
    isStartingRecording ||
    isStoppingRecording ||
    (!isRecording &&
      (!isManualAudioReady ||
        !hasBrowserRecorder ||
        isSubmitting ||
        isTranscribing));
  const textSubmitDisabled =
    !input.trim() ||
    isSubmitting ||
    isStartingRecording ||
    isRecording ||
    isStoppingRecording ||
    isTranscribing;
  const voiceButtonTitle =
    isManualAudioReady && hasBrowserRecorder
      ? "Record a short local-only voice prompt."
      : "Voice capture is gated until local Whisper/Chatterbox roundtrip is wired.";

  return (
    <main className="min-h-full px-4 py-6 md:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-5">
        <section className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <div
              className="mb-3 inline-flex items-center gap-2 rounded-md border px-3 py-1 text-xs"
              style={{
                borderColor: "rgba(255,255,255,0.08)",
                color: "var(--bz-text-2)",
                background: "rgba(255,255,255,0.03)",
              }}
            >
              <ShieldCheck size={14} />
              Non-PII prototype
            </div>
            <h1
              className="text-3xl font-semibold tracking-normal md:text-4xl"
              style={{ color: "var(--bz-text-1)" }}
            >
              Voice Concierge
            </h1>
          </div>

          <div
            className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
            style={{
              borderColor: "rgba(255,255,255,0.08)",
              color: "var(--bz-text-2)",
              background: "rgba(255,255,255,0.03)",
            }}
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{
                background:
                  lastResponse?.mode === "gemini"
                    ? "var(--bz-green)"
                    : "var(--bz-accent)",
              }}
            />
            {getStatusLabel(lastResponse)}
            <span style={{ color: "var(--bz-text-3)" }}>
              {getAudioStackLabel(labStatus)}
            </span>
            {lastResponse?.model ? (
              <span style={{ color: "var(--bz-text-3)" }}>
                {lastResponse.model}
              </span>
            ) : null}
          </div>
        </section>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_360px]">
          <Card
            className="overflow-hidden"
            style={{
              borderColor: "rgba(255,255,255,0.08)",
              background: "rgba(10,12,16,0.86)",
            }}
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Bot size={18} />
                Session
              </CardTitle>
              <CardDescription>Public Bali Zero triage only.</CardDescription>
            </CardHeader>
            <CardContent className="flex min-h-[520px] flex-col gap-4">
              <div
                className="flex min-h-[300px] flex-1 flex-col gap-3 overflow-y-auto rounded-md border p-3"
                style={{
                  borderColor: "rgba(255,255,255,0.08)",
                  background: "rgba(255,255,255,0.02)",
                }}
              >
                {messages.length === 0 ? (
                  <div
                    className="flex h-full min-h-[260px] items-center justify-center text-center text-sm"
                    style={{ color: "var(--bz-text-3)" }}
                  >
                    Ask about visa, PT PMA, tax, property, or operations.
                  </div>
                ) : (
                  messages.map((message) => (
                    <div
                      key={message.id}
                      className={`max-w-[86%] rounded-md px-3 py-2 text-sm leading-relaxed ${
                        message.role === "user" ? "self-end" : "self-start"
                      }`}
                      style={{
                        background:
                          message.role === "user"
                            ? "rgba(212,132,90,0.18)"
                            : "rgba(255,255,255,0.06)",
                        color: "var(--bz-text-1)",
                      }}
                    >
                      {message.content}
                    </div>
                  ))
                )}
              </div>

              {error ? (
                <div
                  className="rounded-md border px-3 py-2 text-sm"
                  style={{
                    borderColor: "rgba(239,68,68,0.28)",
                    color: "#fca5a5",
                    background: "rgba(239,68,68,0.08)",
                  }}
                >
                  {error}
                </div>
              ) : null}

              <div className="flex flex-col gap-3">
                <Textarea
                  aria-label="Concierge prompt"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Can I open a cafe in Bali?"
                  className="min-h-[88px] resize-none"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    aria-label={voiceButtonLabel}
                    disabled={voiceButtonDisabled}
                    onClick={() => void handleVoiceInput()}
                    title={voiceButtonTitle}
                    variant="outline"
                  >
                    {isTranscribing ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Mic />
                    )}
                    {voiceButtonText}
                  </Button>
                  <Button
                    aria-label="Read latest answer"
                    disabled={
                      !lastResponse?.answer || !isManualAudioReady || isSpeaking
                    }
                    onClick={() =>
                      lastResponse &&
                      void playLocalSpeech(getSpeechText(lastResponse), {
                        reportError: true,
                      })
                    }
                    title={
                      isManualAudioReady
                        ? "Read the latest short voice response with local TTS."
                        : "Local TTS is gated until local audio roundtrip is ready."
                    }
                    variant="outline"
                  >
                    {isSpeaking ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Volume2 />
                    )}
                    {isSpeaking ? "Speaking" : "Read"}
                  </Button>
                  <Button
                    disabled={textSubmitDisabled}
                    onClick={() => void submitTurn(input)}
                  >
                    {isSubmitting ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Send />
                    )}
                    Send
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <aside className="flex flex-col gap-5">
            <Card
              style={{
                borderColor: "rgba(255,255,255,0.08)",
                background: "rgba(10,12,16,0.76)",
              }}
            >
              <CardHeader>
                <CardTitle className="text-lg">Routing</CardTitle>
                <CardDescription>Latest structured state.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <dl className="grid grid-cols-[120px_1fr] gap-2">
                  <dt style={{ color: "var(--bz-text-3)" }}>Intent</dt>
                  <dd style={{ color: "var(--bz-text-1)" }}>
                    {lastResponse?.intent ?? "unknown"}
                  </dd>
                  <dt style={{ color: "var(--bz-text-3)" }}>Risk</dt>
                  <dd style={{ color: "var(--bz-text-1)" }}>
                    {lastResponse?.risk_level ?? "low"}
                  </dd>
                  <dt style={{ color: "var(--bz-text-3)" }}>Next action</dt>
                  <dd style={{ color: "var(--bz-text-1)" }}>
                    {lastResponse?.next_action ?? "answer_only"}
                  </dd>
                </dl>
              </CardContent>
            </Card>

            <Card
              style={{
                borderColor: "rgba(255,255,255,0.08)",
                background: "rgba(10,12,16,0.76)",
              }}
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Activity size={18} />
                  Audio stack
                </CardTitle>
                <CardDescription>
                  {getAudioStackLabel(labStatus)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {providerRows.map(({ label, provider }) => (
                  <div
                    key={label}
                    className="grid grid-cols-[44px_1fr_auto] items-center gap-2 rounded-md border px-3 py-2"
                    style={{
                      borderColor: "rgba(255,255,255,0.08)",
                      background: "rgba(255,255,255,0.03)",
                    }}
                  >
                    <span style={{ color: "var(--bz-text-3)" }}>{label}</span>
                    <span
                      className="truncate"
                      title={provider?.detail ?? "checking"}
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      {provider?.name ?? "checking"}
                    </span>
                    <span
                      className="rounded-md px-2 py-1 text-xs"
                      style={{
                        color: provider?.available ? "#86efac" : "#fca5a5",
                        background: provider?.available
                          ? "rgba(34,197,94,0.12)"
                          : "rgba(239,68,68,0.10)",
                      }}
                    >
                      {provider?.available ? "ready" : "gated"}
                    </span>
                  </div>
                ))}
                <div
                  className="rounded-md border px-3 py-2"
                  style={{
                    borderColor: "rgba(255,255,255,0.08)",
                    color: "var(--bz-text-2)",
                    background: "rgba(255,255,255,0.03)",
                  }}
                >
                  Text:{" "}
                  {labStatus?.text_concierge_provider === "google-ai-studio"
                    ? "Google AI Studio"
                    : "Demo"}
                </div>
              </CardContent>
            </Card>

            <Card
              style={{
                borderColor: "rgba(255,255,255,0.08)",
                background: "rgba(10,12,16,0.76)",
              }}
            >
              <CardHeader>
                <CardTitle className="text-lg">Replies</CardTitle>
                <CardDescription>Safe follow-up prompts.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {(
                  lastResponse?.quick_replies ?? [
                    "Visa triage",
                    "PT PMA setup",
                    "Property check",
                  ]
                ).map((reply) => (
                  <Button
                    key={reply}
                    className="justify-start whitespace-normal text-left"
                    onClick={() => setInput(reply)}
                    variant="outline"
                  >
                    {reply}
                  </Button>
                ))}
              </CardContent>
            </Card>

            <Card
              style={{
                borderColor: "rgba(255,255,255,0.08)",
                background: "rgba(10,12,16,0.76)",
              }}
            >
              <CardHeader>
                <CardTitle className="text-lg">Boundary</CardTitle>
              </CardHeader>
              <CardContent
                className="text-sm leading-relaxed"
                style={{ color: "var(--bz-text-2)" }}
              >
                {lastResponse?.safety_note ??
                  "No passports, KTP, NPWP, phone numbers, emails, names, document IDs, CRM notes, or WhatsApp details."}
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
    </main>
  );
}

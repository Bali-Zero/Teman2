"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  Loader2,
  Mic,
  MicOff,
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

type RecognitionResult = {
  isFinal?: boolean;
  0?: { transcript?: string };
};

type RecognitionEvent = Event & {
  results: {
    length: number;
    [index: number]: RecognitionResult;
  };
};

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: RecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type SpeechWindow = Window &
  typeof globalThis & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const speechWindow = window as SpeechWindow;
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

function getStatusLabel(response: ConciergeResponse | null): string {
  if (!response) return "Ready";
  return response.mode === "gemini" ? "Gemini" : "Demo";
}

function isConciergeResponse(
  payload: ConciergeResponse | ConciergeErrorResponse,
): payload is ConciergeResponse {
  return "answer" in payload;
}

export function VoiceConciergeClient(): React.JSX.Element {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ConciergeMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<ConciergeResponse | null>(
    null,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [canListen, setCanListen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const speak = useCallback((text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.96;
    window.speechSynthesis.speak(utterance);
  }, []);

  useEffect(() => {
    setCanListen(getSpeechRecognition() !== null);
    return () => {
      recognitionRef.current?.stop();
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

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
            locale: "en",
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
        speak(payload.answer);
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
    [isSubmitting, messages, speak],
  );

  const toggleListening = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const Recognition = getSpeechRecognition();
    if (!Recognition) {
      setError("Speech recognition is not available in this browser.");
      return;
    }

    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event: RecognitionEvent) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index]?.[0]?.transcript ?? "";
      }
      setInput(transcript.trim());
    };
    recognition.onerror = () => {
      setError("Voice capture stopped.");
      setIsListening(false);
    };
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    setError(null);
    setIsListening(true);
    recognition.start();
  }, [isListening]);

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
              <CardDescription>
                Public Bali Zero triage only.
              </CardDescription>
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
                    aria-label={isListening ? "Stop voice input" : "Start voice input"}
                    disabled={!canListen}
                    onClick={toggleListening}
                    variant={isListening ? "secondary" : "outline"}
                  >
                    {isListening ? <MicOff /> : <Mic />}
                    Voice
                  </Button>
                  <Button
                    aria-label="Read latest answer"
                    disabled={!lastResponse?.answer}
                    onClick={() => lastResponse && speak(lastResponse.answer)}
                    variant="outline"
                  >
                    <Volume2 />
                    Read
                  </Button>
                  <Button
                    disabled={!input.trim() || isSubmitting}
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
                <CardTitle className="text-lg">Replies</CardTitle>
                <CardDescription>Safe follow-up prompts.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {(lastResponse?.quick_replies ?? [
                  "Visa triage",
                  "PT PMA setup",
                  "Property check",
                ]).map((reply) => (
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

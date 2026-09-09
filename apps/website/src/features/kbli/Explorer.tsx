"use client";
import { useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import type { ExplorerReply } from "./types";
import styles from "./kbli.module.css";

export function Explorer({
  available,
  initialCode,
}: {
  available: boolean;
  initialCode?: string;
}) {
  const [query, setQuery] = useState(
    initialCode
      ? `Explain the activity scope and recorded requirements for KBLI ${initialCode}.`
      : "",
  );
  const [turns, setTurns] = useState<
    { question: string; reply: ExplorerReply }[]
  >([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const starters = [
    "How do I find a code for my business activity?",
    "What should I compare before choosing a KBLI code?",
    "How do scope and scale affect licensing?",
  ];
  async function submit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!available || pending || !query.trim()) return;
    const question = query.trim();
    const abort = new AbortController();
    controller.current = abort;
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/kbli/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: question }),
        signal: abort.signal,
      });
      const data = (await response.json()) as ExplorerReply & {
        error?: string;
      };
      if (!response.ok)
        throw new Error(data.error || "The answer could not be retrieved.");
      setTurns((previous) => [
        ...previous.slice(-7),
        { question, reply: data },
      ]);
      setQuery("");
    } catch (failure) {
      if (!abort.signal.aborted)
        setError(
          failure instanceof Error
            ? failure.message
            : "The answer is unavailable.",
        );
    } finally {
      setPending(false);
    }
  }
  function clear(): void {
    controller.current?.abort();
    setTurns([]);
    setError("");
    setQuery("");
    setPending(false);
  }
  return (
    <div className={styles.explorerPanel}>
      {!available && (
        <p className={styles.status}>
          Assisted answers are currently unavailable in this preview. You can
          search the complete activity directory, inspect a code and compare
          your shortlist.
        </p>
      )}
      <form onSubmit={submit} className={styles.chatForm}>
        <label htmlFor="explorer-query">
          Describe the activity or ask about a code
        </label>
        <textarea
          id="explorer-query"
          maxLength={4000}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="For example: which activity should I investigate for a restaurant?"
        />
        <p className={styles.caption}>
          Use business activities and code numbers. Do not include personal
          documents or identifying details. Questions stay in this page’s
          memory; each answer addresses the question you submit.
        </p>
        <div className={styles.actions}>
          <button
            className={styles.primary}
            disabled={!available || pending || !query.trim()}
            type="submit"
          >
            {pending ? "Retrieving an answer…" : "Ask the Explorer →"}
          </button>
          {(turns.length > 0 || pending) && (
            <button className={styles.secondary} type="button" onClick={clear}>
              Clear conversation
            </button>
          )}
        </div>
      </form>
      {error && (
        <p role="alert" className={styles.status}>
          {error}
        </p>
      )}
      <div aria-live="polite" aria-busy={pending}>
        {turns.map((turn, index) => (
          <article className={styles.chatAnswer} key={index}>
            <p className={styles.chatQuestion}>{turn.question}</p>
            <div className={styles.prose}>
              <ReactMarkdown>{turn.reply.answer}</ReactMarkdown>
            </div>
            {turn.reply.detected_kbli.length > 0 && (
              <div className={styles.chips}>
                {turn.reply.detected_kbli.map((code) => (
                  <a
                    className={styles.secondary}
                    key={code}
                    href={`/kbli-explorer?inspect=${code}`}
                  >
                    Inspect {code} →
                  </a>
                ))}
              </div>
            )}
            {turn.reply.sources.length > 0 && (
              <details className={styles.chatSources}>
                <summary>
                  Read {turn.reply.sources.length} retrieved sources
                </summary>
                {turn.reply.sources.map((source, sourceIndex) => (
                  <div key={sourceIndex}>
                    <h4>{source.label}</h4>
                    {source.code && (
                      <a href={`/kbli/${source.code}`}>
                        Activity {source.code} →
                      </a>
                    )}
                    <p>{source.content}</p>
                  </div>
                ))}
              </details>
            )}
            {turn.reply.suggested_queries.length > 0 && (
              <div className={styles.starterList}>
                {turn.reply.suggested_queries.map(
                  (suggestion, suggestionIndex) => (
                    <button
                      key={suggestionIndex}
                      type="button"
                      onClick={() => setQuery(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ),
                )}
              </div>
            )}
          </article>
        ))}
      </div>
      {!turns.length && (
        <div className={styles.chatAnswer}>
          <span className={styles.eyebrow}>A place to start</span>
          <div className={styles.starterList}>
            {starters.map((starter) => (
              <button
                type="button"
                key={starter}
                onClick={() => setQuery(starter)}
              >
                {starter} <span aria-hidden="true">↗</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

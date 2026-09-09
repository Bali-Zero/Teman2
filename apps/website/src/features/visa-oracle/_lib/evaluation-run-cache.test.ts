import { describe, expect, it, vi } from "vitest";
import { EvaluationRunCache } from "./evaluation-run-cache";

describe("evaluation run cache lease ownership", () => {
  it("survives StrictMode cleanup/setup without a second request or aborted result", async () => {
    const cache = new EvaluationRunCache<string>();
    let resolve!: (value: string) => void;
    const run = vi.fn(
      (signal: AbortSignal) =>
        new Promise<string>((accept, reject) => {
          resolve = accept;
          signal.addEventListener("abort", () => reject(new Error("aborted")));
        }),
    );

    const first = cache.acquire("same-request", run);
    first.release();
    const strictReplacement = cache.acquire("same-request", run);
    await Promise.resolve();
    expect(run).toHaveBeenCalledOnce();
    expect(run.mock.calls[0][0].aborted).toBe(false);

    resolve("authoritative-outcome");
    await expect(strictReplacement.promise).resolves.toBe(
      "authoritative-outcome",
    );
    strictReplacement.release();

    const laterConsumer = cache.acquire("same-request", run);
    await expect(laterConsumer.promise).resolves.toBe("authoritative-outcome");
    expect(run).toHaveBeenCalledOnce();
  });

  it("aborts an orphaned in-flight request and lets a later consumer start cleanly", async () => {
    vi.useFakeTimers();
    const cache = new EvaluationRunCache<string>();
    const signals: AbortSignal[] = [];
    const run = (signal: AbortSignal) => {
      signals.push(signal);
      return new Promise<string>((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(new Error("aborted")));
      });
    };
    const orphan = cache.acquire("request", run);
    const orphanedResult = expect(orphan.promise).rejects.toThrow("aborted");
    orphan.release();
    await vi.advanceTimersByTimeAsync(25);
    expect(signals[0].aborted).toBe(true);
    await orphanedResult;

    const replacement = cache.acquire("request", run);
    expect(signals).toHaveLength(2);
    replacement.release();
    vi.useRealTimers();
  });
});

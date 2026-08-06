export interface EvaluationRunLease<T> {
  promise: Promise<T>;
  release: () => void;
}

interface EvaluationRunEntry<T> {
  controller: AbortController;
  promise: Promise<T>;
  consumers: number;
  settled: boolean;
  abortTimer?: ReturnType<typeof setTimeout>;
}

/**
 * Component-local request dedupe with lease ownership. An effect cleanup does
 * not immediately abort a request: a same-tick StrictMode replacement may
 * acquire the lease first. Once no consumer remains, the request is aborted
 * and removed. Successful outcomes stay cached until explicit invalidation.
 */
export class EvaluationRunCache<T> {
  private readonly entries = new Map<string, EvaluationRunEntry<T>>();

  acquire(
    key: string,
    run: (signal: AbortSignal) => Promise<T>,
  ): EvaluationRunLease<T> {
    let entry = this.entries.get(key);
    if (entry?.controller.signal.aborted) {
      this.entries.delete(key);
      entry = undefined;
    }
    if (entry?.abortTimer) {
      clearTimeout(entry.abortTimer);
      entry.abortTimer = undefined;
    }
    if (!entry) {
      const controller = new AbortController();
      entry = {
        controller,
        consumers: 0,
        settled: false,
        promise: Promise.resolve(undefined as T),
      };
      const created = entry;
      created.promise = run(controller.signal)
        .then((value) => {
          created.settled = true;
          return value;
        })
        .catch((error: unknown) => {
          created.settled = true;
          if (this.entries.get(key) === created) this.entries.delete(key);
          throw error;
        });
      this.entries.set(key, created);
      entry = created;
    }

    entry.consumers += 1;
    let released = false;
    return {
      promise: entry.promise,
      release: () => {
        if (released) return;
        released = true;
        entry!.consumers -= 1;
        entry!.abortTimer = setTimeout(() => {
          if (
            entry!.consumers === 0 &&
            !entry!.settled &&
            this.entries.get(key) === entry
          ) {
            this.entries.delete(key);
            entry!.controller.abort();
          }
        }, 25);
      },
    };
  }

  invalidate(key: string): void {
    const entry = this.entries.get(key);
    this.entries.delete(key);
    if (entry?.abortTimer) clearTimeout(entry.abortTimer);
    if (entry && !entry.settled) entry.controller.abort();
  }

  clear(): void {
    for (const entry of this.entries.values()) {
      if (entry.abortTimer) clearTimeout(entry.abortTimer);
      if (!entry.settled) entry.controller.abort();
    }
    this.entries.clear();
  }
}

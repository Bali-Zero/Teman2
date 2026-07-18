import { AsyncLocalStorage } from "node:async_hooks";

import type { D1DatabaseLike } from "./publication-repository";

export type MagazineRuntimeBindings = Readonly<{
  ACTOR_KEY_SECRET?: string;
  ROLE_ALLOWLIST_JSON?: string;
  DB?: D1DatabaseLike;
}>;

const storageKey = Symbol.for("bali-zero-magazine.runtime-bindings");
const registry = globalThis as typeof globalThis & {
  [key: symbol]: AsyncLocalStorage<MagazineRuntimeBindings> | undefined;
};
const storage =
  registry[storageKey] ??
  (registry[storageKey] = new AsyncLocalStorage<MagazineRuntimeBindings>());

export function runWithMagazineBindings<T>(
  bindings: MagazineRuntimeBindings,
  operation: () => T,
): T {
  return storage.run(bindings, operation);
}

export function getMagazineBindings(): MagazineRuntimeBindings {
  return storage.getStore() ?? {};
}

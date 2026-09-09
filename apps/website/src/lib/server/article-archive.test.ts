import { afterEach, describe, expect, it, vi } from "vitest";

const archiveState = vi.hoisted(() => ({ folderMtimeOffset: 0 }));
const archiveSpies = vi.hoisted(() => ({
  readFile: vi.fn(),
  stat: vi.fn(),
}));

vi.mock("node:fs/promises", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:fs/promises")>();
  archiveSpies.readFile.mockImplementation(actual.readFile);
  archiveSpies.stat.mockImplementation(async (target) => {
    const value = await actual.stat(target);
    if (!String(target).endsWith("/immigration")) return value;
    return new Proxy(value, {
      get(target, property, receiver) {
        if (property === "mtimeMs") {
          return target.mtimeMs + archiveState.folderMtimeOffset;
        }
        return Reflect.get(target, property, receiver);
      },
    });
  });
  return {
    ...actual,
    readFile: archiveSpies.readFile,
    stat: archiveSpies.stat,
  };
});

import {
  listAuthoredEnglishArticles,
  resetArticleArchiveMemo,
} from "./article-archive";

afterEach(() => {
  archiveState.folderMtimeOffset = 0;
  archiveSpies.readFile.mockClear();
  archiveSpies.stat.mockClear();
  resetArticleArchiveMemo();
});

describe("authored archive memo", () => {
  it("reuses parsed articles for five minutes and invalidates on folder mtime", async () => {
    const first = await listAuthoredEnglishArticles();
    const firstReadCount = archiveSpies.readFile.mock.calls.length;
    expect(first.length).toBeGreaterThanOrEqual(808);
    expect(firstReadCount).toBeGreaterThanOrEqual(808);

    const second = await listAuthoredEnglishArticles();
    expect(second).toBe(first);
    expect(archiveSpies.readFile).toHaveBeenCalledTimes(firstReadCount);

    archiveState.folderMtimeOffset = 1;
    const third = await listAuthoredEnglishArticles();
    expect(third).not.toBe(first);
    expect(archiveSpies.readFile.mock.calls.length).toBeGreaterThan(
      firstReadCount,
    );
  });
});

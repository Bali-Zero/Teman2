import { describe, it, expect } from "vitest";
import {
  activeMatters,
  resolveUploadPractice,
  uploadNeedsPractice,
} from "./uploadPractice";

const m = (id: number, status: string) => ({ id, status });

describe("uploadPractice", () => {
  it("drops completed and cancelled, keeps everything else", () => {
    const all = [
      m(1, "completed"),
      m(2, "Cancelled"),
      m(3, "on_process"),
      m(4, "approved"),
      m(5, "waiting_documents"),
    ];
    expect(activeMatters(all).map((x) => x.id)).toEqual([3, 4, 5]);
  });

  it("preselects only the single active practice", () => {
    expect(resolveUploadPractice([m(7, "inquiry")], undefined)).toBe("7");
    expect(resolveUploadPractice([], undefined)).toBeNull();
    expect(
      resolveUploadPractice([m(1, "inquiry"), m(2, "inquiry")], undefined),
    ).toBeNull();
  });

  it("a client choice, including 'no practice', beats the default", () => {
    expect(resolveUploadPractice([m(7, "inquiry")], null)).toBeNull();
    expect(resolveUploadPractice([m(7, "inquiry")], "9")).toBe("9");
  });

  it("blocks upload only for 2+ active practices with none chosen", () => {
    const two = [m(1, "inquiry"), m(2, "inquiry")];
    expect(uploadNeedsPractice(two, null)).toBe(true);
    expect(uploadNeedsPractice(two, "1")).toBe(false);
    expect(uploadNeedsPractice([m(1, "inquiry")], null)).toBe(false);
    expect(uploadNeedsPractice([], null)).toBe(false);
  });
});

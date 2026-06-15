import { describe, it, expect, beforeEach } from "vitest";
import {
  loadViewMode,
  saveViewMode,
  CLIENTS_VIEW_MODE_KEY,
  PROCESS_VIEW_MODE_KEY,
} from "./view-mode-storage";

const MODES = ["list", "kanban", "table", "map"] as const;

describe("view-mode persistence (P2.2)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns the fallback when nothing is stored", () => {
    expect(loadViewMode(CLIENTS_VIEW_MODE_KEY, MODES, "list")).toBe("list");
  });

  it("round-trips a saved mode", () => {
    saveViewMode(CLIENTS_VIEW_MODE_KEY, "table");
    expect(loadViewMode(CLIENTS_VIEW_MODE_KEY, MODES, "list")).toBe("table");
  });

  it("ignores junk values and returns the fallback", () => {
    localStorage.setItem(CLIENTS_VIEW_MODE_KEY, "garbage");
    expect(loadViewMode(CLIENTS_VIEW_MODE_KEY, MODES, "list")).toBe("list");
  });

  it("keeps pages isolated under their own keys", () => {
    saveViewMode(CLIENTS_VIEW_MODE_KEY, "map");
    saveViewMode(PROCESS_VIEW_MODE_KEY, "list");
    expect(loadViewMode(CLIENTS_VIEW_MODE_KEY, MODES, "list")).toBe("map");
    expect(
      loadViewMode(PROCESS_VIEW_MODE_KEY, ["kanban", "list"], "kanban"),
    ).toBe("list");
  });
});

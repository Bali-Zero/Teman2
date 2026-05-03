import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { CommandPalette, type CommandAction } from "./CommandPalette";

describe("CommandPalette", () => {
  it("filters actions by query and invokes handler on Enter", () => {
    const run = vi.fn();
    const actions: CommandAction[] = [
      {
        id: "create-kitas",
        label: "Crea pratica KITAS",
        group: "Pratiche",
        run,
      },
      { id: "export-lkpm", label: "Esporta LKPM", group: "Tax", run: () => {} },
    ];
    const { getByRole, getByText } = render(
      <CommandPalette open actions={actions} onClose={() => {}} />,
    );
    const input = getByRole("combobox");
    fireEvent.change(input, { target: { value: "kit" } });
    expect(getByText("Crea pratica KITAS")).toBeTruthy();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(run).toHaveBeenCalledTimes(1);
  });
});

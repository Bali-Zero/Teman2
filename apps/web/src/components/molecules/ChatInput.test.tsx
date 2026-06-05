import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("sends a trimmed message on Enter and clears the textarea", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByRole("textbox", { name: /chat message/i });
    await user.type(input, "  How to set up a PT PMA?  ");
    await user.keyboard("{Enter}");

    expect(onSend).toHaveBeenCalledWith("How to set up a PT PMA?");
    expect(input).toHaveValue("");
  });

  it("keeps Shift+Enter as a newline without sending", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByRole("textbox", { name: /chat message/i });
    await user.type(input, "line one");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(input, "line two");

    expect(onSend).not.toHaveBeenCalled();
    expect(input).toHaveValue("line one\nline two");
  });

  it("shows an abort control while loading", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const onAbort = vi.fn();
    render(<ChatInput onSend={onSend} onAbort={onAbort} isLoading />);

    expect(screen.getByRole("textbox", { name: /chat message/i })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /stop/i }));

    expect(onAbort).toHaveBeenCalledTimes(1);
    expect(onSend).not.toHaveBeenCalled();
  });
});

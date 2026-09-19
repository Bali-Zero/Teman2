import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "./Modal";

function renderModal(isSaving: boolean) {
  const onClose = vi.fn();
  const view = render(
    <Modal
      title="Sample modal"
      onClose={onClose}
      isSaving={isSaving}
      onSave={(event) => event.preventDefault()}
    >
      <button type="button">Synthetic content</button>
    </Modal>,
  );

  return { onClose, ...view };
}

function backdrop(container: HTMLElement) {
  const element = container.querySelector("div.absolute.inset-0");
  if (!element) throw new Error("Modal backdrop not found");
  return element;
}

describe("Modal close guard", () => {
  it("does not close from the backdrop while saving", async () => {
    const user = userEvent.setup();
    const { container, onClose } = renderModal(true);

    await user.click(backdrop(container));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("does not close from X while saving and disables it", async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal(true);
    const closeButton = screen.getByRole("button", { name: "Close modal" });

    expect(closeButton).toBeDisabled();
    expect(closeButton).toHaveAttribute("aria-disabled", "true");
    await user.click(closeButton);

    expect(onClose).not.toHaveBeenCalled();
  });

  it("does not close from Escape while saving", () => {
    const { onClose } = renderModal(true);

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).not.toHaveBeenCalled();
  });

  it.each([
    [
      "backdrop",
      async (container: HTMLElement) => userEvent.click(backdrop(container)),
    ],
    [
      "X",
      async () =>
        userEvent.click(screen.getByRole("button", { name: "Close modal" })),
    ],
    ["Escape", async () => fireEvent.keyDown(document, { key: "Escape" })],
  ])("closes exactly once from %s when not saving", async (_vector, close) => {
    const { container, onClose } = renderModal(false);

    await close(container);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it.each([true, false])(
    "does not close when dialog content is clicked while isSaving=%s",
    async (isSaving) => {
      const user = userEvent.setup();
      const { onClose } = renderModal(isSaving);

      await user.click(
        screen.getByRole("button", { name: "Synthetic content" }),
      );

      expect(onClose).not.toHaveBeenCalled();
    },
  );
});

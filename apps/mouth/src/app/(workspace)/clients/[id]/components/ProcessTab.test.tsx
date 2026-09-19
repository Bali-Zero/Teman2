import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ClientProfile } from "@/lib/api/crm/crm.types";
import { api } from "@/lib/api";
import { ProcessTab } from "./ProcessTab";

const { toast, toastSuccess, toastError, toastDismiss } = vi.hoisted(() => {
  const mockToast = Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  });

  return {
    toast: mockToast,
    toastSuccess: mockToast.success,
    toastError: mockToast.error,
    toastDismiss: mockToast.dismiss,
  };
});

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn(),
    crm: {
      deletePractice: vi.fn(),
    },
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("sonner", () => ({ toast }));

vi.mock("./AiSummaryCard", () => ({
  AiSummaryCard: () => null,
}));

type ConfirmOptions = {
  action: { onClick: () => Promise<void> };
  cancel: { onClick: () => void };
};

const practice: ClientProfile["practices"][number] = {
  id: 71,
  status: "cancelled",
  practice_type_code: "SYNTHETIC",
  practice_type_name: "Synthetic Process",
};

function getConfirmOptions(): ConfirmOptions {
  return toast.mock.calls[toast.mock.calls.length - 1]?.[1] as ConfirmOptions;
}

function renderProcessTab(onRefresh = vi.fn()) {
  render(
    <ProcessTab
      clientId={4}
      practices={[practice]}
      formatDate={(value) => value}
      onRefresh={onRefresh}
    />,
  );

  return { onRefresh };
}

function openDeleteConfirmation() {
  fireEvent.click(screen.getByRole("button", { name: "Delete process" }));
  return getConfirmOptions();
}

describe("ProcessTab practice deletion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getProfile).mockResolvedValue({
      email: "operator@test.invalid",
    } as never);
  });

  it("re-enables the delete button after a successful soft delete", async () => {
    let resolveDelete:
      ((value: { success: boolean; message: string }) => void) | undefined;
    vi.mocked(api.crm.deletePractice).mockImplementation(
      () =>
        new Promise<{ success: boolean; message: string }>((resolve) => {
          resolveDelete = resolve;
        }),
    );
    const { onRefresh } = renderProcessTab();

    const confirmation = openDeleteConfirmation();
    let deletion: Promise<void>;
    act(() => {
      deletion = confirmation.action.onClick();
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Delete process" }),
      ).toBeDisabled(),
    );

    await act(async () => {
      resolveDelete?.({ success: true, message: "Practice cancelled" });
      await deletion;
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Delete process" }),
      ).toBeEnabled(),
    );
    expect(api.crm.deletePractice).toHaveBeenCalledWith(
      71,
      "operator@test.invalid",
    );
    expect(toastSuccess).toHaveBeenCalledWith("Process deleted");
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("re-enables the delete button and reports an API error", async () => {
    vi.mocked(api.crm.deletePractice).mockRejectedValue(
      new Error("Synthetic failure"),
    );
    renderProcessTab();

    await act(async () => {
      await openDeleteConfirmation().action.onClick();
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Delete process" }),
      ).toBeEnabled(),
    );
    expect(toastError).toHaveBeenCalledWith("Error", {
      description: "Synthetic failure",
    });
  });

  it("leaves the delete button enabled when confirmation is cancelled", () => {
    renderProcessTab();

    openDeleteConfirmation().cancel.onClick();

    expect(
      screen.getByRole("button", { name: "Delete process" }),
    ).toBeEnabled();
    expect(api.getProfile).not.toHaveBeenCalled();
    expect(api.crm.deletePractice).not.toHaveBeenCalled();
    expect(toastDismiss).toHaveBeenCalledOnce();
  });
});

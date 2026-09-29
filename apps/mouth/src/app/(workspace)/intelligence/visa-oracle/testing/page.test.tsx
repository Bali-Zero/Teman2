import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Page from "./TestingCampaign";

const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { request: mocks.request } }));

describe("Oracle team testing", () => {
  beforeEach(() => vi.clearAllMocks());
  it("fails closed when the authenticated campaign cannot be loaded", async () => {
    mocks.request.mockRejectedValue(new Error("Unavailable"));
    render(<Page />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Data pengujian belum dapat dimuat",
    );
    expect(
      screen.queryByRole("link", { name: /Buka Visa Oracle/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Simpan hasil/ }),
    ).not.toBeInTheDocument();
  });
  it("allows retry without inventing a tester or a result", async () => {
    mocks.request.mockRejectedValue(new Error("Unavailable"));
    render(<Page />);
    await screen.findByRole("alert");
    await userEvent.click(screen.getByRole("button", { name: "Coba lagi" }));
    expect(mocks.request).toHaveBeenCalledTimes(2);
  });
});

const fixture = (started = false) => ({
  campaign: {
    id: "test-campaign",
    start_date: "2026-09-28",
    end_date: "2026-10-02",
    timezone: "Asia/Makassar",
    planned: 150,
    per_day: 5,
    plan_version: "1",
  },
  viewer: { slot: "T01", can_review: false, can_configure: false },
  slots: [],
  assignments: Array.from({ length: 5 }, (_, index) => ({
    id: `assignment-${index}`,
    slot: "T01",
    day: "2026-09-28",
    index,
    can_start: true,
    can_record_results: started,
    scenario: {
      id: `case-${index}`,
      title: `Kasus sintetis ${index + 1}`,
      focus: "Test fixture",
      inputs: { nationality: "Synthetic" },
      instructions: ["Use synthetic inputs only"],
    },
    record: started
      ? {
          status: "started",
          expected: {
            text: "A prior expectation",
            basis: "hypothesis",
            reference: "",
            browser: "Test browser",
            device: "Test device",
            displayed_version: "unknown",
          },
          started_at: "2026-09-28T01:00:00Z",
          submitted_at: null,
          result: null,
          review: null,
        }
      : null,
  })),
  progress: [],
  counts: {
    planned: 150,
    started: started ? 5 : 0,
    submitted: 0,
    reproduced: 0,
    reviewed: 0,
    reached: 0,
    blocked: 0,
  },
});

describe("Server-controlled test workflow", () => {
  beforeEach(() => vi.clearAllMocks());
  it("shows five assigned cases but no Oracle link, reviewer tools or admin controls before server lock", async () => {
    mocks.request.mockResolvedValue(fixture());
    render(<Page />);
    await screen.findByText("Penugasan Anda");
    expect(
      screen.getAllByRole("button", { name: /Kasus \d · case-/ }),
    ).toHaveLength(5);
    await userEvent.click(
      screen.getByRole("button", { name: /Kasus 1 · case-0/ }),
    );
    expect(
      screen.queryByRole("link", { name: "Buka Visa Oracle" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Status hasil aktual"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Antrean reviewer")).not.toBeInTheDocument();
    expect(screen.queryByText("Konfigurasi enam slot")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Kunci ekspektasi" }),
    ).toBeDisabled();
  });
  it("locks the fifth expectation then unlocks Oracle only after the server confirms the whole day", async () => {
    const user = userEvent.setup();
    const beforeLast = fixture(true);
    beforeLast.assignments = beforeLast.assignments.map((a, index) => ({
      ...a,
      can_record_results: false,
      record: index === 0 ? null : a.record,
    }));
    mocks.request
      .mockResolvedValueOnce(beforeLast)
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce(fixture(true));
    render(<Page />);
    await user.click(
      await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
    );
    await user.type(
      screen.getByLabelText("Hasil yang Anda harapkan dan alasannya"),
      "Needs review",
    );
    await user.type(screen.getByLabelText("Browser dan versi"), "Test browser");
    await user.type(screen.getByLabelText("Perangkat / OS"), "Test device");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Kunci ekspektasi" }));
    expect(
      await screen.findByRole("link", { name: "Buka Visa Oracle" }),
    ).toHaveAttribute("target", "_blank");
    const [, options] = mocks.request.mock.calls[1];
    expect(mocks.request.mock.calls[1][0]).toBe(
      "/api/visa-oracle/testing/assignment-0/start",
    );
    expect(JSON.parse(options.body)).toMatchObject({
      text: "Needs review",
      synthetic_only: true,
      displayed_version: "unknown",
    });
    expect(
      screen.getByLabelText("Hasil yang Anda harapkan dan alasannya"),
    ).toBeDisabled();
    expect(
      screen.getByLabelText("Hasil yang Anda harapkan dan alasannya"),
    ).toHaveValue("A prior expectation");
    expect(
      screen.getByRole("button", { name: "Kirim observasi" }),
    ).toBeDisabled();
  });
  it("does not unlock Oracle when the start write fails", async () => {
    const user = userEvent.setup();
    mocks.request
      .mockResolvedValueOnce(fixture())
      .mockRejectedValueOnce(new Error("Conflict"));
    render(<Page />);
    await user.click(
      await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
    );
    await user.type(
      screen.getByLabelText("Hasil yang Anda harapkan dan alasannya"),
      "Needs review",
    );
    await user.type(screen.getByLabelText("Browser dan versi"), "Test browser");
    await user.type(screen.getByLabelText("Perangkat / OS"), "Test device");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Kunci ekspektasi" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Perubahan belum tersimpan",
    );
    expect(
      screen.queryByRole("link", { name: "Buka Visa Oracle" }),
    ).not.toBeInTheDocument();
  });
  it("never assumes a tester slot for an unassigned account", async () => {
    const data = fixture();
    mocks.request.mockResolvedValue({
      ...data,
      viewer: { slot: null, can_review: false, can_configure: false },
    });
    render(<Page />);
    expect(
      await screen.findByText(/Akun ini belum ditempatkan/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Kasus 1/ }),
    ).not.toBeInTheDocument();
  });
});

it("submits a blocked observation with explicit attestation and without a client-supplied identity", async () => {
  vi.clearAllMocks();
  const user = userEvent.setup();
  const startedData = fixture(true);
  mocks.request
    .mockResolvedValueOnce({
      ...startedData,
      assignments: startedData.assignments.map((a) =>
        a.record
          ? {
              ...a,
              record: { ...a.record, result: { screenshot_available: true } },
            }
          : a,
      ),
    })
    .mockResolvedValueOnce({ ok: true })
    .mockResolvedValueOnce(fixture(true));
  render(<Page />);
  await user.click(
    await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
  );
  await user.type(
    screen.getByLabelText("Input persis dan langkah yang dilakukan"),
    "1. Entered synthetic fixture. 2. Service timed out.",
  );
  await user.selectOptions(
    screen.getByLabelText("Status hasil aktual"),
    "blocked",
  );
  await user.type(
    screen.getByLabelText("Hasil aktual dan alasan yang tampil"),
    "No result, service timeout.",
  );
  await user.type(
    screen.getByLabelText(
      "URL / referensi sumber, serta informasi yang tidak ditampilkan",
    ),
    "Not shown",
  );
  await user.type(
    screen.getByLabelText(/Bagaimana Oracle menangani/),
    "Not shown",
  );
  await user.type(
    screen.getByLabelText(/Komentar singkat dan dapat ditindaklanjuti/),
    "Investigate timeout before retesting the fixture.",
  );
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Kirim observasi" }));
  await screen.findByText("Perubahan tersimpan di server.");
  const [endpoint, options] = mocks.request.mock.calls[1];
  expect(endpoint).toBe("/api/visa-oracle/testing/assignment-0/result");
  expect(options.method).toBe("PUT");
  const payload = JSON.parse(options.body);
  expect(payload).toMatchObject({
    actual_state: "blocked",
    submit: true,
    synthetic_only: true,
  });
  expect(payload).not.toHaveProperty("slot");
  expect(payload).not.toHaveProperty("user_id");
  expect(payload).not.toHaveProperty("screenshot_available");
});

it("keeps review tools scoped to the tester's own observations, excluding a peer's", async () => {
  vi.clearAllMocks();
  const data = fixture(true);
  const own = {
    ...data.assignments[0],
    record: {
      ...data.assignments[0].record!,
      status: "submitted",
      result: { actual: "Observed synthetic result" },
    },
  };
  const other = {
    ...own,
    id: "other-assignment",
    slot: "T02",
    scenario: { ...own.scenario, title: "Foreign synthetic case" },
  };
  mocks.request.mockResolvedValue({
    ...data,
    viewer: { slot: "T01", can_review: true, can_configure: false },
    assignments: [own, other],
  });
  render(<Page />);
  expect(await screen.findByText("Antrean reviewer")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Ekspor data JSON" }),
  ).toBeInTheDocument();
  // Self-review: `own` (viewer's slot T01) is reviewable, `other` (T02) is not.
  expect(screen.getAllByLabelText("Keputusan reviewer")).toHaveLength(1);
  expect(screen.queryByText("Konfigurasi enam slot")).not.toBeInTheDocument();
});

it("rejects a PNG larger than 600 KiB before sending any image", async () => {
  vi.clearAllMocks();
  const user = userEvent.setup();
  mocks.request.mockResolvedValue(fixture(true));
  render(<Page />);
  await user.click(
    await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
  );
  await user.upload(
    screen.getByLabelText("Screenshot privat PNG/JPG/WebP"),
    new File([new Uint8Array(600 * 1024 + 1)], "oversized.png", {
      type: "image/png",
    }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("600 KiB");
  expect(mocks.request).toHaveBeenCalledTimes(1);
});

it("saves PNG bytes only through the private result endpoint and resets the attachment on case change", async () => {
  vi.clearAllMocks();
  const user = userEvent.setup();
  mocks.request.mockResolvedValue(fixture(true));
  render(<Page />);
  await user.click(
    await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
  );
  const bytes = Uint8Array.from(
    atob(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==",
    ),
    (char) => char.charCodeAt(0),
  );
  await user.upload(
    screen.getByLabelText("Screenshot privat PNG/JPG/WebP"),
    new File([bytes], "synthetic.png", { type: "image/png" }),
  );
  await screen.findByText(/synthetic.png siap disimpan/);
  await user.click(screen.getByRole("checkbox"));
  await user.click(
    screen.getByRole("button", { name: "Simpan draf ke server" }),
  );
  await screen.findByText("Perubahan tersimpan di server.");
  const [endpoint, options] = mocks.request.mock.calls[1];
  expect(endpoint).toBe("/api/visa-oracle/testing/assignment-0/result");
  const payload = JSON.parse(options.body);
  expect(payload.screenshot_base64).toBe(btoa(String.fromCharCode(...bytes)));
  expect(payload.screenshot_base64).not.toContain("data:");
  await user.click(screen.getByRole("button", { name: /Kasus 2 · case-1/ }));
  expect(
    screen.queryByText(/synthetic.png siap disimpan/),
  ).not.toBeInTheDocument();
});

it("rejects disguised SVG bytes and exposes stored images only at the private endpoint", async () => {
  vi.clearAllMocks();
  const user = userEvent.setup();
  const data = fixture(true);
  mocks.request.mockResolvedValue({
    ...data,
    assignments: data.assignments.map((a) =>
      a.record
        ? {
            ...a,
            record: { ...a.record, result: { screenshot_available: true } },
          }
        : a,
    ),
  });
  render(<Page />);
  await user.click(
    await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
  );
  expect(
    screen.getByRole("link", {
      name: "Lihat screenshot tersimpan (akses tim)",
    }),
  ).toHaveAttribute("href", "/api/visa-oracle/testing/assignment-0/screenshot");
  await user.upload(
    screen.getByLabelText("Screenshot privat PNG/JPG/WebP"),
    new File(
      [
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
      ],
      "fake.png",
      { type: "image/png" },
    ),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "SVG tidak diterima",
  );
  expect(mocks.request).toHaveBeenCalledTimes(1);
});

it.each([
  ["JPEG", [255, 216, 255, 224, 0, 16]],
  ["WebP", [82, 73, 70, 70, 12, 0, 0, 0, 87, 69, 66, 80]],
])(
  "accepts verified %s signature even when a screenshot has a PNG filename",
  async (_format, content) => {
    vi.clearAllMocks();
    const user = userEvent.setup();
    mocks.request.mockResolvedValue(fixture(true));
    render(<Page />);
    await user.click(
      await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
    );
    await user.upload(
      screen.getByLabelText("Screenshot privat PNG/JPG/WebP"),
      new File([new Uint8Array(content as number[])], "capture.png", {
        type: "image/png",
      }),
    );
    expect(
      await screen.findByText(/capture.png siap disimpan/),
    ).toBeInTheDocument();
    expect(mocks.request).toHaveBeenCalledTimes(1);
  },
);

it("uses server-wide reached and blocked counts even when peer results are blind", async () => {
  vi.clearAllMocks();
  const data = fixture();
  mocks.request.mockResolvedValue({
    ...data,
    counts: { ...data.counts, reached: 19, blocked: 7 },
  });
  render(<Page />);
  expect(
    await screen.findByText(/19 mencapai status hasil, 7 terhalang/),
  ).toBeInTheDocument();
});

it("does not show review controls for a peer whose results are still blind", async () => {
  vi.clearAllMocks();
  const data = fixture(true);
  mocks.request.mockResolvedValue({
    ...data,
    viewer: { ...data.viewer, can_review: true },
    assignments: [
      ...data.assignments,
      {
        ...data.assignments[0],
        id: "blind-peer",
        slot: "T02",
        record: {
          status: "submitted",
          started_at: "2026-09-28T01:00:00Z",
          submitted_at: "2026-09-28T02:00:00Z",
        },
      },
    ],
  });
  render(<Page />);
  await screen.findByText("Antrean reviewer");
  expect(screen.queryByLabelText("Keputusan reviewer")).not.toBeInTheDocument();
  expect(screen.getByText(/Kunci kelima ekspektasi/)).toBeInTheDocument();
});

it("honors can_start=false without inventing a local date override", async () => {
  vi.clearAllMocks();
  const data = fixture();
  mocks.request.mockResolvedValue({
    ...data,
    assignments: data.assignments.map((a) => ({ ...a, can_start: false })),
  });
  render(<Page />);
  await userEvent.click(
    await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
  );
  expect(
    screen.getByRole("button", { name: "Kunci ekspektasi" }),
  ).toBeDisabled();
  expect(
    screen.getByLabelText("Hasil yang Anda harapkan dan alasannya"),
  ).toBeDisabled();
  expect(screen.getByText(/WITA menentukan tanggal/)).toBeInTheDocument();
});

it("removes a private attachment after submission using the delete endpoint and server reload", async () => {
  vi.clearAllMocks();
  const user = userEvent.setup();
  const data = fixture(true);
  const withImage = {
    ...data,
    assignments: data.assignments.map((a) =>
      a.record
        ? {
            ...a,
            can_start: false,
            record: {
              ...a.record,
              status: "submitted",
              result: { screenshot_available: true },
            },
          }
        : a,
    ),
  };
  const withoutImage = {
    ...withImage,
    assignments: withImage.assignments.map((a) =>
      a.record
        ? {
            ...a,
            record: { ...a.record, result: { screenshot_available: false } },
          }
        : a,
    ),
  };
  mocks.request
    .mockResolvedValueOnce(withImage)
    .mockResolvedValueOnce({ ok: true })
    .mockResolvedValueOnce(withoutImage);
  render(<Page />);
  await user.click(
    await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
  );
  await user.click(screen.getByRole("button", { name: "Hapus lampiran" }));
  await screen.findByText("Perubahan tersimpan di server.");
  expect(mocks.request.mock.calls[1][0]).toBe(
    "/api/visa-oracle/testing/assignment-0/screenshot",
  );
  expect(mocks.request.mock.calls[1][1].method).toBe("DELETE");
  expect(
    screen.queryByRole("link", {
      name: "Lihat screenshot tersimpan (akses tim)",
    }),
  ).not.toBeInTheDocument();
});

it.each([1, 4])(
  "keeps results and Oracle locked with only %i personal expectations locked while allowing the next expectation",
  async (lockedCount) => {
    vi.clearAllMocks();
    const user = userEvent.setup();
    const data = fixture(true);
    mocks.request.mockResolvedValue({
      ...data,
      assignments: data.assignments.map((a, index) => ({
        ...a,
        record: index < lockedCount ? a.record : null,
        can_record_results: false,
      })),
    });
    render(<Page />);
    await user.click(
      await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
    );
    expect(
      screen.getByText(
        `Ekspektasi terkunci untuk hari yang dipilih: ${lockedCount}/5.`,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Buka Visa Oracle" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByLabelText("Input persis dan langkah yang dilakukan"),
    ).toBeDisabled();
    expect(screen.getByLabelText("Status hasil aktual")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Simpan draf ke server" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Kirim observasi" }),
    ).toBeDisabled();
    fireEvent.submit(
      screen.getByRole("button", { name: "Kirim observasi" }).closest("form")!,
    );
    expect(mocks.request).toHaveBeenCalledTimes(1);
    await user.click(
      screen.getByRole("button", {
        name: new RegExp(`Kasus ${lockedCount + 1} · case-${lockedCount}`),
      }),
    );
    expect(
      screen.getByLabelText("Hasil yang Anda harapkan dan alasannya"),
    ).toBeEnabled();
  },
);

it("fails closed if the result permission is missing even with five visible locked expectations", async () => {
  vi.clearAllMocks();
  const data = fixture(true);
  mocks.request.mockResolvedValue({
    ...data,
    assignments: data.assignments.map((a) => ({
      ...a,
      can_record_results: undefined,
    })),
  });
  render(<Page />);
  await userEvent.click(
    await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
  );
  expect(
    screen.queryByRole("link", { name: "Buka Visa Oracle" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Status hasil aktual")).toBeDisabled();
});

it("keeps a saved self-review visible but disables every editing control and submission", async () => {
  vi.clearAllMocks();
  const data = fixture(true);
  const other = {
    ...data.assignments[0],
    id: "reviewed-own",
    slot: "T01",
    record: {
      ...data.assignments[0].record!,
      status: "submitted",
      result: { actual: "Observed synthetic outcome" },
      review: {
        verdict: "not_issue",
        comment: "Checked source and repeated the synthetic steps.",
        reproduced: false,
        reproduction_evidence: "",
        reviewed_at: "2026-09-28T03:00:00Z",
      },
    },
  };
  mocks.request.mockResolvedValue({
    ...data,
    viewer: { ...data.viewer, can_review: true },
    assignments: [...data.assignments, other],
  });
  render(<Page />);
  await screen.findByText("Antrean reviewer");
  const verdict = screen.getByLabelText("Keputusan reviewer");
  expect(verdict).toHaveValue("not_issue");
  expect(verdict).toBeDisabled();
  expect(
    screen.getByLabelText("Alasan, bukti, dan referensi reviewer"),
  ).toHaveValue("Checked source and repeated the synthetic steps.");
  expect(
    screen.getByLabelText("Alasan, bukti, dan referensi reviewer"),
  ).toBeDisabled();
  expect(
    screen.getByLabelText("Referensi observasi kedua dan langkah pengulangan"),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Simpan tinjauan", hidden: true }),
  ).toBeDisabled();
  fireEvent.submit(verdict.closest("form")!);
  expect(mocks.request).toHaveBeenCalledTimes(1);
});

it("allows continuing an already-unlocked day when starting new expectations is no longer allowed", async () => {
  vi.clearAllMocks();
  const data = fixture(true);
  mocks.request.mockResolvedValue({
    ...data,
    assignments: data.assignments.map((a) => ({
      ...a,
      can_start: false,
      can_record_results: true,
    })),
  });
  render(<Page />);
  await userEvent.click(
    await screen.findByRole("button", { name: /Kasus 1 · case-0/ }),
  );
  expect(
    screen.getByRole("link", { name: "Buka Visa Oracle" }),
  ).toHaveAttribute("target", "_blank");
  expect(
    screen.getByLabelText("Input persis dan langkah yang dilakukan"),
  ).toBeEnabled();
  expect(
    screen.getByLabelText("Hasil yang Anda harapkan dan alasannya"),
  ).toBeDisabled();
});

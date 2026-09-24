import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { measurePortalAction, trackPortalPage } from "./portal-analytics";

const client = () => ({ role: "client", impersonating: false });
const gtag = vi.fn();
const ga = window as typeof window & { gtag?: typeof gtag };

beforeEach(() => {
  gtag.mockReset();
  ga.gtag = gtag;
  window.history.replaceState(
    {},
    "",
    "/portal/messages?email=private%40example.test",
  );
  document.title = "Private client name";
});
afterEach(() => {
  delete ga.gtag;
});

describe("portal usage privacy and availability", () => {
  it("reports a closed section without IDs, query, page title, or referrer", () => {
    trackPortalPage("/portal/process/12345", client);
    const payload = gtag.mock.calls[0][2];
    expect(payload.portal_section).toBe("process");
    expect(payload.page_location).toBe(
      window.location.origin + "/portal/process",
    );
    expect(payload.page_title).toBe("Client portal");
    expect(JSON.stringify(gtag.mock.calls)).not.toMatch(
      /12345|private|Private/,
    );
  });

  it.each([
    "/portal/register",
    "/portal/login",
    "/portal/partner/dashboard",
    "/clients/12345",
  ])("does not collect auth, partner or staff routes: %s", (path) => {
    trackPortalPage(path, client);
    expect(gtag).not.toHaveBeenCalled();
  });

  it.each([
    { role: "admin", impersonating: false },
    { role: "client", impersonating: true },
    { role: undefined, impersonating: false },
  ])("excludes staff, previews and unknown identities", (context) => {
    trackPortalPage("/portal", () => context);
    expect(gtag).not.toHaveBeenCalled();
  });

  it("emits submission and success without request or response data", async () => {
    const result = {
      content: "private message",
      file_name: "private-passport.pdf",
    };
    expect(
      await measurePortalAction("message_send", client, async () => result),
    ).toBe(result);
    expect(gtag.mock.calls.map((c) => c[1])).toEqual([
      "portal_action_started",
      "portal_action_completed",
    ]);
    expect(JSON.stringify(gtag.mock.calls)).not.toMatch(
      /private|passport|file_name/,
    );
  });

  it("records a status class and rethrows the original error", async () => {
    const error = { statusCode: 503, message: "private error payload" };
    await expect(
      measurePortalAction("document_upload", client, async () => {
        throw error;
      }),
    ).rejects.toBe(error);
    expect(gtag.mock.calls[1][1]).toBe("portal_action_failed");
    expect(gtag.mock.calls[1][2].failure_class).toBe("server");
    expect(JSON.stringify(gtag.mock.calls)).not.toContain("private");
  });

  it("preserves API behavior if storage or GA throws, or GA is unavailable", async () => {
    const operation = vi.fn().mockResolvedValue("ok");
    const brokenContext = () => {
      throw new Error("storage unavailable");
    };
    expect(
      await measurePortalAction("message_send", brokenContext, operation),
    ).toBe("ok");
    gtag.mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(await measurePortalAction("message_send", client, operation)).toBe(
      "ok",
    );
    delete ga.gtag;
    expect(await measurePortalAction("message_send", client, operation)).toBe(
      "ok",
    );
    expect(operation).toHaveBeenCalledTimes(3);
  });
});

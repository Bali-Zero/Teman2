import { describe, it, expect, vi, beforeEach } from "vitest";
import { emailApi } from "../api";

// Mock logger
vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    warn: vi.fn(),
  },
}));

describe("emailApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();
  });

  describe("getConnectionStatus", () => {
    it("returns connection status", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () =>
          Promise.resolve({
            connected: true,
            email: "user@balizero.com",
            account_id: "acc-123",
            expires_at: "2024-12-31",
          }),
      });

      const status = await emailApi.getConnectionStatus();
      expect(status.connected).toBe(true);
      expect(status.email).toBe("user@balizero.com");
    });
  });

  describe("getFolders", () => {
    it("returns folder list", async () => {
      const mockFolders = {
        folders: [
          {
            folder_id: "inbox-1",
            folder_name: "Inbox",
            folder_path: "/Inbox",
            folder_type: "inbox",
            unread_count: 5,
            total_count: 100,
          },
        ],
      };

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve(mockFolders),
      });

      const result = await emailApi.getFolders();
      expect(result.folders).toHaveLength(1);
      expect(result.folders[0].folder_name).toBe("Inbox");
    });
  });

  describe("listEmails", () => {
    it("includes query params in request", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () =>
          Promise.resolve({
            emails: [],
            total: 0,
            has_more: false,
          }),
      });

      await emailApi.listEmails({
        folder_id: "inbox-1",
        query: "test",
        limit: 50,
      });

      const callUrl = (global.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0][0] as string;
      expect(callUrl).toContain("folder_id=inbox-1");
      expect(callUrl).toContain("search=test");
      expect(callUrl).toContain("limit=50");
    });
  });

  describe("sendEmail", () => {
    it("sends POST request with email data", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () =>
          Promise.resolve({ success: true, message_id: "new-msg-1" }),
      });

      const result = await emailApi.sendEmail({
        to: ["recipient@example.com"],
        subject: "Test Subject",
        html_content: "<p>Hello</p>",
      });

      expect(result.success).toBe(true);
      expect(result.message_id).toBe("new-msg-1");

      const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain("/emails");
      expect(options.method).toBe("POST");
    });
  });

  describe("markRead", () => {
    it("sends PATCH request with message IDs", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({ success: true }),
      });

      await emailApi.markRead({
        message_ids: ["msg-1", "msg-2"],
        is_read: true,
      });

      const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain("/mark-read");
      expect(options.method).toBe("PATCH");
      const body = JSON.parse(options.body as string);
      expect(body.message_ids).toEqual(["msg-1", "msg-2"]);
      expect(body.is_read).toBe(true);
    });
  });

  describe("toggleFlag", () => {
    it("sends PATCH request for flagging", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({ success: true }),
      });

      await emailApi.toggleFlag("msg-1", true);

      const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain("/msg-1/flag");
      expect(options.method).toBe("PATCH");
    });
  });

  describe("deleteEmails", () => {
    it("sends POST request with message IDs", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({ success: true }),
      });

      await emailApi.deleteEmails(["msg-1", "msg-2"]);

      const [, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      const body = JSON.parse(options.body as string);
      expect(body.message_ids).toEqual(["msg-1", "msg-2"]);
    });
  });

  describe("disconnect", () => {
    it("sends DELETE request", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({ success: true }),
      });

      await emailApi.disconnect();

      const [, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(options.method).toBe("DELETE");
    });
  });

  describe("getClientByEmail", () => {
    it("returns client data when found", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () =>
          Promise.resolve({
            id: "client-1",
            full_name: "John Doe",
            client_type: "individual",
          }),
      });

      const client = await emailApi.getClientByEmail("john@example.com");
      expect(client).not.toBeNull();
      expect(client!.full_name).toBe("John Doe");
    });

    it("returns null on error", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error("Not found"),
      );

      const client = await emailApi.getClientByEmail("unknown@example.com");
      expect(client).toBeNull();
    });
  });

  describe("error handling", () => {
    it("redirects on 401", async () => {
      const replaceSpy = vi.fn();
      Object.defineProperty(window, "location", {
        value: { replace: replaceSpy },
        writable: true,
        configurable: true,
      });

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 401,
        headers: new Headers(),
        json: () => Promise.resolve({ detail: "Unauthorized" }),
      });

      await expect(emailApi.getConnectionStatus()).rejects.toThrow(
        "Authentication required",
      );
      expect(replaceSpy).toHaveBeenCalledWith(
        expect.stringContaining("kita.balizero.com/login"),
      );
    });
  });
});

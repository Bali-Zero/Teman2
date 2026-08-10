import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicAuthClient } from "./public-auth";

describe("PublicAuthClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it.each([
    "/api/admin/system-health",
    "/api/auth/../../admin/system-health",
    "/api/auth/login?debug=/api/admin/system-health",
  ])(
    "rejects non-canonical endpoint %s before touching the network",
    async (endpoint) => {
      const fetchSpy = vi.spyOn(globalThis, "fetch");
      const client = new PublicAuthClient();

      await expect(client.request(endpoint)).rejects.toThrow(
        "rejected a non-auth endpoint",
      );
      expect(fetchSpy).not.toHaveBeenCalled();
    },
  );

  it("returns a status-bearing error without redirecting on invalid credentials", async () => {
    window.history.replaceState({}, "", "/portal/login-upgraded");
    const locationBeforeRequest = window.location.href;
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid credentials" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = new PublicAuthClient();

    await expect(
      client.request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: "synthetic.user@example.test",
          pin: "781245",
        }),
      }),
    ).rejects.toMatchObject({ status: 401 });
    expect(window.location.href).toBe(locationBeforeRequest);
  });

  it("persists the synthetic session returned by AuthApi", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          message: "ok",
          data: {
            token: "synthetic-token",
            token_type: "Bearer",
            expiresIn: 3600,
            csrfToken: "synthetic-csrf",
            user: {
              id: "synthetic-user",
              email: "synthetic.user@example.test",
              name: "Synthetic User",
              role: "client",
            },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = new PublicAuthClient();
    const auth = new (await import("./auth/auth.api")).AuthApi(client);

    await auth.login("synthetic.user@example.test", "781245");

    expect(localStorage.getItem("auth_token")).toBe("synthetic-token");
    expect(
      JSON.parse(localStorage.getItem("user_profile") ?? "{}"),
    ).toMatchObject({ id: "synthetic-user", role: "client" });
  });
});

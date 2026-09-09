import {
  contactTopics, isContactSourcePage, isContactTopic, safeCapturedWhatsAppHref,
} from "../../../../lib/destinations/lead-handoff";

export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "no-store" };
const reply = (status: number): Response => Response.json({ available: false }, { status, headers });

/** The owner must configure an independent backend origin before enabling writes. */
function configuredOrigin(requestUrl: string): string | null {
  if (process.env.WEBSITE_LEAD_CAPTURE_ENABLED !== "true") return null;
  try {
    const url = new URL(process.env.WEBSITE_LEAD_CAPTURE_API_ORIGIN ?? "");
    const host = (value: string): string => value.replace(/^www\./, "");
    if (url.protocol !== "https:" || url.username || url.password || url.port ||
      url.pathname !== "/" || url.search || url.hash ||
      host(url.hostname) === host(new URL(requestUrl).hostname) ||
      !url.hostname.includes(".") || /^(?:\d+\.)+\d+$/.test(url.hostname) ||
      /(?:\.localhost|\.local)$/.test(url.hostname)) return null;
    return url.origin;
  } catch { return null; }
}

export async function POST(request: Request): Promise<Response> {
  const origin = configuredOrigin(request.url);
  if (!origin) return reply(503);
  if (request.headers.get("origin") !== new URL(request.url).origin ||
    request.headers.get("content-type")?.split(";")[0] !== "application/json") return reply(403);
  if (Number(request.headers.get("content-length")) > 1024) return reply(413);

  let body: unknown;
  try {
    const reader = request.body?.getReader();
    if (!reader) return reply(400);
    const decoder = new TextDecoder();
    let text = "";
    let bytes = 0;
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      bytes += chunk.value.byteLength;
      if (bytes > 1024) { await reader.cancel(); return reply(413); }
      text += decoder.decode(chunk.value, { stream: true });
    }
    body = JSON.parse(text + decoder.decode());
  } catch { return reply(400); }
  if (!body || typeof body !== "object" || Array.isArray(body) ||
    Object.keys(body).some((key) => key !== "topic" && key !== "sourcePage") ||
    !("topic" in body) || !isContactTopic(body.topic) ||
    !("sourcePage" in body) || !isContactSourcePage(body.sourcePage)) return reply(400);
  const { topic, sourcePage } = body;

  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const capture = async (): Promise<Response> => {
      const upstream = await fetch(`${origin}/api/lead/capture`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        credentials: "omit", redirect: "error", cache: "no-store", signal: controller.signal,
        body: JSON.stringify({
          source: "cta_handoff",
          context: { topic, source_page: sourcePage },
          whatsapp_context: [
            { label: "Topic", value: contactTopics[topic] },
            { label: "Page", value: sourcePage },
          ],
        }),
      });
      if (upstream.status !== 201) return reply(502);
      const payload: unknown = await upstream.json();
      const href = payload && typeof payload === "object" && "whatsapp_url" in payload
        ? safeCapturedWhatsAppHref(payload.whatsapp_url) : null;
      return href ? Response.json({ whatsapp_url: href }, { status: 201, headers }) : reply(502);
    };
    return await Promise.race([
      capture(),
      new Promise<Response>((resolve) => {
        timer = setTimeout(() => { controller.abort(); resolve(reply(504)); }, 1200);
      }),
    ]);
  } catch { return reply(502); }
  finally { if (timer) clearTimeout(timer); }
}

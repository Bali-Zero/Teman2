/** Portal usage events. Closed labels only; never pass client or form data to GA4. */
export type PortalUsageContext = { role?: string; impersonating: boolean };
type ContextReader = () => PortalUsageContext;
type PortalAction = "message_send" | "document_upload";
type GtagWindow = Window & { gtag?: (...args: unknown[]) => void };

const SECTIONS = new Set([
  "visa",
  "company",
  "taxes",
  "vault",
  "documents",
  "messages",
  "chat",
  "process",
  "matters",
  "profile",
  "settings",
  "family",
  "lkpm",
  "deadlines",
  "billing",
]);

function sectionFor(pathname: string): string | null {
  if (pathname === "/portal" || pathname === "/portal/") return "overview";
  const parts = pathname.split("/");
  return parts[1] === "portal" && SECTIONS.has(parts[2]) ? parts[2] : null;
}

function eventContext(readContext: ContextReader, pathname: string) {
  try {
    if (typeof window === "undefined") return null;
    const context = readContext();
    const section = sectionFor(pathname);
    if (
      context.role !== "client" ||
      context.impersonating !== false ||
      !section
    )
      return null;
    return {
      event_category: "Portal",
      portal_section: section,
      // Override GA's inherited URL/title/referrer: dynamic IDs, queries and
      // client-specific page titles must never enter these custom events.
      page_location:
        window.location.origin +
        (section === "overview" ? "/portal" : "/portal/" + section),
      page_title: "Client portal",
      page_referrer: window.location.origin + "/portal",
    };
  } catch {
    return null;
  }
}

function emit(name: string, params: Record<string, string | number> | null) {
  if (!params) return;
  try {
    (window as GtagWindow).gtag?.("event", name, params);
  } catch {
    // Analytics must never interrupt navigation or an API operation.
  }
}

export function trackPortalPage(pathname: string, readContext: ContextReader) {
  emit("portal_page_view", eventContext(readContext, pathname));
}

type FailureClass =
  "validation" | "request" | "server" | "response" | "network" | "unknown";

export function beginPortalAction(
  action: PortalAction,
  readContext: ContextReader,
) {
  const context =
    typeof window === "undefined"
      ? null
      : eventContext(readContext, window.location.pathname);
  const params = context ? { ...context, portal_action: action } : null;
  const started = Date.now();
  let ended = false;
  emit("portal_action_started", params);
  const finish = (failure?: FailureClass) => {
    if (ended) return;
    ended = true;
    emit(
      failure ? "portal_action_failed" : "portal_action_completed",
      params
        ? {
            ...params,
            duration_ms: Date.now() - started,
            ...(failure ? { failure_class: failure } : {}),
          }
        : null,
    );
  };
  return {
    complete: () => finish(),
    fail: (failure: FailureClass) => finish(failure),
  };
}

export async function measurePortalAction<T>(
  action: PortalAction,
  readContext: ContextReader,
  operation: () => Promise<T>,
): Promise<T> {
  const attempt = beginPortalAction(action, readContext);
  try {
    const result = await operation();
    attempt.complete();
    return result;
  } catch (error) {
    const status =
      error && typeof error === "object" && "statusCode" in error
        ? error.statusCode
        : undefined;
    const failure =
      typeof status === "number" && status >= 500
        ? "server"
        : typeof status === "number" && status >= 400
          ? "request"
          : "unknown";
    attempt.fail(failure);
    throw error;
  }
}

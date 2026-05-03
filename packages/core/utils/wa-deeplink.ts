export const WA_CANONICAL = "628213107363";

export interface WaDeeplinkArgs {
  text?: string;
  source?: string;
  sessionId?: string;
  payload?: Record<string, unknown>;
}

export function buildWaDeeplink(args: WaDeeplinkArgs): string {
  let text = args.text;
  if (!text) {
    const parts: string[] = ["Ciao Bali Zero"];
    if (args.source) parts.push(`[source:${args.source}]`);
    if (args.sessionId) parts.push(`[session:${args.sessionId}]`);
    if (args.payload) parts.push(`[data:${JSON.stringify(args.payload)}]`);
    text = parts.join(" ");
  }
  return `https://wa.me/${WA_CANONICAL}?text=${encodeURIComponent(text)}`;
}

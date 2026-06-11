// Single source-of-truth module for both funnel taxonomies (MYTHOS IA-8):
// page-funnel events (FUNNEL_EVENTS) and tool-funnel events (APP_EVENTS)
// stay separate consts but are exported together so consumers and the
// cross-stack parity test cover the union.
export * from "./funnel-view";
export * from "./funnel-app";

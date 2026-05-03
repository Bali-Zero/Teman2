"use client";

/**
 * Messages Page
 *
 * Re-exports the Chat page component.
 * The sidebar links to /portal/messages but the original implementation
 * was at /portal/chat. This ensures both URLs work.
 */
export { default } from "../chat/page";

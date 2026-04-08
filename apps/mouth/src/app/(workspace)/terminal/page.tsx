/**
 * /terminal — Zantara Terminal full-page route.
 *
 * Authenticated via the (workspace) layout which enforces the SSO cookie
 * and redirects to kita.balizero.com/login on failure. This page simply
 * renders the Terminal component; all state lives in the `useTerminal` hook.
 *
 * Note: the workspace layout adds a top header (h=48px) and the sidebar.
 * Terminal sizes itself against `--bz-header-height` so the bottom input
 * bar docks against the viewport bottom without overflow.
 */

"use client";

import { Terminal } from "@/components/terminal";

export default function TerminalPage() {
  return (
    <div className="-m-4 md:-m-6 lg:-m-8">
      <Terminal />
    </div>
  );
}

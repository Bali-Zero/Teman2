"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KBLIPanelDetail } from "@/lib/kbli-panel-detail";
import { KBLIPanelCodeDetail } from "./KBLIPanelCodeDetail";

/**
 * Off-canvas shell for the intercepted sector route
 * (`app/kbli/@panel/(.)sectors/[id]`).
 *
 * Everything the panel shows about a SECTION — header, strip, the KBLI cards —
 * is server-rendered and arrives through `children`/`grid`, produced by the
 * very same `kbli-data` functions the full page at `/kbli/sectors/[id]` uses.
 * That is the point of the intercepting-route approach: no second data path, so
 * the panel cannot disagree with the page about PMA/risk/provenance disclosure.
 *
 * The CODE drill-down is the one part that must be client-side, and not by
 * preference. `/kbli/sectors/[id]` is statically prerendered (22 SSG pages we
 * are not willing to give up), and a prerendered route serves the same output
 * for every query string: measured on a production build, a soft navigation to
 * `?code=01111` does issue the RSC request and does come back without the
 * drill-down. `export const dynamic = "force-dynamic"` on this slot does not
 * change that either — also measured. So the drill-down renders here, from
 * `details` the server projected with `toPanelDetail`, and the URL is updated
 * with the History API rather than by asking the server for a render it cannot
 * give. In dev everything is dynamic, which is exactly why this only shows up
 * in a built app.
 *
 * Radix Dialog supplies, and we deliberately do not re-implement: focus trap,
 * Esc, overlay click, and body scroll lock.
 *
 * Focus RESTORE is ours. Radix returns focus to whatever was focused when the
 * dialog mounted, and here that is not the card: the panel mounts a tick after
 * the route change, by which time the page's own search field has taken focus
 * (KBLISearch autoFocus). Measured, then handled — `onCloseAutoFocus` puts
 * focus back on the sector card for the section the panel is showing, which is
 * also the right target after the strip has moved the user from A to G.
 *
 * The z-indices clear the two highest stacking neighbours this app has:
 * NavShell (`zIndex: 300`) and CommandPalette (400, measured 2026-09-02). A
 * modal that leaves the site nav clickable above its scrim is not modal, and at
 * z-70 the nav did paint over the panel header on the built page. 500/510
 * clears both rather than tying 400 and losing to DOM order. There is no
 * central z-index scale in this codebase; this comment is the closest thing to
 * one for these three components.
 *
 * Closing is a history operation, not local state: the intercepted URL is
 * popped so the browser Back button and the X button do the same thing. HOW
 * MANY entries to pop is not a constant: the panel pushes one when it opens,
 * one more for every section hop through the strip, and one more for a
 * drill-down. Counting the drill-down alone — which is what this component did
 * until a close after one strip hop was measured landing on the PREVIOUS
 * sector URL with the panel still open — leaves the visitor inside the panel,
 * one section back, with no exit but one Escape per hop they made.
 *
 * The count is carried by the history entries themselves, not by a bare
 * counter: every entry the panel creates is tagged with the depth it sits at,
 * so Back and Forward restore the right number instead of drifting. A counter
 * that only ever increments would over-pop after a Back and drop the visitor
 * out of /kbli entirely — exactly what the guard inside `close` prevents for
 * the double-close case.
 */

/** Kept in sync with the .kbli-panel-* exit animations in styles/kbli-theme.css. */
const EXIT_MS = 200;

function codeFromLocation(): string | null {
  if (typeof window === "undefined") return null;
  const code = new URL(window.location.href).searchParams.get("code");
  return code && /^\d{5}$/.test(code) ? code : null;
}

/**
 * Marker written on every history entry the panel creates: how many entries to
 * pop from THAT entry to leave the panel, and the href it was written for.
 * Next.js re-attaches its own internal state on top of whatever we pass to
 * pushState/replaceState (`copyNextJsInternalHistoryState`), so carrying this
 * extra key does not disturb the router.
 *
 * Two things about a section hop were MEASURED in a browser (next 16.3.5, dev),
 * and both rule out the obvious implementations:
 *
 *   1. the component REMOUNTS — a fresh instance, so an instance ref cannot
 *      carry the count across the hop;
 *   2. the pushed entry arrives with NO custom history state — a router
 *      navigation does not carry the previous entry's marker forward, so the
 *      count cannot be read off the entry we came from either.
 *
 * What DOES survive a remount is module scope, and the one moment where the
 * old depth and the destination are both known is the click itself, while the
 * panel that is about to be replaced is still mounted. So a hop hands its
 * depth over in `pendingHop`, tagged with the href it is for, and the marker
 * on each entry is what makes Back and Forward restore the right number
 * instead of drifting.
 */
const PANEL_MARK_KEY = "kbliPanel";

type PanelMark = { depth: number; href: string };

/**
 * Set by the click that starts a section hop, consumed by the instance that
 * mounts on arrival. Module scope, because the instance that knows the current
 * depth is gone by then. Never read for any href other than the one it names.
 */
let pendingHop: PanelMark | null = null;

const SECTOR_HREF = /^\/kbli\/sectors\/[^/]+$/;

function hereHref(): string {
  return window.location.pathname + window.location.search;
}

function readMark(): PanelMark | null {
  if (typeof window === "undefined") return null;
  const raw = (window.history.state as Record<string, unknown> | null)?.[
    PANEL_MARK_KEY
  ];
  if (!raw || typeof raw !== "object") return null;
  const { depth, href } = raw as Partial<PanelMark>;
  if (typeof depth !== "number" || depth < 1) return null;
  if (typeof href !== "string") return null;
  return { depth, href };
}

export function KBLISectorOffcanvas({
  title,
  sectionId,
  details,
  grid,
  children,
}: {
  /** Accessible name for the dialog, e.g. "Section A — Agriculture, Forestry & Fishing". */
  title: string;
  /** Section currently shown — the card to hand focus back to on close. */
  sectionId: string;
  /** Drill-down projections for every code in this section, keyed by code. */
  details: Record<string, KBLIPanelDetail>;
  /** Server-rendered card grid, shown when no drill-down is open. */
  grid: React.ReactNode;
  /** Server-rendered header + section strip. */
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(true);
  const [activeCode, setActiveCode] = useState<string | null>(null);
  const closing = useRef(false);
  /** Entries to pop to leave the panel from where we stand. */
  const depth = useRef(0);

  // Back/Forward inside the panel: the drill-down pushed a history entry, so
  // popstate is what tells us the user left (or re-entered) it — and the entry
  // we landed on carries the pop depth that belongs to it.
  useEffect(() => {
    const onPop = () => {
      setActiveCode(codeFromLocation());
      const mark = readMark();
      if (mark && mark.href === hereHref()) depth.current = mark.depth;
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // A section swap through the strip re-renders this component with a new
  // sectionId; any open drill-down belongs to the section we just left, and
  // the hop is one more entry between the visitor and /kbli. Whether this
  // entry is one we tagged before (Back/Forward — its own depth wins) or a
  // fresh push carrying an inherited marker (one deeper than the entry we came
  // from) is decided by the href on the marker, never by a counter.
  useEffect(() => {
    setActiveCode(null);
    const mark = readMark();
    const here = hereHref();
    if (mark && mark.href === here) {
      depth.current = mark.depth;
      return;
    }
    depth.current = (pendingHop?.href === here ? pendingHop.depth : 0) + 1;
    pendingHop = null;
    window.history.replaceState(
      {
        ...window.history.state,
        [PANEL_MARK_KEY]: { depth: depth.current, href: here },
      },
      "",
    );
  }, [sectionId]);

  const close = useCallback(() => {
    // A second close (X then Esc, or a double click) must not pop two history
    // entries — that would drop the user out of /kbli entirely.
    if (closing.current) return;
    closing.current = true;
    pendingHop = null;
    setOpen(false);

    // Never 0: if no effect has run yet there is still the entry that opened
    // the panel.
    const steps = Math.max(1, depth.current);
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    window.setTimeout(
      () => (steps === 1 ? router.back() : window.history.go(-steps)),
      reduced ? 0 : EXIT_MS,
    );
  }, [router]);

  /**
   * The page underneath never unmounted, so its card is already in the DOM.
   * If it is not there (a viewport or view where that card is not rendered),
   * fall through to Radix's own restore rather than dropping focus to body.
   */
  const restoreFocus = useCallback(
    (event: Event) => {
      const card = document.querySelector<HTMLElement>(
        `a[href="/kbli/sectors/${sectionId}"]`,
      );
      if (!card) return;
      event.preventDefault();
      card.focus();
    },
    [sectionId],
  );

  /**
   * Cards keep their canonical `/kbli/<code>` href — untouched, so a
   * middle-click, a cmd-click, "open in new tab" and a JS-less browser all
   * still reach the real page. Only a plain left click is taken over.
   *
   * CAPTURE phase, not bubble: next/link binds its own handler to the anchor,
   * which is deeper in the tree, so a bubbling listener here would run after
   * the router had already started navigating and preventDefault would arrive
   * too late. Measured — the bubble version navigated away.
   */
  const onGridClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
        return;

      const anchor = (event.target as HTMLElement).closest("a");
      const href = anchor?.getAttribute("href");
      const code = href?.match(/^\/kbli\/(\d{5})$/)?.[1];
      if (!code || !details[code]) return;

      event.preventDefault();
      const codeHref = `${window.location.pathname}?code=${code}`;
      depth.current += 1;
      window.history.pushState(
        { [PANEL_MARK_KEY]: { depth: depth.current, href: codeHref } },
        "",
        codeHref,
      );
      setActiveCode(code);
    },
    [details],
  );

  /**
   * A section hop is a plain `<Link>` — deliberately, so the strip keeps
   * working with JS off and in a new tab. That also means the panel learns
   * about the hop only after it has already happened, in a fresh instance and
   * on an entry with no state. This capture handler is the one place where the
   * depth being left behind and the URL being navigated to are both known, so
   * it hands them over.
   *
   * It observes every hop and takes over exactly one click: the strip letter
   * of the section already open (`aria-current="page"`). That click is not a
   * hop, and letting the router run it was MEASURED to break the count two
   * ways: to the same URL the router replaces the entry and drops its marker
   * (hop B, click B, hop C, Back, Escape landed on /kbli/sectors/A with the
   * panel open), and from a drill-down it pushes an entry nobody counted
   * (drill, click the letter, Escape landed on /kbli/sectors/A with no panel).
   * So on the grid it does nothing, and from a drill-down it is the same
   * history step as the in-panel back control — both end on that section's
   * URL, which is where the letter points.
   *
   * A modified click (new tab), a middle click or a hard `<a>` such as "open as
   * full page" leaves this page entirely, and the note it would leave behind
   * is discarded by the href check on the other side.
   */
  const notePendingHop = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
        return;
      const anchor = (event.target as HTMLElement).closest("a");
      const href = anchor?.getAttribute("href");
      if (!href || !SECTOR_HREF.test(href)) return;
      if (
        anchor?.getAttribute("aria-current") === "page" &&
        href === window.location.pathname
      ) {
        event.preventDefault();
        if (codeFromLocation()) window.history.back();
        return;
      }
      pendingHop = { depth: depth.current, href };
    },
    [],
  );

  const backToGrid = useCallback(() => window.history.back(), []);

  const detail = activeCode ? details[activeCode] : undefined;

  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && close()}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="kbli-panel-overlay fixed inset-0 z-[500] bg-black/70 backdrop-blur-sm"
          data-testid="kbli-sector-panel-overlay"
        />
        <Dialog.Content
          data-testid="kbli-sector-panel"
          // Radix names the dialog through the sr-only Dialog.Title
          // (aria-labelledby). It does NOT emit aria-modal in this version —
          // measured, not assumed — so it is set here explicitly.
          aria-modal="true"
          onCloseAutoFocus={restoreFocus}
          onClickCapture={notePendingHop}
          className="kbli-panel-content fixed z-[510] flex flex-col overflow-hidden
                     border-white/[0.08] bg-[#141416]/95 backdrop-blur-2xl
                     shadow-[0_10px_60px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.04)]
                     inset-x-0 bottom-0 top-16 rounded-t-3xl border-t
                     sm:inset-y-0 sm:left-auto sm:right-0 sm:top-0 sm:w-[600px] sm:max-w-[92vw]
                     sm:rounded-none sm:rounded-l-3xl sm:border-l sm:border-t-0"
        >
          {/* Radix requires a Title for the accessible name; the visible header
              lives in `children` (a Server Component), so this one is
              screen-reader only and the visible one is not duplicated. */}
          <Dialog.Title className="sr-only">{title}</Dialog.Title>

          <Dialog.Close
            aria-label="Close sector panel"
            className="absolute right-4 top-4 z-10 rounded-full border border-white/[0.08]
                       bg-white/[0.04] p-2 text-zinc-400 backdrop-blur-md transition-all
                       hover:bg-white/[0.10] hover:text-white
                       focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--kbli-accent)]"
          >
            <X size={16} />
          </Dialog.Close>

          {children}

          {detail ? (
            <KBLIPanelCodeDetail
              detail={detail}
              sectionId={sectionId}
              onBack={backToGrid}
            />
          ) : (
            <div
              onClickCapture={onGridClick}
              className="@container min-h-0 flex-1 overflow-y-auto px-5 py-5"
              data-testid="kbli-panel-code-grid"
            >
              {grid}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

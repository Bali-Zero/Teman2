"use client";

import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";
import {
  browserAnalyticsConsumer, contactSourcePage, directHandoffHref,
  measureLeadHandoff, navigateToHandoff, requestLeadHandoff, type ContactTopic,
} from "../lib/destinations/lead-handoff";

export interface ContactHandoffProps {
  topic: ContactTopic;
  sourcePage?: string;
  /** Must be set only by a real consent control; omitted means no measurement. */
  analyticsConsent?: boolean;
  className?: string;
  children: ReactNode;
}

export function ContactHandoff({
  topic, sourcePage = "/contact", analyticsConsent = false, className, children,
}: ContactHandoffProps) {
  const pendingRef = useRef(false);
  const [pending, setPending] = useState(false);
  const request = { topic, sourcePage: contactSourcePage(sourcePage) };
  const href = directHandoffHref(request);

  useEffect(() => {
    const restore = (event: PageTransitionEvent): void => {
      if (event.persisted) { pendingRef.current = false; setPending(false); }
    };
    window.addEventListener("pageshow", restore);
    return () => window.removeEventListener("pageshow", restore);
  }, []);

  async function handleClick(event: MouseEvent<HTMLAnchorElement>): Promise<void> {
    // Keep native new-tab/window actions on the always-available direct link.
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    const outcome = await requestLeadHandoff(request);
    measureLeadHandoff({ ...request, captured: outcome.captured }, analyticsConsent, browserAnalyticsConsumer());
    navigateToHandoff(outcome.href);
  }

  return <a href={href} className={className} onClick={handleClick}
    aria-busy={pending} data-lead-source="cta_handoff">{children}</a>;
}

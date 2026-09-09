import type { ReactNode } from "react";
import { SiteHeader } from "./Entry";
import { Footer } from "./Footer";
import styles from "./SiteShell.module.css";

/** Shared orientation; each journey keeps its own semantic main and composition. */
export function SiteShell({ children, mainId = "main-content", context, className = "" }: {
  children: ReactNode;
  mainId?: string;
  context?: { label: string; href: string };
  className?: string;
}) {
  return <div className={`${styles.shell} ${className}`}>
    <a className={styles.skip} href={`#${mainId}`}>Skip to content</a>
    <SiteHeader />
    {context ? <nav className={styles.context} aria-label="Journey navigation"><a href={context.href}>← {context.label}</a></nav> : null}
    {children}
    <Footer />
  </div>;
}

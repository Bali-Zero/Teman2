"use client";

import styles from "./PageRecovery.module.css";

export function PageRecovery({ retry }: { retry: () => void }) {
  return <div className={styles.page}>
    <header><a href="/" aria-label="Bali Zero home"><img src="/assets/logo.png" alt="Bali Zero" width="62" height="62" /></a></header>
    <main>
      <p className={styles.label}>Bali Zero · A moment to reconnect</p>
      <h1>This page needs<br />another moment.</h1>
      <p>We couldn’t finish loading it. Try again, or continue through our services.</p>
      <nav aria-label="Page recovery"><button type="button" onClick={retry}>Try again</button><a href="/services">Explore services <span aria-hidden="true">↗</span></a></nav>
      <a className={styles.contact} href="/contact">Need help with your plans? Contact the team.</a>
    </main>
  </div>;
}

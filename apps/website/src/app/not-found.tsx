import Link from "next/link";
import { ButtonLink, Container } from "../components/ui";
import styles from "./not-found.module.css";
import "../styles/brand-fonts.css";

export default function NotFound() {
  return (
    <div className={styles.pageTheme}>
      <a className="skip" href="#main">Skip to content</a>
      <header className={styles.header}>
        <Link href="/" aria-label="Bali Zero home">
          <img src="/assets/logo.png" alt="Bali Zero" width="62" height="62" />
        </Link>
      </header>
      <Container as="main" id="main" tabIndex={-1} className={styles.main}>
        <div className={styles.content}>
          <span className={styles.eyebrow}>404 · Bali Zero</span>
          <h1>Page not found.</h1>
          <p>This address doesn’t lead to a page. Return home or explore our services.</p>
          <nav className={styles.actions} aria-label="Page recovery">
            <ButtonLink href="/">Back to home</ButtonLink>
            <ButtonLink href="/services" variant="secondary">Explore services</ButtonLink>
          </nav>
        </div>
      </Container>
    </div>
  );
}

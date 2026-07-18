import Link from "next/link";

type MagazineShellProps = Readonly<{
  children: React.ReactNode;
  eyebrow?: string;
}>;

export function MagazineShell({
  children,
  eyebrow = "Bali Zero intelligence",
}: MagazineShellProps) {
  return (
    <>
      <a className="skip-link" href="#magazine-content">
        Skip to the edition
      </a>
      <header className="masthead">
        <div className="masthead-kicker">{eyebrow}</div>
        <div className="masthead-row">
          <Link
            className="wordmark"
            href="/"
            aria-label="Bali Zero Magazine home"
          >
            <span>Bali Zero</span>
            <strong>Magazine</strong>
          </Link>
          <nav aria-label="Magazine sections">
            <Link href="/">Magazine</Link>
            <span aria-disabled="true">Research</span>
            <span aria-disabled="true">Operations</span>
          </nav>
        </div>
      </header>
      <main id="magazine-content">{children}</main>
      <footer className="magazine-footer">
        <span>Bali Zero Magazine</span>
        <span>Workspace edition · verified intelligence only</span>
      </footer>
    </>
  );
}

export function WorkspaceAccessRequired() {
  return (
    <section className="access-state" aria-labelledby="access-title">
      <p className="section-label">Protected workspace</p>
      <h1 id="access-title">Workspace access required</h1>
      <p>
        This private edition is available only to authenticated Bali Zero
        readers.
      </p>
    </section>
  );
}

import { KbliShell, CodeCard } from "../../features/kbli/KbliPages";
import { Explorer } from "../../features/kbli/Explorer";
import {
  getCode,
  publicItem,
  first,
  type SearchParams,
} from "../../features/kbli/catalog.server";
import { kbliBackendOrigin } from "../../features/kbli/explorer.server";
import styles from "../../features/kbli/kbli.module.css";
export const dynamic = "force-dynamic";
export const metadata = { title: "KBLI Explorer | Bali Zero" };
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const inspect = first((await searchParams).inspect);
  const code = /^\d{5}$/.test(inspect) ? getCode(inspect) : undefined;
  return (
    <KbliShell active="explorer">
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>The KBLI Explorer</span>
          <h1>
            Make sense of
            <br />
            your next activity.
          </h1>
          <p className={styles.intro}>
            Ask about the classification, inspect an activity and follow the
            evidence. Use the detailed record to check ownership, scale and
            licensing together.
          </p>
        </div>
        <aside className={styles.heroNote}>
          <a href="/kbli" className={styles.textLink}>
            Search the directory →
          </a>
          <p>
            Every activity has a source-backed record. Start there, then explore
            the questions around it.
          </p>
        </aside>
      </header>
      <div className={styles.explorerLayout}>
        <Explorer
          available={Boolean(kbliBackendOrigin())}
          initialCode={code?.code}
        />
        <aside className={styles.explorerAside}>
          <section className={styles.inspection}>
            <span className={styles.eyebrow}>Inspect an activity</span>
            <form action="/kbli-explorer" className={styles.searchForm}>
              <label htmlFor="inspect-code">
                Five-digit KBLI code
                <input
                  name="inspect"
                  id="inspect-code"
                  pattern="[0-9]{5}"
                  inputMode="numeric"
                  maxLength={5}
                  required
                  defaultValue={inspect}
                  placeholder="Enter a code"
                />
              </label>
              <button className={styles.secondary} type="submit">
                Open activity →
              </button>
            </form>
            {inspect && !code && (
              <p role="status">
                No current record was found for this code. Search by activity
                name or review its classification history.
              </p>
            )}
            {code && <CodeCard item={publicItem(code)} />}
          </section>
          <h2>A few useful terms.</h2>
          <dl className={styles.glossary}>
            <dt>KBLI</dt>
            <dd>
              Indonesia’s classification of business activities. The five-digit
              code identifies a specific activity.
            </dd>
            <dt>PT PMA</dt>
            <dd>
              A foreign investment company. Read the verified ownership
              disclosure separately from the licensing rows.
            </dd>
            <dt>Scope & scale</dt>
            <dd>
              The declared activity and business scale used when reading a
              licensing requirement.
            </dd>
            <dt>Source history</dt>
            <dd>
              A code’s predecessor mapping and the origin of its licensing text
              are separate checks.
            </dd>
          </dl>
          <div className={styles.actions}>
            <a className={styles.textLink} href="/kbli/builder">
              Compare my shortlist →
            </a>
            <a className={styles.textLink} href="/contact?topic=company">
              Review with Bali Zero →
            </a>
          </div>
        </aside>
      </div>
    </KbliShell>
  );
}

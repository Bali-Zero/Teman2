import styles from "./Portal.module.css";

const capabilities = [
  { title: "Documents", description: "Find the passport, visa, company and tax records shared with your account." },
  { title: "Applications", description: "View application progress, document requests and the next steps linked to your case." },
  { title: "Conversations", description: "Continue conversations with your Bali Zero team in the context of your case." },
];

export function Portal() {
  return (
    <section id="client-portal" aria-labelledby="portal-title" className={styles.portal}>
      <div className={styles.opening}>
        <span className={styles.eyebrow}>My Bali Zero · For existing clients</span>
        <h2 id="portal-title">Your case.<br /><em>Connected.</em></h2>
        <p>Open your existing client account to view your documents, application progress and conversations with the team.</p>
        <a className={styles.signIn} href="https://my.balizero.com/" target="_blank" rel="noopener noreferrer">Sign in to My Bali Zero <span aria-hidden="true">↗</span></a>
        <p className={styles.note}>Have your account sign-in details ready. Opens My Bali Zero in a new tab.</p>
      </div>
      <div className={styles.contents}>
        <dl>{capabilities.map(({title,description}, index) => <div key={title}><dt><span aria-hidden="true">0{index + 1}</span>{title}</dt><dd>{description}</dd></div>)}</dl>
        <p className={styles.permissions}>Available records and actions depend on your account and permissions.</p>
        <a className={styles.help} href="/contact?topic=portal&from=home">Need access or help with your account?<span>Contact the team <span aria-hidden="true">→</span></span></a>
      </div>
    </section>
  );
}

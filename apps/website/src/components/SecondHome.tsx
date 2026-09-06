import type { CSSProperties } from "react";
export function SecondHome() {
  return (
    <section
      aria-labelledby="studio-title"
      className="second-home wrap"
      id="second-home-studio"
    >
      <div className="studio-topline">
        <span className="eyebrow">{"Second Home Studio"}</span>
        <span>{"A little room for a bigger life."}</span>
      </div>
      <div className="studio-grid">
        <div className="studio-visual">
          <img
            alt="An open book unfolds into a Balinese doorway, garden and terraces: a new chapter taking shape."
            height="1086"
            loading="lazy"
            src="/assets/second-home-book.png"
            width="1448"
          />
          <span className="studio-art-caption">
            {"Every new chapter starts with a possibility."}
          </span>
        </div>
        <div className="studio-copy">
          <h2 id="studio-title">
            {"A new chapter."}
            <br />
            <em>{"On your terms."}</em>
          </h2>
          <p className="studio-lead">
            {
              "Picture your life in Indonesia. Then explore how a Second Home plan could take shape."
            }
          </p>

          <p aria-live="polite" className="studio-thought" id="studio-thought">
            {
              "A slower morning. A different rhythm. Start with the life you have in mind."
            }
          </p>
          <a
            className="button studio-open"
            href="https://balizero.com/visa/second-home/studio"
          >
            {"Open Second Home Studio "}
            <span aria-hidden="true">{"↗"}</span>
          </a>
          <p className="studio-note">{"Explore your fit. Build your plan."}</p>
          <a
            aria-label="Contact our team about Ari’s Second Home Studio project"
            className="project-host host-ari"
            href="https://wa.me/628213454721?text=Hello%20Bali%20Zero%2C%20I%20would%20like%20to%20discuss%20Second%20Home%20Studio%20with%20Ari."
          >
            <span className="host-portrait">
              <img alt="Ari" loading="lazy" src="/assets/ari-cutout-v19.png" />
            </span>
            <span className="host-copy">
              <span className="host-label">
                {"A familiar face for a new chapter"}
              </span>
              <strong>
                {"Ari "}
                <span>{"· Second Home Studio"}</span>
              </strong>
              <span className="host-contact">
                {"Talk through your plans "}
                <span aria-hidden="true">{"↗"}</span>
              </span>
            </span>
          </a>
        </div>
      </div>
    </section>
  );
}

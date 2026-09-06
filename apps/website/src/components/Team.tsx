import type { CSSProperties } from "react";
export function Team() {
  return (
    <section className="team-new" id="team">
      <div className="wrap">
        <div className="team-intro">
          <span className="eyebrow">{"The people behind Bali Zero"}</span>
          <span className="small">{"Bali, Indonesia · Since 2020"}</span>
        </div>
        <div className="founders-feature">
          <div className="founder-pair">
            <figure>
              <img
                alt="Zainal Abidin, Bali Zero founder"
                loading="lazy"
                src="/assets/zainal-ceo.jpg"
              />
              <figcaption>
                <strong>{"Zainal Abidin"}</strong>
                <span>{"Chief Executive Officer · Founder"}</span>
              </figcaption>
            </figure>
            <figure>
              <img
                alt="Pak Heru, Bali Zero founder"
                loading="lazy"
                src="/assets/heru-komisaris.jpg"
              />
              <figcaption>
                <strong>{"Pak Heru"}</strong>
                <span>{"Komisaris · Founder"}</span>
              </figcaption>
            </figure>
          </div>
          <div className="founders-copy">
            <span className="eyebrow">
              {"Local roots. Personal commitment."}
            </span>
            <h2>
              {"Good advice starts"}
              <br />
              {"with people."}
            </h2>
            <p>
              {
                "A local team, a personal conversation. Meet the people who help you understand your options and take your next step in Indonesia."
              }
            </p>
            <a
              className="button light"
              href="https://balizero.com/v2/company/about"
            >
              {"Get to know Bali Zero "}
              <span aria-hidden="true">{"↗"}</span>
            </a>
            <div className="leadership-note">
              <img alt="Ruslana" loading="lazy" src="/assets/ruslana.jpg" />
              <div>
                <strong>{"Ruslana"}</strong>
                <span>{"Board Member"}</span>
              </div>
            </div>
          </div>
        </div>
        <div className="team-directory-head">
          <div>
            <span className="eyebrow">{"The people you can turn to"}</span>
            <h3>{"Different talents. One team."}</h3>
          </div>
          <a className="textlink" href="https://balizero.com/team">
            {"Meet the whole team ↗"}
          </a>
        </div>
        <div className="team-directory team-gallery">
          <article className="team-person">
            <a
              aria-label="Meet Veronika and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  { "--atlas-x": "-100%", "--atlas-y": "0%" } as CSSProperties
                }
              >
                <img
                  alt="Veronika"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Veronika"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Tax Manager"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Dewa Ayu and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  { "--atlas-x": "-200%", "--atlas-y": "0%" } as CSSProperties
                }
              >
                <img
                  alt="Dewa Ayu"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Dewa Ayu"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Tax Consultant"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Krisna and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  { "--atlas-x": "-300%", "--atlas-y": "0%" } as CSSProperties
                }
              >
                <img
                  alt="Krisna"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Krisna"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Setup Team"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Ari and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  { "--atlas-x": "0%", "--atlas-y": "-100%" } as CSSProperties
                }
              >
                <img
                  alt="Ari"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Ari"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Second Home Studio"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Subhi and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  {
                    "--atlas-x": "-300%",
                    "--atlas-y": "-100%",
                  } as CSSProperties
                }
              >
                <img
                  alt="Subhi"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Subhi"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Zantara · AI"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Adit and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  { "--atlas-x": "0%", "--atlas-y": "-200%" } as CSSProperties
                }
              >
                <img
                  alt="Adit"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Adit"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Supervisor · Lead Setup"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Angel and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  {
                    "--atlas-x": "-100%",
                    "--atlas-y": "-200%",
                  } as CSSProperties
                }
              >
                <img
                  alt="Angel"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Angel"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Tax Lead"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Candra and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  {
                    "--atlas-x": "-200%",
                    "--atlas-y": "-200%",
                  } as CSSProperties
                }
              >
                <img
                  alt="Candra"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Candra"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Advisor · Ulu Team"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Vino and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  {
                    "--atlas-x": "-300%",
                    "--atlas-y": "-200%",
                  } as CSSProperties
                }
              >
                <img
                  alt="Vino"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Vino"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Setup Team"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Asya and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  { "--atlas-x": "0%", "--atlas-y": "-300%" } as CSSProperties
                }
              >
                <img
                  alt="Asya"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Asya"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Accounting"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Surya and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  {
                    "--atlas-x": "-100%",
                    "--atlas-y": "-300%",
                  } as CSSProperties
                }
              >
                <img
                  alt="Surya"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Surya"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"E-VOA"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Damar and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  {
                    "--atlas-x": "-200%",
                    "--atlas-y": "-300%",
                  } as CSSProperties
                }
              >
                <img
                  alt="Damar"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Damar"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Setup Team"}</p>
              </div>
            </a>
          </article>
          <article className="team-person">
            <a
              aria-label="Meet Dea and the Bali Zero team"
              href="https://balizero.com/team"
            >
              <div
                className="person-art"
                style={
                  {
                    "--atlas-x": "-300%",
                    "--atlas-y": "-300%",
                  } as CSSProperties
                }
              >
                <img
                  alt="Dea"
                  height="1448"
                  loading="lazy"
                  src="/assets/team-ivory-atlas.png"
                  width="1086"
                />
              </div>
              <div className="person-caption">
                <h3>{"Dea"}</h3>
                <span aria-hidden="true">{"↗"}</span>
                <p>{"Advisor · Ulu Team"}</p>
              </div>
            </a>
          </article>
        </div>
        <div className="team-invitation">
          <div>
            <h3>{"Not sure who to speak to?"}</h3>
            <p>
              {"Tell us what you’re planning. We’ll start the conversation."}
            </p>
          </div>
          <a className="button" href="#contact">
            {"Talk to our team "}
            <span aria-hidden="true">{"→"}</span>
          </a>
        </div>
      </div>
    </section>
  );
}

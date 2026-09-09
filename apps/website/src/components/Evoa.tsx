import styles from "./ToolEntries.module.css";
import art from "./HomeTools.module.css";
export function Evoa() {
  return (
    <section className={art.arrival} id="evoa" aria-labelledby="arrival-title">
      <img
        alt="AI photographic study of a Balinese jukung on continuous crystalline sea"
        className={art.panorama}
        loading="lazy"
        src="/assets/evoa-panorama.png"
      />
      <div className={art.arrivalVisual}>
        <span className={art.caption}>
          <span className={art.captionKicker}>{"YOUR NEXT CHAPTER"}</span>
          {"Bali is closer"}
          <br />
          {"than you think."}
        </span>
      </div>
      <div className={art.arrivalCopy}>
        <span className={art.eyebrow}>{"Arriving in Indonesia?"}</span>
        <h2 id="arrival-title">{"E-VOA"}</h2>
        <p className={art.subtitle}>{"Electronic Visa on Arrival"}</p>
        <div className={art.arrivalDetails}>
          <p className={art.arrivalLead}>{"Plan your arrival."}</p>
          <p className={art.small}>
            {
              "Planning a short visit? Start with your nationality and travel plans. The E-VOA service checks the available route and shows the documents, application steps and current fees."
            }
          </p>
        </div>
        <a className={art.primary} href="/visa/voa">
          {"Explore E-VOA "}
          <span aria-hidden="true">{"→"}</span>
        </a>
        <p className={art.small}>
          {"Have your passport and arrival plans ready when you begin an application."}
        </p>
        <div className={`${styles.branches}`} aria-label="Choose your visa starting point">
          <a href="/visa-oracle">Still choosing a visa? Explore your options →</a>
          <a href="/visa/clock">Already in Indonesia? Check your stay dates →</a>
          <a href="/services/immigration">Discuss an extension or renewal →</a>
        </div>
        <a
          aria-label="Contact our team about Surya’s E-VOA project"
          className={art.host}
          href="https://wa.me/628213454721?text=Hello%20Bali%20Zero%2C%20I%20would%20like%20to%20discuss%20E-VOA%20with%20Surya."
        >
          <span className={art.hostPortrait}>
            <img
              alt="Surya"
              loading="lazy"
              src="/assets/surya-cutout-v19.png"
            />
          </span>
          <span className={art.hostCopy}>
            <span className={art.hostLabel}>
              {"The person behind your next step"}
            </span>
            <strong>
              {"Surya "}
              <span>{"· E-VOA"}</span>
            </strong>
            <span className={art.hostContact}>
              {"Questions? Start a conversation "}
              <span aria-hidden="true">{"↗"}</span>
            </span>
          </span>
        </a>
      </div>
    </section>
  );
}

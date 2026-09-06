import type { CSSProperties } from "react";
export function Evoa() {
  return (
    <section className="voa" id="evoa">
      <img
        alt="AI photographic study of a Balinese jukung on continuous crystalline sea"
        className="voa-panorama"
        loading="lazy"
        src="/assets/evoa-panorama.png"
      />
      <div className="voa-visual">
        <span className="caption">
          <span className="caption-kicker">{"YOUR NEXT CHAPTER"}</span>
          {"Bali is closer"}
          <br />
          {"than you think."}
        </span>
      </div>
      <div className="voa-copy">
        <span className="eyebrow">{"Arriving in Indonesia?"}</span>
        <h2>{"E-VOA"}</h2>
        <p className="subtitle">{"Electronic Visa on Arrival"}</p>
        <div className="voa-price-block">
          <span className="eyebrow">{"Your E-VOA, with Bali Zero"}</span>
          <p className="price">{"Plan your arrival."}</p>
          <p className="small">
            {
              "Explore the application steps and current fees in the E-VOA service."
            }
          </p>
        </div>
        <a className="button copper" href="https://balizero.com/visa/voa">
          {"Explore E-VOA "}
          <span aria-hidden="true">{"→"}</span>
        </a>
        <p className="small">
          {"First, check your eligibility. Then follow the application steps."}
        </p>
        <a
          aria-label="Contact our team about Surya’s E-VOA project"
          className="project-host host-surya"
          href="https://wa.me/628213454721?text=Hello%20Bali%20Zero%2C%20I%20would%20like%20to%20discuss%20E-VOA%20with%20Surya."
        >
          <span className="host-portrait">
            <img
              alt="Surya"
              loading="lazy"
              src="/assets/surya-cutout-v19.png"
            />
          </span>
          <span className="host-copy">
            <span className="host-label">
              {"The person behind your next step"}
            </span>
            <strong>
              {"Surya "}
              <span>{"· E-VOA"}</span>
            </strong>
            <span className="host-contact">
              {"Questions? Start a conversation "}
              <span aria-hidden="true">{"↗"}</span>
            </span>
          </span>
        </a>
      </div>
    </section>
  );
}

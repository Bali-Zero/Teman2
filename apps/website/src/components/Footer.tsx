import type { CSSProperties } from "react";
export function Footer() {
  return (
    <footer>
      <div className="wrap">
        <div className="footer-grid">
          <div>
            <a aria-label="Bali Zero home" className="brand" href="#main">
              <img
                alt="Bali Zero"
                height="62"
                src="/assets/logo.png"
                width="62"
              />
            </a>
            <p>{"Bali, Indonesia · Since 2020"}</p>
            <p>{"Local knowledge. A human connection."}</p>
          </div>
          <div className="footer-col">
            <span className="eyebrow">{"Explore"}</span>
            <a href="#tools">{"Our tools"}</a>
            <a href="#services">{"Our services"}</a>
            <a href="#evoa">{"E-VOA"}</a>
            <a href="https://balizero.com/news">{"The Bali Zero Journal"}</a>
          </div>
          <div className="footer-col">
            <span className="eyebrow">{"Bali Zero"}</span>
            <a href="https://balizero.com/v2/company/about">{"Our story"}</a>
            <a href="https://balizero.com/team">{"Our team"}</a>
            <a href="https://maps.app.goo.gl/whiMUTNchcDR5naz8">
              {"Client reviews"}
            </a>
            <a href="https://my.balizero.com/">{"My Bali Zero"}</a>
          </div>
          <div className="footer-col">
            <span className="eyebrow">{"Connect"}</span>
            <a href="https://wa.me/628213454721">{"WhatsApp"}</a>
            <a href="mailto:zantara@balizero.com">{"zantara@balizero.com"}</a>
            <a href="tel:+628213454721">{"+62 821 3454 721"}</a>
            <a href="https://t.me/Balizerobot">{"Zantara on Telegram"}</a>
          </div>
        </div>
        <div className="footer-base">
          <span>{"© 2026 Bali Zero"}</span>
          <div>
            <a href="https://balizero.com/v2/privacy">{"Privacy"}</a>
            <a href="https://balizero.com/v2/terms">{"Terms"}</a>
            <a href="https://balizero.com/v2/cookies">{"Cookies"}</a>
            <span>{"Website development preview"}</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

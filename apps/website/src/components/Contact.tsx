import type { CSSProperties } from "react";
export function Contact() {
  return (
    <section className="contact wrap" id="contact">
      <div>
        <span className="eyebrow">{"A real conversation"}</span>
        <h2 style={{ marginTop: "15px" } as CSSProperties}>
          {"Tell us what"}
          <br />
          {"you’re planning."}
        </h2>
        <p>{"Big decisions or a simple question. Start here."}</p>
      </div>
      <div className="contact-actions">
        <a className="button" href="https://wa.me/628213454721">
          {"Talk to us on WhatsApp ↗"}
        </a>
        <a className="textlink" href="mailto:zantara@balizero.com">
          {"Email our team"}
        </a>
        <a
          className="small"
          href="https://maps.google.com/?q=Bali+Zero+Kerobokan"
        >
          {"Find us in Bali ↗"}
        </a>
      </div>
    </section>
  );
}

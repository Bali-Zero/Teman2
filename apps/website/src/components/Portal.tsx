"use client";
import { useRef, useState, type KeyboardEvent } from "react";
const tabs = ["Documents", "Applications", "Messages"];
export function Portal() {
  const [active, setActive] = useState(0);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const target =
      event.key === "ArrowRight"
        ? (index + 1) % 3
        : event.key === "ArrowLeft"
          ? (index + 2) % 3
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? 2
              : null;
    if (target === null) return;
    event.preventDefault();
    setActive(target);
    buttons.current[target]?.focus();
  }
  return (
    <section
      id="client-portal"
      aria-labelledby="portal-title"
      className="portal wrap portal-r19"
    >
      <div className="portal-copy">
        <span className="eyebrow">{"MY BALI ZERO"}</span>
        <h2 id="portal-title">
          {"Your personal"}
          <br />
          <em>{"client portal."}</em>
        </h2>
        <p>
          {"Find your documents. Follow your applications. Talk to your "}
          <span
            aria-label="Bali Zero"
            className="inline-brand-accessible"
            role="img"
          >
            <span aria-hidden="true" className="inline-brand">
              <img
                alt=""
                className="brand-logo-3-img"
                src="/assets/brand-3.png"
              />
              <span>{"ALI"}</span>
              <span className="brand-zero">
                {"ZER"}
                <span className="brand-om-circle"></span>
              </span>
            </span>
          </span>
          {" team."}
        </p>
        <a
          className="portal-enter"
          href="https://my.balizero.com"
          rel="noopener noreferrer"
          target="_blank"
        >
          <span>{"Sign in to My Bali Zero"}</span>
          <span aria-hidden="true">{"↗"}</span>
        </a>
        <span className="portal-entry-note">
          {"Your account at my.balizero.com"}
        </span>
      </div>
      <div className="portal-tour">
        <div className="portal-tour-top">
          <span>{"INSIDE MY BALI ZERO"}</span>
          <span className="tour-label">{"Feature preview"}</span>
        </div>
        <div
          className="portal-tabs"
          role="tablist"
          aria-label="Explore My Bali Zero"
        >
          {tabs.map((label, index) => (
            <button
              key={label}
              ref={(node) => {
                buttons.current[index] = node;
              }}
              id={"portal-tab-" + label.toLowerCase()}
              aria-controls={"portal-" + label.toLowerCase()}
              role="tab"
              aria-selected={active === index}
              tabIndex={active === index ? 0 : -1}
              type="button"
              onClick={() => setActive(index)}
              onKeyDown={(event) => onKeyDown(event, index)}
            >
              {label}
            </button>
          ))}
        </div>
        <div
          aria-labelledby="portal-tab-documents"
          className="portal-pane"
          id="portal-documents"
          role="tabpanel"
          hidden={active !== 0}
          tabIndex={0}
        >
          <span className="portal-pane-label">
            {"KEEP EVERYTHING TOGETHER"}
          </span>
          <h3>{"Your document vault."}</h3>
          <p>{"Find the files you need, when you need them."}</p>
          <ul className="portal-file-list">
            <li>
              <span aria-hidden="true" className="portal-file-icon"></span>
              <span>{"Passport & visa"}</span>
            </li>
            <li>
              <span aria-hidden="true" className="portal-file-icon"></span>
              <span>{"Company documents"}</span>
            </li>
            <li>
              <span aria-hidden="true" className="portal-file-icon"></span>
              <span>{"Tax records"}</span>
            </li>
          </ul>
        </div>
        <div
          aria-labelledby="portal-tab-applications"
          className="portal-pane"
          id="portal-applications"
          role="tabpanel"
          hidden={active !== 1}
          tabIndex={0}
        >
          <span className="portal-pane-label">{"KNOW WHAT HAPPENS NEXT"}</span>
          <h3>{"Your applications, in view."}</h3>
          <p>
            {"See where each application stands and what needs your attention."}
          </p>
          <ol className="portal-step-list">
            <li>
              <span aria-hidden="true">{"01"}</span>
              <div>
                <strong>{"Documents"}</strong>
                <span>{"See what is needed for your application."}</span>
              </div>
            </li>
            <li>
              <span aria-hidden="true">{"02"}</span>
              <div>
                <strong>{"Progress"}</strong>
                <span>{"Follow updates from your team."}</span>
              </div>
            </li>
            <li>
              <span aria-hidden="true">{"03"}</span>
              <div>
                <strong>{"Next step"}</strong>
                <span>{"Know what to do next."}</span>
              </div>
            </li>
          </ol>
        </div>
        <div
          aria-labelledby="portal-tab-messages"
          className="portal-pane"
          id="portal-messages"
          role="tabpanel"
          hidden={active !== 2}
          tabIndex={0}
        >
          <span className="portal-pane-label">{"STAY IN TOUCH"}</span>
          <h3>{"Your team, a message away."}</h3>
          <p>
            {"Keep your questions and your team's replies in one conversation."}
          </p>
          <div className="portal-message-example">
            <span aria-hidden="true" className="portal-message-mark">
              {"↗"}
            </span>
            <div>
              <strong>{"Your Bali Zero team"}</strong>
              <span>
                {
                  "Questions about a document or your next step? Continue the conversation here."
                }
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

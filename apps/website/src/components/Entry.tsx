"use client";

import { useId, useRef, useState } from "react";
import "./entry.css";

const navigation = [
  { label: "Explore", href: "#tools" },
  { label: "Services", href: "/services" },
  { label: "Journal", href: "/journal" },
  { label: "Our team", href: "#team" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const menuButton = useRef<HTMLButtonElement>(null);

  return (
    <header
      className="site-header"
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          setOpen(false);
          menuButton.current?.focus();
        }
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <a aria-label="Bali Zero home" className="brand" href="#main">
        <img alt="Bali Zero" height="62" src="/assets/logo.png" width="62" />
      </a>
      <button
        ref={menuButton}
        className="entry-menu-toggle"
        type="button"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        <span>{open ? "Close menu" : "Menu"}</span>
        <span aria-hidden="true">{open ? "−" : "+"}</span>
      </button>
      <nav
        aria-label="Main navigation"
        id={menuId}
        className="entry-navigation"
        data-open={open}
      >
        {navigation.map(({ label, href }) => (
          <a href={href} key={href} onClick={() => setOpen(false)}>
            {label}
          </a>
        ))}
        <a
          aria-label="My account"
          className="account"
          href="https://my.balizero.com/"
          onClick={() => setOpen(false)}
        >
          <span aria-hidden="true" className="account-my">
            My
          </span>
          <span aria-hidden="true" className="account-brand">
            <img
              alt=""
              className="brand-logo-3-img"
              src="/assets/brand-3.png"
            />
            <span>ALI</span>
            <span className="brand-zero">
              ZER
              <span className="brand-om-circle" />
            </span>
          </span>
          <span aria-hidden="true" className="account-arrow">
            ↗
          </span>
        </a>
      </nav>
    </header>
  );
}

const categories = [
  { label: "Visas & residence", href: "/services/immigration" },
  { label: "Business & company", href: "/services/company-setup" },
  { label: "Tax", href: "/services/tax" },
  { label: "Property", href: "/services/property" },
];

export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="hero entry-hero">
      <img
        alt="Sunset illustration of traditional Balinese artisans beside a river, connected by a bridge to a futuristic cultural design atelier"
        fetchPriority="high"
        src="/assets/hero-sunset-future.png"
      />
      <div className="hero-copy">
        <span className="eyebrow">Bali · Indonesia</span>
        <h1 id="hero-title">
          What’s your next step
          <br />
          in Indonesia?
        </h1>
        <p>
          Consultancy for immigration, company setup, tax and property in
          Indonesia.
        </p>
        <div className="entry-starting-points">
          <span className="entry-category-label" id="entry-category-label">
            Choose where to start
          </span>
          <ul
            aria-labelledby="entry-category-label"
            className="entry-categories"
          >
            {categories.map(({ label, href }) => (
              <li key={href}>
                <a href={href}>
                  {label}
                  <span aria-hidden="true">→</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
        <a className="human" href="#contact">
          Talk to our team
        </a>
      </div>
      <span className="hero-caption">
        TRADITION, TOMORROW · AI ILLUSTRATION
      </span>
    </section>
  );
}

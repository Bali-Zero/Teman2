"use client";

import { useEffect, useId, useRef, useState } from "react";

const navigation = [
  { label: "Explore", href: "/#tools" },
  { label: "Services", href: "/services" },
  { label: "Journal", href: "/news" },
  { label: "Our story", href: "/v2/company/about" },
  { label: "Our team", href: "/team" },
  { label: "Contact", href: "/contact" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 981px)");
    const dismiss = () => {
      if (desktop.matches) setOpen(false);
    };
    desktop.addEventListener("change", dismiss);
    return () => desktop.removeEventListener("change", dismiss);
  }, []);

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
      <a aria-label="Bali Zero home" className="brand" href="/">
        <img
          alt="Bali Zero"
          height="62"
          src="/assets/r19/logo.webp"
          width="62"
        />
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
              src="/assets/r19/brand-3.webp"
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
  { label: "Visas & residence", href: "/services/visa" },
  { label: "Business & company", href: "/services/company" },
  { label: "Tax", href: "/services/tax" },
  { label: "Property", href: "/services/property" },
  { label: "Compliance", href: "/services/compliance" },
];

export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="hero entry-hero">
      <img
        alt="Sunset illustration of traditional Balinese artisans beside a river, connected by a bridge to a futuristic cultural design atelier"
        fetchPriority="high"
        src="/assets/r19/hero-sunset-future.webp"
      />
      <div className="hero-copy">
        <span className="eyebrow">Bali · Indonesia</span>
        <h1 id="hero-title">
          What’s your next step
          <br />
          in Indonesia?
        </h1>
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
      </div>
      <span className="hero-caption">TRADITION, TOMORROW</span>
    </section>
  );
}

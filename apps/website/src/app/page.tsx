import { Suspense } from "react";
import type { Metadata } from "next";
import { SiteHeader, Hero } from "../components/Entry";
import { Services } from "../components/Services";
import { Evoa } from "../components/Evoa";
import { SecondHome } from "../components/SecondHome";
import { Reviews } from "../components/Reviews";
import { Portal } from "../components/Portal";
import { HomeJournal, JournalPending } from "../components/HomeJournal";
import { Team } from "../components/Team";
import { Contact } from "../components/Contact";
import { Footer } from "../components/Footer";

export const metadata: Metadata = {
  title: "Bali Zero Indonesia | Bali Zero",
  description:
    "Immigration, company setup, tax and property guidance for living and doing business in Indonesia.",
  alternates: { canonical: "/" },
};

export default function Home() {
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <SiteHeader />
      <main id="main" tabIndex={-1}>
        <Hero />
        <Services />
        <Reviews />
        <Evoa />
        <SecondHome />
        <Portal />
        <Suspense fallback={<JournalPending />}>
          <HomeJournal />
        </Suspense>
        <Team />
        <Contact />
      </main>
      <Footer />
    </>
  );
}

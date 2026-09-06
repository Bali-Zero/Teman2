import { SiteHeader, Hero } from "../components/Entry";
import { Services } from "../components/Services";
import { Evoa } from "../components/Evoa";
import { SecondHome } from "../components/SecondHome";
import { Reviews } from "../components/Reviews";
import { Portal } from "../components/Portal";
import { Journal } from "../components/Journal";
import { Team } from "../components/Team";
import { Contact } from "../components/Contact";
import { Footer } from "../components/Footer";
export default function Home() {
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <SiteHeader />
      <main id="main">
        <Hero />
        <Services />
        <Evoa />
        <SecondHome />
        <Reviews />
        <Portal />
        <Journal />
        <Team />
        <Contact />
      </main>
      <Footer />
    </>
  );
}

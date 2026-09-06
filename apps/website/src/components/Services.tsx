import { services, contactHref } from "../content/services";
export function Services() {
  return (
    <div className="wrap services-area">
      <section
        id="services"
        aria-labelledby="services-title"
        className="services-intro"
      >
        <span className="eyebrow">Advice, with people behind it</span>
        <h2 id="services-title">A team for your next step.</h2>
        <p>Explore our services, or talk to us about the help you need.</p>
        <a className="textlink" href="/services">
          Explore all services →
        </a>
      </section>
      <section className="tools" id="tools" aria-label="Services and tools">
        {services.map((service, index) => (
          <article key={service.id} id={service.id + "-tool"} className="tool">
            <span className="tool-index" aria-hidden="true">
              {String(index + 1).padStart(2, "0")}
              <span>↗</span>
            </span>
            <span className="eyebrow">{service.title}</span>
            <h3>{service.tool}</h3>
            <div className="tool-art" aria-hidden="true">
              <img
                src={"/assets/" + service.image}
                alt=""
                width="1448"
                height="1086"
                loading="lazy"
              />
            </div>
            <p className="service-description">{service.description}</p>
            <div className="tool-ui">
              <p>{service.detail}</p>
            </div>
            <a className="textlink" href={service.route}>
              Explore {service.title} <span aria-hidden="true">→</span>
            </a>
            <a className="textlink" href={service.href}>
              {service.action} <span aria-hidden="true">↗</span>
            </a>
            <a className="service-contact" href={contactHref(service.title)}>
              Talk to our team <span aria-hidden="true">↗</span>
            </a>
          </article>
        ))}
      </section>
    </div>
  );
}

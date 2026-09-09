"use client";

import { useEffect, useId, useRef, useState } from "react";
import { destinationIntents } from "../../content/destinations";
import type { ServiceDossier } from "../../content/service-dossiers";
import { servicePriceIdentities } from "../../content/service-price-identities";
import { ServicePrice } from "./ServicePrice";
import styles from "./service-sections.module.css";

type CatalogGroup = { title: string; description: string; services: ServiceDossier[] };
export function ServiceCatalog({ groups, title }: { groups: CatalogGroup[]; title: string }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  const searchId = useId();
  const comparisonHeading = useRef<HTMLHeadingElement>(null);
  const compareButton = useRef<HTMLButtonElement>(null);
  const services = groups.flatMap((group) => group.services);
  const needle = query.trim().toLocaleLowerCase();
  const matches = (dossier: ServiceDossier) => !needle || [dossier.name, dossier.explanation].join(" ").toLocaleLowerCase().includes(needle);
  const visibleCount = services.filter(matches).length;
  const chosen = selected.map((id) => services.find((dossier) => dossier.id === id)!);

  useEffect(() => {
    if (comparing) comparisonHeading.current?.focus();
  }, [comparing]);
  useEffect(() => {
    const reveal = () => {
      const id = window.location.hash.slice(1);
      if (!/^(svc-|catalog-)/.test(id)) return;
      const target = document.getElementById(id);
      if (!target) return;
      setQuery("");
      if (target instanceof HTMLDetailsElement) target.open = true;
      const group = target.closest<HTMLDetailsElement>("details[id^='catalog-']");
      if (group) group.open = true;
      requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
    };
    reveal();
    window.addEventListener("hashchange", reveal);
    return () => window.removeEventListener("hashchange", reveal);
  }, []);

  function select(id: string) {
    setComparing(false);
    setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : current.length < 2 ? [...current, id] : current);
  }
  function returnToSelection() {
    setComparing(false);
    requestAnimationFrame(() => compareButton.current?.focus());
  }

  return <>
    <div className={styles.catalogLayout}>
      <aside className={styles.catalogRail}>
        <span className={styles.eyebrow}>In this collection</span>
        <nav className={styles.catalogIndex} aria-label={title + " service groups"}>
          {groups.map((group, index) => <a key={group.title} href={"#catalog-" + (index + 1)} onClick={() => {
            setQuery("");
            const target = document.getElementById("catalog-" + (index + 1));
            if (target instanceof HTMLDetailsElement) target.open = true;
            requestAnimationFrame(() => target?.scrollIntoView({ block: "start" }));
          }}><span className={styles.railNumber}>{String(index + 1).padStart(2, "0")}</span><span>{group.title}</span><span className={styles.railCount}>{group.services.length}</span></a>)}
        </nav>
        <p className={styles.catalogNote}>Service guidance helps you prepare; it does not determine eligibility. Requested periods and application routes need confirmation for your case. Your quote itemises deliverables and third-party costs.</p>
      </aside>
      <div className={styles.catalogMain}>
        <div className={styles.searchBar}>
          <div><label htmlFor={searchId}>Find a service</label><input id={searchId} type="search" value={query} onChange={(event) => { setQuery(event.target.value); if (event.target.value.trim()) document.querySelectorAll<HTMLDetailsElement>("details[id^='catalog-']").forEach((group) => { group.open = true; }); }} placeholder="Search names or situations" /></div>
          <p role="status">{visibleCount} of {services.length} services</p>
          {query && <button type="button" onClick={() => setQuery("")}>Clear search</button>}
        </div>
        {visibleCount === 0 && <div className={styles.emptySearch}><h3>No matching services.</h3><p>Try another name or clear your search to browse the complete collection.</p></div>}
        {selected.length > 0 && <div className={styles.compareTray}>
          <div><span className={styles.eyebrow}>Your comparison · {selected.length}/2</span><p>{chosen.map((dossier) => dossier.name).join(" / ")}</p></div>
          <button ref={compareButton} type="button" disabled={selected.length !== 2} onClick={() => setComparing(true)}>Compare selected ({selected.length})</button>
          <button type="button" onClick={() => { setSelected([]); setComparing(false); }}>Clear selection</button>
        </div>}
        {comparing && chosen.length === 2 && <section className={styles.comparison} aria-labelledby={searchId + "-comparison"}>
          <span className={styles.eyebrow}>Read the differences</span>
          <h3 ref={comparisonHeading} tabIndex={-1} id={searchId + "-comparison"}>Two services, side by side.</h3>
          <p>Compare their stated scope. This comparison does not select a route or determine eligibility.</p>
          <table><caption>Selected service comparison</caption><thead><tr><th scope="col">Consider</th>{chosen.map((dossier) => <th scope="col" key={dossier.id}>{dossier.name}</th>)}</tr></thead><tbody>
            {([ ["Who it helps", "explanation"], ["Key difference", "distinction"], ["Application route", "routeNote"], ["Limits to confirm", "limit"], ["Next step", "next"] ] as const).filter(([, key]) => chosen.some((dossier) => dossier[key])).map(([label, key]) => <tr key={key}><th scope="row">{label}</th>{chosen.map((dossier) => <td key={dossier.id}>{dossier[key] || "Confirm the application route for your case."}</td>)}</tr>)}
          </tbody></table>
          <button type="button" onClick={returnToSelection}>Return to selected services ↑</button>
        </section>}
        <div className={styles.catalog}>
          {groups.map((group, index) => <details key={group.title} id={"catalog-" + (index + 1)} open hidden={!group.services.some(matches)} className={styles.catalogGroup}>
            <summary><span className={styles.number} aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><div><h3 className={styles.groupTitle}>{group.title}</h3><p className={styles.description}>{group.description}</p></div><span className={styles.count}>{group.services.length} {group.services.length === 1 ? "service" : "services"}</span><span className={styles.toggle} aria-hidden="true">+</span></summary>
            <ul className={styles.serviceList}>{group.services.map((dossier) => <li key={dossier.id} id={dossier.id} hidden={!matches(dossier)} className={styles.serviceRow}>
              <article aria-labelledby={dossier.id + "-title"}>
                <div className={styles.rowIntro}>
                  <div><h4 id={dossier.id + "-title"}>{dossier.name}</h4><p className={styles.explanation}>{dossier.explanation}</p></div>
                  <div className={styles.serviceActions}>
                    <span className={styles.feeLabel}>Service fee</span>
                    {servicePriceIdentities[dossier.name] ? <ServicePrice serviceKey={servicePriceIdentities[dossier.name].key} name={dossier.name} /> : <span className={styles.quoteOnly}>Scope-based quotation</span>}
                    <a className={styles.quoteLink} aria-label={"Request a quote for " + dossier.name} href={destinationIntents.whatsapp({ topic: "a quote for " + dossier.name + " (" + dossier.id + "), including scope, preparation and timing" })}>Request a quote <span aria-hidden="true">↗</span></a>
                  </div>
                </div>
                <div className={styles.rowTools}><label className={styles.compareChoice}><input type="checkbox" checked={selected.includes(dossier.id)} disabled={selected.length === 2 && !selected.includes(dossier.id)} onChange={() => select(dossier.id)} aria-label={"Compare " + dossier.name} />Compare</label></div>
                <details className={styles.dossier}>
                  <summary aria-label={"Scope and preparation for " + dossier.name}>Scope & preparation <span className={styles.toggle} aria-hidden="true">+</span></summary>
                  <div className={styles.dossierBody}>
                    <div className={styles.distinction}><span className={styles.dossierLabel}>The dossier</span><h5>What makes this different</h5><p>{dossier.distinction}</p>{dossier.routeNote && <p>{dossier.routeNote}</p>}</div>
                    <div className={styles.dossierReading}>
                      <div className={styles.dossierColumns}><div><h5>Work to include in your scope</h5><ul>{dossier.scope.map((item) => <li key={item}>{item}</li>)}</ul></div><div><h5>Have these ready</h5><ul>{dossier.preparation.map((item) => <li key={item}>{item}</li>)}</ul></div></div>
                      <div className={styles.boundary}><h5>Limits & points to confirm</h5><p>{dossier.limit}</p></div>
                      <div className={styles.nextStep}><h5>Your next step</h5><p>{dossier.next}</p>{dossier.guide && <a aria-label={dossier.guide.label + " for " + dossier.name} href={dossier.guide.href}>{dossier.guide.label} <span aria-hidden="true">↗</span></a>}</div>
                      {dossier.reference && <p className={styles.reference}><a href={dossier.reference.url}>{dossier.reference.label}</a><span>Reference checked <time dateTime={dossier.reference.checkedOn}>{dossier.reference.checkedOn}</time>. Scope is confirmed separately.</span></p>}
                      <button type="button" className={styles.returnLink} onClick={(event) => { const details = event.currentTarget.closest("details")!; details.open = false; details.querySelector("summary")?.focus(); }}>Close dossier & return to service ↑</button>
                    </div>
                  </div>
                </details>
              </article>
            </li>)}</ul>
          </details>)}
        </div>
      </div>
    </div>
  </>;
}

"use client";
import { publishedEditionHref } from "../../lib/retained-routes";
import { useId, useRef, useState } from "react";
import type { Data } from "./article-model";
import { checklistData, decisionData, label, type CheckItem, type DecisionData } from "./interaction-data";
import { buildWhatsAppIntent } from "../../lib/destinations/intents";
import styles from "./ArticleInteraction.module.css";

export function ArticleInteraction({ name, props, articleTitle, articleUrl }: { name: string; props: Record<string, Data>; articleTitle: string; articleUrl: string }) {
  const title = label(props.title) || (name === "Checklist" ? "Checklist" : "Decision guide");
  const description = label(props.subtitle) || label(props.description);
  if (name === "Checklist") {
    const items = checklistData(props);
    if (items) return <Checklist key={JSON.stringify(items)} title={title} description={description} items={items} />;
  }
  if (name === "DecisionTree") {
    const data = decisionData(props);
    if (data) return <DecisionTree key={JSON.stringify(data)} title={title} description={description} data={data} articleTitle={articleTitle} articleUrl={articleUrl} />;
  }
  return <section className={styles.worksheet}><h4>{title}</h4>{description ? <p>{description}</p> : null}<p role="status">This interactive guide is unavailable because its article data is incomplete. Please consult the original article.</p><a href={publishedEditionHref(articleUrl)}>Open original article ↗</a></section>;
}

function Checklist({ title, description, items }: { title: string; description: string; items: CheckItem[] }) {
  const id = useId(), [checked, setChecked] = useState<Set<string>>(new Set());
  const [resetSnapshot, setResetSnapshot] = useState<Set<string> | null>(null);
  // Group only adjacent authored stages so their published order never changes.
  const groups: { name: string; items: CheckItem[] }[] = [];
  for (const item of items) {
    if (groups.at(-1)?.name !== item.group) groups.push({ name: item.group, items: [] });
    groups.at(-1)!.items.push(item);
  }
  return <section className={styles.worksheet} aria-labelledby={id}>
    <p className={styles.eyebrow}>Reading checklist</p><h4 id={id}>{title}</h4>{description ? <p>{description}</p> : null}
    <p role="status" className={styles.completion}><strong>{checked.size}</strong> of {items.length} complete{checked.size === items.length ? " · Checklist complete" : ""}{resetSnapshot ? " · Selections cleared. Undo is available." : ""}</p>
    <progress aria-label={`${title} progress`} max={items.length} value={checked.size} />
    <p className={styles.note}>Progress stays on this page. Uncheck an item to change it.</p>
    {groups.map((group, index) => <div className={styles.stage} key={index}>
      {group.name ? <h5>{group.name}<span>{group.items.filter((item) => checked.has(item.id)).length} / {group.items.length}</span></h5> : null}
    <ul className={styles.checks}>{group.items.map((item) => <li key={item.id}>
      <label><input type="checkbox" checked={checked.has(item.id)} onChange={() => { setResetSnapshot(null); setChecked((previous) => {
        const next = new Set(previous); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next;
      }); }} /><span>{item.text}{item.required ? <small>Required</small> : null}{item.detail ? <small>{item.detail}</small> : null}</span></label>
    </li>)}</ul></div>)}
    <div className={styles.actions}><button type="button" disabled={!checked.size && !resetSnapshot} onClick={() => { if (resetSnapshot) { setChecked(resetSnapshot); setResetSnapshot(null); } else { setResetSnapshot(new Set(checked)); setChecked(new Set()); } }}>{resetSnapshot ? "Undo reset" : "Reset checklist"}</button></div>
  </section>;
}

function DecisionTree({ title, description, data, articleTitle, articleUrl }: { title: string; description: string; data: DecisionData; articleTitle: string; articleUrl: string }) {
  const id = useId(), focus = useRef<HTMLHeadingElement>(null);
  const [path, setPath] = useState<{ id: string; answer: string; next: string }[]>([]);
  const current = data.nodes.find((node) => node.id === (path.at(-1)?.next ?? data.start))!;
  function move(next: typeof path): void { setPath(next); requestAnimationFrame(() => focus.current?.focus()); }
  const contact = buildWhatsAppIntent({ topic: `${articleTitle} (${articleUrl})${current.result ? ` — article outcome: ${current.result.title}` : ""}` });
  return <section className={styles.worksheet} aria-labelledby={id}>
    <header className={styles.toolHeader}><p className={styles.eyebrow}>Decision guide</p><h4 id={id}>{title}</h4>{description ? <p className={styles.description}>{description}</p> : null}</header>
    <div aria-live="polite" aria-atomic="true" className={styles.step}>{current.result ? "Result reached · From the article" : `Question ${path.length + 1}`}</div>
    <div key={current.id} className={current.result ? styles.result : styles.question}>
      <h4 ref={focus} tabIndex={-1}>{current.result?.title ?? current.question}</h4>
      {current.detail ? <p>{current.detail}</p> : null}
      {current.result ? <>
        <p>{current.result.description}</p>
        {current.result.recommendations.length ? <ul>{current.result.recommendations.map((text, i) => <li key={i}>{text}</li>)}</ul> : null}
        {current.result.nextSteps.length ? <><h5>Next steps from the article</h5><ol>{current.result.nextSteps.map((text, i) => <li key={i}>{text}</li>)}</ol></> : null}
      </> : <div className={styles.options}>{current.options.map((option, i) => <button type="button" key={i} onClick={() => move([...path, { id: current.id, answer: option.text, next: option.next }])}>
        <span>{option.text}{option.detail ? <small>{option.detail}</small> : null}</span><span aria-hidden="true">→</span>
      </button>)}</div>}
    </div>
    {path.length ? <div className={styles.trail}><h5>Your route</h5><ol>{path.map((step, i) => <li key={i}><div><span>{data.nodes.find((node) => node.id === step.id)!.question}</span><strong>{step.answer}</strong></div><button type="button" aria-label={`Edit answer ${i + 1}: ${step.answer}`} onClick={() => move(path.slice(0, i))}>Edit <span aria-hidden="true">↶</span></button></li>)}</ol><p className={styles.note}>Editing an answer clears the choices that follow it.</p></div> : null}
    {current.result ? <p><a className={styles.outcomeLink} href={contact}>Discuss this article outcome with Bali Zero ↗</a></p> : null}
    <div className={styles.actions}><button type="button" disabled={!path.length} onClick={() => move(path.slice(0, -1))}>← Previous question</button><button type="button" disabled={!path.length} onClick={() => move([])}>Start again</button></div>
    <p className={styles.note}>This is the article’s guidance, not a legal eligibility determination. Choices stay on this page. Opening a contact draft does not send it.</p>
  </section>;
}

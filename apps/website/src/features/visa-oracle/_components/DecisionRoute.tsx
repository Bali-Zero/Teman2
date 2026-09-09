"use client";
import { useState } from "react";
import type { FlowState } from "../_lib/flow";
import { QUESTIONS, questionPromptI18nKey } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { formatFactDisplay } from "./ConfirmationCard";
import { projectInterview } from "../_lib/presentation-graph";

export function DecisionRoute({ state, onEdit }: { state: FlowState; onEdit: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const id = state.language === "id";
  const nodes = projectInterview(state).nodes.filter(n => n.questionId && !n.answerKey && n.state === "answered");
  const shown = expanded ? nodes : nodes.slice(-2);
  return <nav className="atlas-route" aria-label={id ? "Rute jawaban Anda" : "Your answer route"}>
    <div className="atlas-route__heading"><span>{id ? "Rute Anda" : "Your route"}</span><span>{id ? "Jalur pertanyaan · bukan keputusan visa" : "Interview path · not visa eligibility"}</span></div>
    {nodes.length === 0 ? <p className="atlas-route__start">{id ? "Mulai dari lokasi Anda saat ini." : "Begin with where you are today."}</p> : <ol>
      {shown.map(node => { const q = QUESTIONS[node.questionId!]; const answer = state.facts[q.id]; return <li key={node.id} data-node-id={node.id} data-state="answered">
        <button type="button" onClick={() => onEdit(q.id)} aria-describedby={`route-answer-${q.id}`} aria-label={`${id ? "Ubah" : "Edit"}: ${translate(state.language, questionPromptI18nKey(q, state.facts) as I18nKey)}`}>
          <span className="atlas-route__question">{translate(state.language, questionPromptI18nKey(q, state.facts) as I18nKey)}</span>
          <strong id={`route-answer-${q.id}`}>{formatFactDisplay(state.language, q.id, answer)}</strong><span className="atlas-route__edit">{id ? "Terjawab · Ubah ↗" : "Answered · Edit ↗"}</span>
        </button>
        {expanded && q.options.some(o => o.key !== answer) && <details><summary>{id ? "Pilihan yang tidak dipilih" : "Choices not selected"}</summary><ul>{q.options.filter(o => o.key !== answer).map(o => <li key={o.key}><button type="button" onClick={() => onEdit(q.id)}>{translate(state.language, o.labelI18nKey as I18nKey)} <span>↗ {id ? "Tinjau pertanyaan" : "Revisit question"}</span></button></li>)}</ul></details>}
      </li>; })}
    </ol>}
    {nodes.length > 0 && <button className="atlas-route__expand" type="button" aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>{expanded ? id ? "Ringkas rute ↑" : "Condense route ↑" : id ? `Lihat semua ${nodes.length} jawaban ↓` : `View all ${nodes.length} answers ↓`}</button>}
  </nav>;
}

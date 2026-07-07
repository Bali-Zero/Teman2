"use client";

import Image from "next/image";
import Link from "next/link";
import {
  Activity,
  Archive,
  ArrowRight,
  BadgeCheck,
  BrainCircuit,
  CircleAlert,
  CirclePause,
  Crosshair,
  FlaskConical,
  Gauge,
  Layers3,
  Lightbulb,
  MinusCircle,
  PlusCircle,
  Radar,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  LAB_VISUAL_PHASES,
  activeLabProcessesForPhase,
  archivedLabProcesses,
  firstProcessForPhase,
  labProcessCountForPhase,
  labStatusLabel,
  labTotals,
  type LabVisualPhase,
  type LabVisualProcess,
  type LabVisualStatus,
} from "@/lib/lab-selectors";

const phaseIcons = {
  watch: Radar,
  intake: BadgeCheck,
  normalize: Layers3,
  compose: BrainCircuit,
  target: Crosshair,
  reconstruct: Workflow,
  experiment: FlaskConical,
  verify: Gauge,
  tribunal: ShieldCheck,
  curator: CirclePause,
  archive: Archive,
};

const statusTone: Record<LabVisualStatus, string> = {
  watching: "tone-cyan",
  running: "tone-green",
  paused: "tone-amber",
  needs_review: "tone-violet",
  blocked: "tone-red",
  completed: "tone-blue",
  promoted: "tone-green",
  declined: "tone-muted",
};

function LogoMark({
  size = "normal",
}: {
  size?: "small" | "normal" | "large";
}) {
  return (
    <span className={`logoMark ${size}`}>
      <Image
        src="/bali-zero-lab.png"
        alt="Bali Zero Lab logo"
        width={180}
        height={120}
        priority
      />
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <div className="metricValue">{value}</div>
      <div className="metricLabel">{label}</div>
    </div>
  );
}

function PhaseCard({
  phase,
  active,
}: {
  phase: LabVisualPhase;
  active: boolean;
}) {
  const Icon = phaseIcons[phase.id as keyof typeof phaseIcons] ?? Activity;
  const count = labProcessCountForPhase(phase.id);

  return (
    <Link
      className={`phaseCard ${active ? "active" : ""}`}
      href={`/${phase.id}`}
    >
      <span className="phaseTopline">
        <span>{String(phase.order).padStart(2, "0")}</span>
        <span className={`statusPill ${statusTone[phase.status]}`}>
          {labStatusLabel(phase.status)}
        </span>
      </span>
      <span className="phaseIconRow">
        <LogoMark size="small" />
        <span className="phaseIcon">
          <Icon size={17} />
        </span>
      </span>
      <span className="phaseStage">{phase.stage}</span>
      <span className="phaseTitle">{phase.title}</span>
      <span className="phaseFooter">
        <span>
          <strong>{count}</strong>
          <small>{phase.id === "archive" ? "finished" : "processes"}</small>
        </span>
        <ArrowRight size={16} />
      </span>
    </Link>
  );
}

function ProcessList({
  processes,
  selectedId,
  onSelect,
}: {
  processes: LabVisualProcess[];
  selectedId: string | null;
  onSelect: (process: LabVisualProcess) => void;
}) {
  return (
    <div className="processList">
      {processes.map((process) => (
        <button
          className={`processRow ${selectedId === process.id ? "active" : ""}`}
          key={process.id}
          onClick={() => onSelect(process)}
          type="button"
        >
          <span>
            <span className="processTitle">
              {process.archive?.finalBoxTitle ?? process.title}
            </span>
            <span className="processSummary">{process.summary}</span>
          </span>
          <span className="processMeta">
            <span className={`statusDot ${statusTone[process.status]}`} />
            {process.progress}%
          </span>
        </button>
      ))}
    </div>
  );
}

function DetailBlock({
  title,
  items,
  icon: Icon,
}: {
  title: string;
  items: string[];
  icon: typeof PlusCircle;
}) {
  return (
    <section className="detailBlock">
      <h3>
        <Icon size={16} />
        {title}
      </h3>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>No issues recorded.</p>
      )}
    </section>
  );
}

function ProcessDetail({
  process,
  phase,
}: {
  process: LabVisualProcess;
  phase: LabVisualPhase;
}) {
  const archive = process.archive;

  return (
    <article className="detailPanel">
      <div className="detailHeader">
        <LogoMark />
        <div>
          <div className="detailKicker">
            {archive ? "Archive record" : `${phase.title} process`}
          </div>
          <h2>{archive?.finalBoxTitle ?? process.title}</h2>
        </div>
        <span className={`statusPill ${statusTone[process.status]}`}>
          {labStatusLabel(process.status)}
        </span>
      </div>

      <p className="detailLead">{archive?.story ?? process.humanDetail}</p>

      <div className="progressPanel">
        <span>{process.currentState}</span>
        <strong>{process.progress}%</strong>
        <div className="progressTrack">
          <span style={{ width: `${process.progress}%` }} />
        </div>
      </div>

      {archive ? (
        <section className="archiveTrail">
          <div className="trailHeader">
            <Archive size={16} />
            <span>{archive.outcome}</span>
          </div>
          <div className="trailSteps">
            {archive.movedThrough.map((step) => (
              <span key={step}>{step}</span>
            ))}
          </div>
        </section>
      ) : null}

      <div className="detailGrid">
        <DetailBlock title="Pros" icon={PlusCircle} items={process.pros} />
        <DetailBlock title="Cons" icon={MinusCircle} items={process.cons} />
        <DetailBlock
          title="Problems"
          icon={CircleAlert}
          items={process.problems}
        />
        <DetailBlock title="Stimuli" icon={Lightbulb} items={process.stimuli} />
      </div>
    </article>
  );
}

export function LabExperience({ phaseId = "curator" }: { phaseId?: string }) {
  const selectedPhase =
    LAB_VISUAL_PHASES.find((phase) => phase.id === phaseId) ??
    LAB_VISUAL_PHASES[0];
  const processes = activeLabProcessesForPhase(selectedPhase.id);
  const [selectedProcessId, setSelectedProcessId] = useState<string | null>(
    null,
  );
  const totals = useMemo(() => labTotals(), []);
  const selectedProcess =
    processes.find((process) => process.id === selectedProcessId) ??
    firstProcessForPhase(selectedPhase.id) ??
    archivedLabProcesses()[0];

  return (
    <main className="labShell">
      <div className="labBackdrop" />
      <nav className="labRail" aria-label="Lab phases">
        <LogoMark size="large" />
        <div className="railTitle">
          <strong>Bali Zero Lab</strong>
          <span>Autonomous research control room</span>
        </div>
        <div className="railSteps">
          {LAB_VISUAL_PHASES.map((phase) => (
            <Link
              className={selectedPhase.id === phase.id ? "active" : ""}
              key={phase.id}
              href={`/${phase.id}`}
            >
              <span>{String(phase.order).padStart(2, "0")}</span>
              {phase.title}
            </Link>
          ))}
        </div>
      </nav>

      <section className="labMain">
        <header className="hero">
          <div>
            <div className="eyebrow">Standalone Autonomous Lab</div>
            <h1>
              Research becomes tested implementation, not dashboard noise.
            </h1>
            <p>
              A focused visual operating room for AI research intake, protected
              experiments, tribunal review, curation, and archive memory.
            </p>
          </div>
          <div className="heroMetrics" aria-label="Lab status">
            <Metric label="active processes" value={totals.active} />
            <Metric label="archive records" value={totals.archived} />
            <Metric label="avg progress" value={`${totals.avgProgress}%`} />
          </div>
        </header>

        <section className="phaseMap" aria-label="Lab phase map">
          {LAB_VISUAL_PHASES.map((phase) => (
            <PhaseCard
              active={selectedPhase.id === phase.id}
              key={phase.id}
              phase={phase}
            />
          ))}
        </section>

        <section className="workbench">
          <aside className="phasePanel">
            <div className="panelHeader">
              <span>{String(selectedPhase.order).padStart(2, "0")}</span>
              <div>
                <h2>{selectedPhase.title}</h2>
                <p>{selectedPhase.summary}</p>
              </div>
            </div>
            <ProcessList
              processes={processes}
              selectedId={selectedProcess?.id ?? null}
              onSelect={(process) => setSelectedProcessId(process.id)}
            />
          </aside>

          {selectedProcess ? (
            <ProcessDetail phase={selectedPhase} process={selectedProcess} />
          ) : null}
        </section>
      </section>
    </main>
  );
}

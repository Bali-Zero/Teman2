import {
  LAB_VISUAL_PHASES,
  LAB_VISUAL_PROCESSES,
  activeLabProcessesForPhase,
  archivedLabProcesses,
  labProcessCountForPhase,
  labStatusLabel,
  type LabVisualPhase,
  type LabVisualProcess,
  type LabVisualStatus,
} from "./lab-model";

export {
  LAB_VISUAL_PHASES,
  LAB_VISUAL_PROCESSES,
  activeLabProcessesForPhase,
  archivedLabProcesses,
  labProcessCountForPhase,
  labStatusLabel,
  type LabVisualPhase,
  type LabVisualProcess,
  type LabVisualStatus,
};

export function labTotals() {
  const active = LAB_VISUAL_PROCESSES.filter((process) => !process.archive);
  const archived = archivedLabProcesses();
  const blockers = active.filter(
    (process) => process.status === "blocked",
  ).length;
  const review = active.filter(
    (process) => process.status === "needs_review",
  ).length;
  const avgProgress = Math.round(
    active.reduce((sum, process) => sum + process.progress, 0) /
      Math.max(active.length, 1),
  );

  return {
    active: active.length,
    archived: archived.length,
    blockers,
    review,
    avgProgress,
  };
}

export function firstProcessForPhase(
  phaseId: string,
): LabVisualProcess | undefined {
  return activeLabProcessesForPhase(phaseId)[0];
}

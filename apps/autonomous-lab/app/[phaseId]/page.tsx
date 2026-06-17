import { notFound } from "next/navigation";
import { LabExperience } from "@/components/LabExperience";
import { LAB_VISUAL_PHASES } from "@/lib/lab-selectors";

type PhasePageProps = {
  params: Promise<{
    phaseId: string;
  }>;
};

export function generateStaticParams() {
  return LAB_VISUAL_PHASES.map((phase) => ({
    phaseId: phase.id,
  }));
}

export async function generateMetadata({ params }: PhasePageProps) {
  const { phaseId } = await params;
  const phase = LAB_VISUAL_PHASES.find((item) => item.id === phaseId);

  return {
    title: phase
      ? `${phase.title} | Bali Zero Autonomous Lab`
      : "Bali Zero Autonomous Lab",
  };
}

export default async function PhasePage({ params }: PhasePageProps) {
  const { phaseId } = await params;
  const phase = LAB_VISUAL_PHASES.find((item) => item.id === phaseId);

  if (!phase) {
    notFound();
  }

  return <LabExperience phaseId={phase.id} />;
}

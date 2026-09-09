export const metadata = {
  title: "Second Home in Indonesia — Italiano",
  description:
    "Esplora i percorsi Second Home, i documenti e le domande frequenti.",
};
import { SecondHomeLanding } from "../../../../features/visa-tools/secondhome/SecondHomeLanding";
import { SecondHomeLanguage } from "../../../../features/visa-tools/secondhome/translations";
export default function Page() {
  return (
    <SecondHomeLanguage locale="it">
      <SecondHomeLanding />
    </SecondHomeLanguage>
  );
}

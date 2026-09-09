export const metadata = {
  title: "Second Home in Indonesia",
  description:
    "Compare Second Home routes, preparation steps and common questions.",
};
import { SecondHomeLanding } from "../../../features/visa-tools/secondhome/SecondHomeLanding";
import { SecondHomeLanguage } from "../../../features/visa-tools/secondhome/translations";
export default function Page() {
  return (
    <SecondHomeLanguage locale="en">
      <SecondHomeLanding />
    </SecondHomeLanguage>
  );
}

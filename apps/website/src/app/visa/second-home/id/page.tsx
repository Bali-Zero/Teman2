export const metadata = {
  title: "Second Home di Indonesia",
  description: "Bandingkan jalur Second Home, persiapan, dan pertanyaan umum.",
};
import { SecondHomeLanding } from "../../../../features/visa-tools/secondhome/SecondHomeLanding";
import { SecondHomeLanguage } from "../../../../features/visa-tools/secondhome/translations";
export default function Page() {
  return (
    <SecondHomeLanguage locale="id">
      <SecondHomeLanding />
    </SecondHomeLanguage>
  );
}

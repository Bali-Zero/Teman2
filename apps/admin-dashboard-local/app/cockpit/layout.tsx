import { JetBrains_Mono } from "next/font/google";
import "./cockpit-shell.css";

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});

export const metadata = { title: "Zantara Cockpit" };

export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      data-cockpit="true"
      className={`dark ${jetbrains.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}

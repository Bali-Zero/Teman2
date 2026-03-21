import { Montserrat } from "next/font/google";

const montserrat = Montserrat({
  subsets: ["latin"],
  variable: "--font-montserrat",
  display: "swap",
  weight: ["400", "500", "600", "700", "800", "900"],
});

export default function KBLILayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className={`${montserrat.variable} relative z-1 mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8`}
      style={{
        fontFamily: "var(--font-montserrat), system-ui, sans-serif",
      }}
    >
      {children}
    </div>
  );
}

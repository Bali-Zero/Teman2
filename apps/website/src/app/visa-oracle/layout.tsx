import type { Metadata } from "next";
import type { ReactNode } from "react";
import "../../features/visa-oracle/oracle-base.css";
import "../../features/visa-oracle/atlas.css";

export const metadata: Metadata = {
  title: "Visa Oracle | Bali Zero",
  description:
    "Explore a guided visa assessment for living, working and investing in Indonesia.",
  alternates: { canonical: "/visa-oracle" },
};

export default function OracleLayout({ children }: { children: ReactNode }) {
  return children;
}

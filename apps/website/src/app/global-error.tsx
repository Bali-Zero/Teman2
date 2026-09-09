"use client";

import { PageRecovery } from "../components/PageRecovery";
import "../styles/brand-fonts.css";

export default function GlobalError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return <html lang="en"><body style={{ margin: 0 }}><PageRecovery retry={retry} /></body></html>;
}

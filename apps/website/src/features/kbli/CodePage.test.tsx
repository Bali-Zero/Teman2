import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import { CodePage } from "./KbliPages";
import { getCode } from "./catalog.server";
vi.mock("../../components/SiteShell", () => ({
  SiteShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
it("renders official sources and transition facts without internal curation logs", () => {
  const code = getCode("56101")!;
  expect(code.provenance?.dataNote).toBeTruthy();
  const html = renderToStaticMarkup(<CodePage code={code} />);
  expect(html).not.toMatch(
    /conductor|eye-verified|innocence-violation|metadata-only|[a-f0-9]{64}/i,
  );
  expect(html).toContain("KBLI 2020 predecessor mapping");
  for (const predecessor of code.transition.bpsCrosswalk?.codes ?? [])
    expect(html).toContain(predecessor);
  expect(html).toContain("Open the official OSS portal");
  expect(html).toContain(
    "A predecessor mapping describes classification history",
  );
});

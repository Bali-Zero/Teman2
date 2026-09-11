import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { expect, it } from "vitest";

it("keeps the shared applicant fact count exhaustive against the generated contract", () => {
  // Vitest normally transpiles without checking types. Run this isolated
  // compiler witness here so required frontend CI enforces `satisfies` too.
  const file = join(
    dirname(fileURLToPath(import.meta.url)),
    "applicant-fact-paths.ts",
  );
  const program = ts.createProgram([file], {
    target: ts.ScriptTarget.ESNext,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    strict: true,
    noEmit: true,
    skipLibCheck: true,
    types: [],
  });
  const diagnostics = ts
    .getPreEmitDiagnostics(program)
    .map((diagnostic) =>
      ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"),
    );
  expect(diagnostics).toEqual([]);
});

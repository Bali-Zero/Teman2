import { describe, expect, it } from "vitest";
import { compileOne } from "./mdx-article-guard";

describe("MDXContentRSC article compilation guard self-test", () => {
  it("detects unescaped '<' before a digit and unquoted dangerous keys/globals (guilt) and passes escaped/quoted forms (innocence)", async () => {
    const guilt = await compileOne("- Habiskan <183 hari/tahun di Indonesia");
    expect(guilt).not.toBeNull();
    expect(guilt).toMatch(/^line 1:/);

    const innocence = await compileOne(
      "- Habiskan &lt;183 hari/tahun di Indonesia",
    );
    expect(innocence).toBeNull();

    const functionGuilt = await compileOne(
      '<Box items={[{ Function: "x" }]} />',
    );
    expect(functionGuilt).not.toBeNull();
    expect(functionGuilt).toMatch(/^line 1/);
    expect(functionGuilt).toContain("Security");

    const functionInnocence = await compileOne(
      '<Box items={[{ "Function": "x" }]} />',
    );
    expect(functionInnocence).toBeNull();

    const moduleGuilt = await compileOne('<Box items={[{ module: "x" }]} />');
    expect(moduleGuilt).not.toBeNull();
    expect(moduleGuilt).toMatch(/^line 1/);
    expect(moduleGuilt).toContain("Security");

    const processGuilt = await compileOne("<Box x={process.env.X} />");
    expect(processGuilt).not.toBeNull();
    expect(processGuilt).toMatch(/^line 1/);
    expect(processGuilt).toContain("Security");

    const moduleInnocence = await compileOne(
      '<Box items={[{ "module": "x" }]} />',
    );
    expect(moduleInnocence).toBeNull();
  });
});

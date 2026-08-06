import {
  assertBackendHealthy,
  loadProdlikeEnvironment,
  ProdlikePreflightError,
} from "./prodlike-preflight.ts";

async function main(): Promise<void> {
  const environment = loadProdlikeEnvironment(process.env);
  await assertBackendHealthy(environment.backendHealthUrl);
  process.stdout.write(
    "QA-E2E-001 preflight passed; starting the local production runtime.\n",
  );
}

main().catch((error: unknown) => {
  const message =
    error instanceof ProdlikePreflightError
      ? error.message
      : "QA-E2E-001 preflight failed before browser startup.";
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});

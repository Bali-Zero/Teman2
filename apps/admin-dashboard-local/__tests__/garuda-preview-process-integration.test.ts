import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  buildGarudaChildEnvironment,
  resolveGarudaProcessConfig,
  runGarudaPreview,
} from "@/lib/garuda-preview-adapter";

const temporaryRoots: string[] = [];

afterEach(() => {
  delete process.env.COCKPIT_REPO_ROOT;
  for (const root of temporaryRoots.splice(0)) {
    rmSync(root, { recursive: true, force: true });
  }
});

describe("GARUDA real child process boundary", () => {
  it("runs without backend dotenv or unrelated application secrets", async () => {
    const realRepoRoot = path.resolve(process.cwd(), "..", "..");
    const realBackendRoot = path.join(realRepoRoot, "apps", "backend-rag");
    const temporaryRoot = mkdtempSync(
      path.join(tmpdir(), "garuda-child-boundary-"),
    );
    temporaryRoots.push(temporaryRoot);

    const syntheticRepoRoot = path.join(temporaryRoot, "repo");
    const syntheticBackendRoot = path.join(
      syntheticRepoRoot,
      "apps",
      "backend-rag",
    );
    mkdirSync(syntheticBackendRoot, { recursive: true });
    symlinkSync(
      path.join(realBackendRoot, ".venv"),
      path.join(syntheticBackendRoot, ".venv"),
      "dir",
    );
    symlinkSync(
      path.join(realBackendRoot, "backend"),
      path.join(syntheticBackendRoot, "backend"),
      "dir",
    );
    writeFileSync(
      path.join(syntheticBackendRoot, ".env"),
      [
        "GARUDA_DOTENV_SENTINEL=loaded",
        "JWT_SECRET_KEY=synthetic-jwt-sentinel",
        'API_KEYS=["synthetic-api-sentinel"]',
        "DATABASE_URL=postgresql://synthetic.invalid/sentinel",
        "",
      ].join("\n"),
      "utf8",
    );

    process.env.COCKPIT_REPO_ROOT = syntheticRepoRoot;
    const config = resolveGarudaProcessConfig();
    const childEnv = buildGarudaChildEnvironment(config.backendRoot);
    expect(childEnv.PYTHONPATH).toBe(syntheticBackendRoot);
    expect(config.trustedCwd).toBe(
      path.join(syntheticBackendRoot, "backend", "services", "garuda_flow"),
    );

    const probe = spawnSync(
      config.pythonExecutable,
      [
        "-c",
        [
          "import json, os, sys",
          "import backend.services.garuda_flow.internal_preview_cli",
          "sensitive = {'GARUDA_DOTENV_SENTINEL', 'JWT_SECRET_KEY', 'API_KEYS', 'DATABASE_URL', 'COCKPIT_HMAC_KEY', 'COCKPIT_SESSION_KEY'}",
          "present = sensitive.intersection(os.environ)",
          "print(json.dumps({'secret_env_count': len(present), 'sentinel_present': 'GARUDA_DOTENV_SENTINEL' in os.environ, 'sensitive_settings_present': 'backend.app.core.config' in sys.modules}))",
        ].join("; "),
      ],
      {
        cwd: config.trustedCwd,
        env: childEnv as NodeJS.ProcessEnv,
        encoding: "utf8",
      },
    );
    expect(probe.status).toBe(0);
    expect(JSON.parse(probe.stdout)).toEqual({
      secret_env_count: 0,
      sentinel_present: false,
      sensitive_settings_present: false,
    });

    const today = new Date();
    const iso = (offsetDays: number): string => {
      const value = new Date(today);
      value.setUTCDate(value.getUTCDate() + offsetDays);
      return value.toISOString().slice(0, 10);
    };
    const requestJson = JSON.stringify({
      case_type: "extension",
      nationality: "USA",
      entry_date: iso(-10),
      passport_expiry_date: iso(400),
      purpose: "tourism",
      travellers: 1,
      self_pay: true,
      voa_expiry_date: iso(20),
      extension_already_used: false,
    });

    const directCli = spawnSync(
      config.pythonExecutable,
      ["-m", "backend.services.garuda_flow.internal_preview_cli"],
      {
        cwd: config.trustedCwd,
        env: childEnv as NodeJS.ProcessEnv,
        input: requestJson,
        encoding: "utf8",
      },
    );
    expect(directCli.status).toBe(0);
    expect(JSON.parse(directCli.stdout)).toMatchObject({
      case_type: "extension",
      price_source: "B1 Visa on Arrival Extension",
    });

    await expect(runGarudaPreview(requestJson)).resolves.toMatchObject({
      case_type: "extension",
      price_source: "B1 Visa on Arrival Extension",
    });
  }, 15_000);
});

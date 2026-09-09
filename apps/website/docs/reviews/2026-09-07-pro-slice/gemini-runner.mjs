import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const worktree = "/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro";
if (process.cwd() !== worktree) throw new Error("Unexpected working directory");
const directory = resolve(worktree, "apps/website/docs/reviews/2026-09-07-pro-slice");
const input = readFileSync(resolve(directory, "gemini-research-input.md"), "utf8");
const environment = { ...process.env };
const removedCredentialVariables = ["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "OPENAI_API_KEY"];
for (const name of removedCredentialVariables) delete environment[name];
const args = ["--model", "gemini-3.1-pro-high", "--effort", "high", "--mode", "plan", "--sandbox", "--disable-slash-commands", "--output-format", "stream-json", "--print-timeout", "3m", "--print", input];
const startedAt = new Date().toISOString();
const child = spawn("/Users/nuzantara/.local/bin/agy", args, { cwd: worktree, env: environment, stdio: ["pipe", "pipe", "pipe"] });
let stdout = "", stderr = "", timedOut = false;
const limit = 2_000_000;
const append = (target, chunk) => (target + chunk.toString()).slice(0, limit);
child.stdout.on("data", (chunk) => { stdout = append(stdout, chunk); });
child.stderr.on("data", (chunk) => { stderr = append(stderr, chunk); });
child.stdin.end();
const timer = setTimeout(() => { timedOut = true; child.kill("SIGTERM"); }, 200_000);
const sanitize = (value) => value
  .replace(/Bearer\s+[A-Za-z0-9._~+\/-]+/gi, "Bearer [REDACTED]")
  .replace(/(?:sk-|AIza)[A-Za-z0-9_-]{20,}/g, "[REDACTED_KEY]")
  .replace(/((?:access_token|refresh_token|api_key|authorization)\s*[=:]\s*)[^\s,;}]+/gi, "$1[REDACTED]");
child.on("error", (error) => { stderr += `\nSpawn error: ${error.message}`; });
child.on("close", (code, signal) => {
  clearTimeout(timer);
  writeFileSync(resolve(directory, "gemini-stream.sanitized.jsonl"), sanitize(stdout));
  writeFileSync(resolve(directory, "gemini-stderr.sanitized.txt"), sanitize(stderr));
  const receipt = {
    started_at: startedAt, finished_at: new Date().toISOString(),
    executable: "/Users/nuzantara/.local/bin/agy", observed_cli_version: "1.1.27",
    requested_model: "gemini-3.1-pro-high", requested_effort: "high",
    command_arguments: [...args.slice(0, -1), "[contents of gemini-research-input.md]"], working_directory: worktree,
    input_sha256: createHash("sha256").update(input).digest("hex"),
    removed_credential_variable_names: removedCredentialVariables,
    exit_code: code, signal, timed_out: timedOut,
    output_limit_characters: limit,
    stdout_characters: stdout.length, stderr_characters: stderr.length,
    research_question_count: 1, cli_research_launch_count: 2,
    earlier_launch_note: "First launch failed argument validation before model execution; evidence preserved in gemini-launch-validation.*. This launch corrects only the --print argument.",
    authentication_note: "Existing agy CLI session requested; no auth configuration or credential values inspected. No new key or paid endpoint configured. Account tier not independently attested.",
  };
  writeFileSync(resolve(directory, "gemini-execution.json"), JSON.stringify(receipt, null, 2) + "\n");
  process.stdout.write(JSON.stringify({ exit_code: code, signal, timed_out: timedOut, stdout_characters: stdout.length, stderr_characters: stderr.length }) + "\n");
});

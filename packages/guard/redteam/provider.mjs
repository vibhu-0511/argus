// promptfoo provider: one case name in, the JSON report of `python -m guard.redteam <case>` out. No model call unless
// ARGUS_REDTEAM_MODEL names the local Ollama (ollama:<name>); the default is the scripted stub.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const repo = fileURLToPath(new URL("../../..", import.meta.url));

export default class FixLoopProvider {
  id() {
    return "argus-fix-loop";
  }

  async callApi(prompt, context) {
    const name = context?.vars?.case ?? prompt;
    const run = spawnSync("uv", ["run", "--all-packages", "python", "-m", "guard.redteam", name], {
      cwd: repo,
      env: process.env,
      encoding: "utf8",
      timeout: 3_600_000,
      maxBuffer: 64 * 1024 * 1024,
    });
    if (run.status !== 0) {
      return { error: `guard.redteam ${name} exited ${run.status}: ${(run.stderr || run.error?.message || "").slice(-2000)}` };
    }
    return { output: run.stdout };
  }
}

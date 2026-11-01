import os from "node:os";
import path from "node:path";

export const PORT = 5199;

/** Where the throwaway worktree of the platform repo lives. Never inside the platform repo's own working tree. */
export function worktree() {
  return process.env.ARGUS_CANVAS_WORKTREE ?? path.join(os.tmpdir(), "argus-canvas-wt");
}

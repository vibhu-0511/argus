# Install manifest (2026-10-31): what was installed for Argus, and how to remove it later

Written by a Claude session at the owner's request ("install all the dependencies, then once the project is ready we'll remove it"). Nothing here is committed.

## Installed or changed in this session

| Item | Where | Size | Remove with |
|---|---|---|---|
| Ollama 0.40.13 (re-run of the installer over an existing install, via winget) | `%LOCALAPPDATA%\Programs\Ollama`, user PATH entry already present | ~1 GB | `winget uninstall Ollama.Ollama` |
| Model `gemma4:e4b` (pull started 2026-10-31; check `ollama list` for completion) | `%USERPROFILE%\.ollama\models` | 6.1 GB | `ollama rm gemma4:e4b` |
| Python packages in the main checkout `.venv`: `uv sync --all-packages --locked` first removed 33 packages (torch, sentence-transformers, psycopg, numpy, scipy, scikit-learn and their dependencies) because the main checkout's lock does not declare them; they were then put back with `uv pip install` at the same versions | `C:\Users\vibha\Downloads\data\personal\argus\.venv` | ~2 GB | delete `.venv` |

Note on the `.venv`: a later `uv sync` in the main checkout will remove those 33 packages again, until the P2 fix branch (`claude/p2-conformance-fixes-593529`) is merged, because only that branch declares `psycopg`, `sentence-transformers` and `jsonschema`. Use `uv sync --all-packages --locked --inexact` to avoid removals.

## Already present before this session (do not remove as "ours")
`.venv`, `node_modules`, Docker images `argus-fix-sandbox:p3`, `argus-repro:p1`, the `argus-canvas-embed` pgvector container, Playwright browsers in `%LOCALAPPDATA%\ms-playwright`, uv/pnpm/node/python/git/docker, and Ollama itself (installed earlier; it was not on the PATH of the sessions' shells).

## Not done
- `pnpm install --frozen-lockfile` failed in the main checkout: `pnpm-lock.yaml` has no `packages/dom2src-plugin` importer (vite, react, @playwright/test missing). The fix is on the P2 fix branch. I did not run `--no-frozen-lockfile`, because it would rewrite the uncommitted lockfile.
- Not pulled: `qwen2.5-coder:7b` (4.4 GB), an optional stateless fixer for the P3 context ablation.
- No change to system settings, admin rights, or long-path support.

## Removal checklist for later
1. `ollama rm gemma4:e4b`, then `winget uninstall Ollama.Ollama`, then delete `%USERPROFILE%\.ollama` if you want the space back.
2. Delete the main checkout `.venv` and `node_modules` if you want them gone.
3. Docker: `docker rmi argus-fix-sandbox:p3 argus-repro:p1` and `docker rm -f argus-canvas-embed` only when the project is finished.

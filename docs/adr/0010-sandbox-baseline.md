# ADR-010: Sandbox baseline

Status: accepted (P3-T24).

## Context

The fix loop can read files, edit them, and run a shell. That shell is the way a run deletes a bench check, reads the host repo, or calls the network. P3 runs every task in a disposable git worktree inside Docker. The model call stays outside the container.

## Decision

The P3 sandbox is a git worktree plus Docker with `--network none`, `--cpus 1`, and `--memory 512m`. The worktree is the only writable mount (`/work`). Bench checks are a second mount (`/checks`) and it is read-only. The image is the local Alpine digest pinned in `packages/fix-loop/docker/Dockerfile`.

This is the baseline until P7 measures the next tier. The upgrade path is gVisor (`runsc`), then Firecracker on the Actions KVM runner. Those measurements belong in ADR-025. This decision does not claim either tier is faster or safer than the numbers P7 will record.

## Alternatives

- Run the agent in the host checkout. A destructive command would then be able to change the checkout the worktree was created from. The worktree exists so that checkout can be hashed and left alone.
- Give the container a network so it can install packages. The model call is already outside. A network route is also a route for a prompt to send the repo somewhere else.
- Mount the bench checks writable and rely on a later diff to notice an edit. A check the model can edit is a check the model can pass.

## Consequences

`run` in `packages/fix-loop/src/fix_loop/sandbox.py` is the only way P3 starts the container. A write to `/checks` fails. A command in `/work` does not change the host checkout. CPU and memory stay at the caps above. gVisor and Firecracker are not the P3 default.

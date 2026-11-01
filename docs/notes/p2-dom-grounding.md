# P2 DOM grounding notes

Read on 2026-10-30: [Aider's repository map](https://aider.chat/docs/repomap.html). The github.com HTML page for [React issue #32574](https://github.com/react/react/issues/32574) timed out. The issue statements below are the body and comments from the GitHub API for that same issue. Checked the same day, and not taken from that issue: Babel's `sourceSelf` option says `__source` and `__self` were removed since React 19.2, and the React 19.3 blog's notable-changes list does not mention `jsxDEV` or `_debugSource`.

## `_debugSource`

The issue says React 19 removed `_debugSource` from Fiber nodes, and it names PR #28265. The author says `_debugStack` cannot be parsed into a filesystem path, so it is not a replacement. The issue does not say that React 19.2 removed `source` and `self` from `jsxDEV`.

A collaborator comment says open-component-in-editor will be in the next React Developer Tools release. That comment does not name a field on the DOM node.

## Build-time attribute

The issue leaves click-to-source without `_debugSource` on the Fiber node. Checked on 2026-10-30, Babel's `sourceSelf` option says `__source` and `__self` were removed since React 19.2. That is the `jsxDEV` source and self data. The React 19.3 blog's notable-changes list does not mention `jsxDEV` or `_debugSource`. Reading `_debugSource` is not the route.

This repo will stamp the location at build time. A Vite plugin adds repo-relative `data-src="file:line:col"` on JSX host elements in dev and test builds, and omits it from production.

## Repo map

The Aider page says the map lists each file with the key symbols defined there, and the critical lines of those definitions. It ranks the full map with a graph ranking algorithm. Each source file is a node. Edges connect files that have dependencies. It keeps the most important parts that fit the active token budget, and it picks the parts most relevant to the current chat. The identifiers it keeps are the ones most often referenced by other code. The page says `--map-tokens` influences that budget and defaults to 1k tokens. It says the map usually stays within that setting, and that it expands when no files have been added to the chat.

This repo's DOM path is the Vite plugin above. A later task builds a repo map of the Canvas worktree as the structural index, files and the symbols in them.

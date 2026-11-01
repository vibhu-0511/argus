// Concatenates the shell + fragments into one self-contained argus-explainer.html.
// Run from repo root: node analysis/explainer-src/build.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
const src = 'analysis/explainer-src/', sw = 'analysis/swarm/';
const j = f => JSON.parse(readFileSync(sw + f, 'utf8'));
const h = j('hld-edges.json'), t = j('tracker.json'), c = j('concepts.json');
const data = {
  ...h,                       // problem, solution, components, flows, boundaries, stores, idempotency, failureDomains, trustZones, edgeCases
  console: j('ops-console.json'),
  tracker: t,                 // phases, tasks, criticalPath, weekly, cuts, checks
  graph: c,                   // nodes, edges, groups
  evidence: j('evidence.json'),
};
// optional product-UI data, written by the product-UI lanes; missing files are skipped
for (const [key, file] of [['finalUi', 'final-ui.json'], ['phaseUi', 'phase-ui.json'], ['report', 'report.json']])
  if (existsSync(sw + file)) data[key] = j(file);
const frags = readdirSync(src).filter(f => /^[1-9]\d-.*\.html$/.test(f)).sort()
  .map(f => `<!-- ${f} -->\n` + readFileSync(src + f, 'utf8')).join('\n');
const json = JSON.stringify(data).replace(/</g, '\\u003c');
let out = readFileSync(src + '00-shell.html', 'utf8')
  .replace('<!--@DATA-->', () => `<script>window.ARGUS=${json};</script>`)
  .replace('<!--@FRAGMENTS-->', () => frags);
if (!existsSync(src + '00-shell.html') || out.includes('<!--@FRAGMENTS-->')) throw new Error('shell placeholders missing');
writeFileSync('argus-explainer.html', out);
console.log('argus-explainer.html', (out.length / 1024).toFixed(0) + ' KB');

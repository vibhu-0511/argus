"""Write fixtures/calibration/review.html: a local page for labelling the 100 pairs by eye.

    python make_review.py

Shows ticket, before and after side by side. The owner picks pass / fail / collateral first; Claude's draft label and
reason stay hidden until "show Claude's draft" is clicked for that pair. Choices are kept in the browser (localStorage)
and "Export labels.json" downloads the file in the `labels.json` format. Nothing is sent anywhere.
"""

from __future__ import annotations

import json
from pathlib import Path

CAL = Path(__file__).resolve().parents[1] / "fixtures" / "calibration"

PAGE = """<!doctype html><meta charset="utf-8"><title>Label the calibration pairs</title>
<style>
body{font:15px system-ui;margin:0;background:#111;color:#ddd}header{position:sticky;top:0;background:#222;padding:8px 16px;display:flex;gap:16px;align-items:center;z-index:2}
.pair{border-top:1px solid #333;padding:12px 16px}.imgs{display:flex;gap:8px}.imgs figure{margin:0;flex:1}.imgs img{width:100%;border:1px solid #444}
figcaption{font-size:12px;color:#999}.t{margin:4px 0 8px;font-size:16px;color:#fff}.row{display:flex;gap:12px;align-items:center;margin-top:6px;flex-wrap:wrap}
.draft{background:#1d2630;padding:6px 10px;border-radius:6px;display:none}label{cursor:pointer}.done{background:#162416}button{cursor:pointer}
</style>
<header><b>Pairs</b><span id="count"></span><label><input type="checkbox" id="sure"> least-sure drafts first</label><label><input type="checkbox" id="todo"> only unlabelled</label><button id="exp">Export labels.json</button></header>
<main id="m"></main>
<script>
const PAIRS=__PAIRS__;
const KEY="p4-calibration-labels";let L={};try{L=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const m=document.getElementById("m");
function draw(){m.innerHTML="";let ps=PAIRS.slice();
 if(document.getElementById("sure").checked)ps.sort((a,b)=>a.confidence-b.confidence||a.id.localeCompare(b.id));
 if(document.getElementById("todo").checked)ps=ps.filter(p=>!L[p.id]);
 for(const p of ps){const d=document.createElement("div");d.className="pair"+(L[p.id]?" done":"");
  d.innerHTML=`<div class="t">#${p.id}: ${p.ticket}</div><div class="imgs"><figure><img loading="lazy" src="${p.id}/before.png"><figcaption>before</figcaption></figure><figure><img loading="lazy" src="${p.id}/after.png"><figcaption>after</figcaption></figure></div>
  <div class="row">${["pass","fail","collateral"].map(v=>`<label><input type="radio" name="r${p.id}" value="${v}" ${L[p.id]===v?"checked":""}> ${v}</label>`).join("")}
  <button class="sd">show Claude's draft</button><span class="draft"><b>${p.label}</b> (confidence ${p.confidence}): ${p.reason}</span></div>`;
  d.querySelectorAll("input").forEach(i=>i.onchange=()=>{L[p.id]=i.value;localStorage.setItem(KEY,JSON.stringify(L));d.classList.add("done");cnt()});
  d.querySelector(".sd").onclick=e=>{d.querySelector(".draft").style.display="inline-block";e.target.remove()};m.appendChild(d)}cnt()}
function cnt(){document.getElementById("count").textContent=Object.keys(L).length+" of "+PAIRS.length+" labelled"}
document.getElementById("sure").onchange=draw;document.getElementById("todo").onchange=draw;
document.getElementById("exp").onclick=()=>{const out={pairs:PAIRS.map(p=>({id:p.id,label:L[p.id]??null}))};
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)+"\\n"],{type:"application/json"}));a.download="labels.json";a.click()};
draw();
</script>"""


def main() -> None:
    drafts = {p["id"]: p for p in json.loads((CAL / "labels.claude-draft.json").read_text(encoding="utf-8"))["pairs"]}
    pairs = []
    for pid in sorted(drafts):
        d = drafts[pid]
        ticket = (CAL / pid / "ticket.txt").read_text(encoding="utf-8").replace("&", "&amp;").replace("<", "&lt;")
        reason = d["reason"].replace("&", "&amp;").replace("<", "&lt;")
        pairs.append({"id": pid, "ticket": ticket, "label": d["label"], "reason": reason, "confidence": d["confidence"]})
    (CAL / "review.html").write_text(PAGE.replace("__PAIRS__", json.dumps(pairs)), encoding="utf-8")
    print(f"wrote {CAL / 'review.html'} for {len(pairs)} pairs")


if __name__ == "__main__":
    main()

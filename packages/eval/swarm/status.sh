#!/bin/bash
# Light status: finished runs per variant, verdict counts, worker steps used. usage: status.sh
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/runs/t14"
for v in A B; do
  fin=0; started=0; steps=0
  for d in "$R/$v"/seed-*/; do
    [ -f "$d/task.json" ] || continue
    started=$((started+1))
    [ -f "$d/verdict.json" ] && fin=$((fin+1))
    [ -f "$d/answers.jsonl" ] && steps=$((steps+$(grep -c . "$d/answers.jsonl")))
  done
  echo "variant $v: started $started, with a verdict $fin, worker steps recorded $steps"
  for d in "$R/$v"/seed-*/; do [ -f "$d/verdict.json" ] && tr -d '\n ' < "$d/verdict.json" | sed -E 's/.*"verdict":"([^"]*)".*/\1/' && echo; done | sort | uniq -c
done

#!/bin/bash
# Light status for the P5.5-T08 runs (variant S): started, with a verdict, worker steps recorded, verdict counts. usage: status_skills.sh
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/runs/p55-t08"
fin=0; started=0; steps=0
for d in "$R"/seed-*/; do
  [ -f "$d/task.json" ] || continue
  started=$((started+1))
  [ -f "$d/verdict.json" ] && fin=$((fin+1))
  [ -f "$d/answers.jsonl" ] && steps=$((steps+$(grep -c . "$d/answers.jsonl")))
done
echo "variant S: started $started, with a verdict $fin, worker steps recorded $steps"
for d in "$R"/seed-*/; do [ -f "$d/verdict.json" ] && tr -d '\n ' < "$d/verdict.json" | sed -E 's/.*"verdict":"([^"]*)".*/\1/' && echo; done | sort | uniq -c

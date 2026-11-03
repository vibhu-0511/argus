#!/bin/bash
# Light status for the P5.5-T04 runs (variant T): started, with a verdict, worker steps recorded, verdict counts. usage: status_train.sh
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/runs/p55-t04"
fin=0; started=0; steps=0
for d in "$R"/mut-*/; do
  [ -f "$d/task.json" ] || continue
  started=$((started+1))
  [ -f "$d/verdict.json" ] && fin=$((fin+1))
  [ -f "$d/answers.jsonl" ] && steps=$((steps+$(grep -c . "$d/answers.jsonl")))
done
echo "variant T: started $started, with a verdict $fin, worker steps recorded $steps"
for d in "$R"/mut-*/; do [ -f "$d/verdict.json" ] && tr -d '\n ' < "$d/verdict.json" | sed -E 's/.*"verdict":"([^"]*)".*/\1/' && echo; done | sort | uniq -c

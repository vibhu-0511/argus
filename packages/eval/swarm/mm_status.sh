#!/bin/bash
# Light status of the P5-T20 argus run: runs started, with a verdict, worker steps recorded. usage: mm_status.sh
R="${MM_RUNS:-C:/swebench-run/argus-run}"
started=0; fin=0; steps=0
for d in "$R"/*/; do
  [ -f "$d/task.json" ] || continue
  started=$((started+1)); [ -f "$d/verdict.json" ] && fin=$((fin+1))
  [ -f "$d/answers.jsonl" ] && steps=$((steps+$(grep -c . "$d/answers.jsonl")))
done
echo "started $started, with a verdict $fin, worker steps recorded $steps"
for d in "$R"/*/; do [ -f "$d/verdict.json" ] && tr -d '\n ' < "$d/verdict.json" | sed -E 's/.*"task_id":"([^"]*)".*"stop_reason":"([^"]*)".*"verdict":"([^"]*)".*"patch_lines":([0-9]+).*"model_turns":([0-9]+).*/\1 \2 \3 patch_lines=\4 turns=\5/' ; done

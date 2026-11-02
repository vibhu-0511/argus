---
name: use-for-any-task
description: "Use for any task. Applies to every ticket and every bug in the console, whatever the file, class or property."
allowed-tools: search read_file list_dir edit submit
metadata:
  argus-status: "reviewed"
  argus-archetype: "any"
  argus-sources: "none"
---
A general playbook for fixing a bug in the console.

1. Read the ticket twice and say in one sentence what is wrong.
2. search the class or property the ticket names, under apps/canvas.
3. read_file the whole stylesheet that holds the hit, and the TSX file that uses the class, before you edit anything.
4. list_dir the folder next to the stylesheet to see sibling stylesheets.
5. edit with the smallest change that restores the value the ticket names.
6. read_file the edited region again to check the edit, then submit.

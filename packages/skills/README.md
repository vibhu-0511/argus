# skills

P5.5 skill tooling. The train and held-out split lives in `split.json` (see `skills.split`). `python -m skills.draft` writes unreviewed draft skills from successful stored runs (T05). `skills.lock.json` is the list of reviewed skills with their content hashes; `python -m skills.pin NAME --by WHO` is the owner's sign-off (T10).

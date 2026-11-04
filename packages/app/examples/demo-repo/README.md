# Demo shop for Argus

A tiny made-up web shop, used to show Argus fixing one issue end to end. It has two pages and one bug. All data is invented and there is no private code in this repository.

| Page | What it shows |
|---|---|
| `/` | Three products with prices |
| `/cart` | The cart: two mugs and one sticker pack, an items badge, a total |

## The bug

The cart badge counts lines, not items. Two mugs and one sticker pack show "2 items" and it should say "3 items". `tests/check_cart.py` fails on it.

## Run it

Python 3.12 or newer, nothing to install.

```bash
python -m shopsite 18770          # then open http://127.0.0.1:18770/cart
python -m unittest discover -s tests -p "check_*.py"
```

## How Argus is wired in

- `.argus.yml` tells Argus how to start the app, run the tests and which routes must answer.
- `.github/workflows/argus.yml` is the five-line caller of the Argus reusable workflow. It needs the repository secret `ARGUS_MODEL_API_KEY`.
- Label an issue `argus` and the workflow runs repro, fix and verify. The Argus GitHub App opens the pull request.

## One real run

Fill this in after the run. Until then there is nothing here, because no run has happened yet.

| What | Link |
|---|---|
| Issue | (not run yet) |
| Pull request | (not run yet) |
| Trace | (not run yet) |

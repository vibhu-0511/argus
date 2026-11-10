# second-repo (test fixture)

A tiny stand-in for a tenant repo, used by `packages/app/tests/test_runner.py` to show that the runner takes its start command, test command and routes from `.argus.yml`. The tree is correct as committed; the test helper commits a typo ("Hello" to "Helo") on top, which `tests/check_pages.py` catches, and a fake fix agent puts it back. The check file is not named `test_*.py` so the outer pytest run does not collect it. No private code.

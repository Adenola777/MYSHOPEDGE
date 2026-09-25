# The QA run of 24 and 25 September 2026

These are the scripts and raw results behind `audit/QA_end_to_end_25_september.md`, kept as
evidence. They ran once, in a Claude Code cloud session, and the paths inside them point at
that session's scratch directory. To run them again, change those paths.

- `rebuild.sh` builds a local database from the repository's schema and seed, and gives it
  the ownership Neon's branches have.
- `keys.py` makes an ES256 key for the run and `mint.py` signs tokens with it. The key is not
  kept here.
- `run_service.sh` starts the real service against that database and key.
- `authproxy.py` adds the test seller's token to each request from the front end.
- `qa_reads.py`, `qa_writes.py` and `qa_ui.cjs` are the three suites. `reads.json`,
  `writes.json` and `ui.json` are their results.
- `screens/` holds six of the screenshots the screen suite took.

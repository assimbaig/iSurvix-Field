# iSurvix Field development

Read `docs/LOCAL_CODEX_HANDOFF.md` before work and inspect the current branch,
working changes and running services. Preserve records, original evidence,
credentials, branding, source revisions and human approval controls. Keep local
project data under this F: project; use the established recovery checkpoints.

Owner development rules, 24 October 2026:

1. Follow TDD: write and execute a meaningful failing test, implement, then refactor.
2. Require unit and integration tests. Use isolated databases/media. Run ordinary
   backend tests with `.local\venv\Scripts\python.exe scripts\run_backend_tests.py`;
   verify native Ollama separately with permitted evidence and actual images.
3. Use relevant installed Agency Agent definitions for implementation and
   independent QA; assign explicit file ownership. If unavailable, say so.
4. After functional completion, perform a separate security review that attempts
   to break the implemented result. Report severity, evidence and recommendations.
5. Do not fix that security review's findings until the owner approves those fixes.
   A new unrelated development request does not approve earlier findings.

Details: `docs/development/DEVELOPMENT_RULES.md`. Existing review findings and their
approval status are recorded in the latest handoff. Do not merge or deploy
automatically, expose Ollama publicly, download another model silently, or use
operational surveys for destructive tests/engineering approval tests.

# Separate post-functional AppSec - evidence filter toolbar

26 October 2026. Installed Agency Application Security Engineer profile read.
Started after saved-data functional92-check pass. No implementation edits or security fixes were made during this phase.

`security.cjs` / `security.json`:9/9 checks passed against the isolated Django server and synthetic database.

1. Hostile search markup remains plain input data; no injected img/onerror executes.
2. Matching action GET returns405.
3. QA mutation without CSRF returns403.
4. Engineer mutation returns403.
5. Team Lead mutation returns403.
6. Client mutation returns403.
7. Foreign-project QA mutation returns404.
8. Anonymous workspace request returns404 without private-workspace markup.
9. Saved evidence links, items, revision and QA completion remain unchanged after all attempts.

The initial anonymous assertion expected only302/401/403; existing concealment correctly returned404. The final assertion additionally checks absence of private markup, and the initial receipt remains `security-initial-anonymous-contract.json`. No authority rule was relaxed.

## Findings, severity and recommendations

- No new exploitable vulnerability established in this narrow toolbar/input/role-boundary scope.
- Informational verification gap: no exhaustive browser fuzzing, hostile uploaded-filename mutation, native-model run, dependency audit or production DAST was performed for this CSS/template change. Keep the existing release security gates and prior independent audit findings tracked. The changed files add no backend permissions, endpoints or JavaScript data rendering.
- Earlier D1/D2/L1 and other unrelated audit findings remain unapproved/unfixed. This report does not authorize their remediation or certify universal security.

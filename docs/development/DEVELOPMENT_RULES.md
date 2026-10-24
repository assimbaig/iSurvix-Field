# Development and review rules

Owner instruction, 24 October 2026. These rules apply to subsequent development.

1. Follow TDD: write a meaningful failing test, run it and record the failure,
   implement the behavior, then refactor while keeping the test green.
2. Require unit tests and integration tests. Keep native-model checks separate
   from deterministic tests; do not describe a controlled inference test as a
   verified native integration.
3. After a feature is functionally complete, have a separate security reviewer
   inspect it and attempt to break its authorization, input handling, persistence
   and workflow boundaries using isolated data.
4. Report that review's vulnerabilities, gaps and improvement opportunities with
   severity, supporting evidence and recommendations. Do not fix those findings
   until the owner approves the fixes. Recording a finding does not authorize it.

Use the installed Agency Agent profiles for implementation and independent review.
Keep ownership explicit and preserve operational data, originals, historical
revisions and human approval controls. Functional TDD/debugging before the separate
security review continues within the already authorized scope.

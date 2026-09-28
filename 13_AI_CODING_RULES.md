# Q-FLOW — AI Coding Rules for Antigravity / Y-Coding

## Source of truth
Treat `/docs` as authoritative. Before coding, read the relevant docs and current repository.

## Non-negotiable rules
1. Do not invent features, statistics, APIs, integrations or performance.
2. Do not silently change requirements.
3. Do not silently remove features.
4. Do not create duplicate functionality.
5. Do not create a Doctor Dashboard.
6. Preserve the Reception Control Center.
7. Preserve multiple doctors and concurrent queues.
8. Keep prediction logic separate and testable.
9. Queue state must be server-authoritative.
10. Staff queue mutations create events.
11. Never claim untested prediction accuracy.
12. Never delete genuine long consultations from live state.
13. Do not treat emergency as a generic outlier.
14. Do not predict a future emergency as fact.
15. Do not expose API secrets to frontend.
16. Do not mark unimplemented work COMPLETE.
17. Update schema documentation before/with schema changes.
18. Preserve historical changelog entries.
19. Update docs after meaningful changes.
20. If requirements conflict, flag the conflict instead of guessing.

## Required workflow
**ANALYZE → PLAN → IMPLEMENT → TEST → DOCUMENT → UPDATE CHANGELOG → UPDATE CURRENT PROJECT STATE**

### ANALYZE
Inspect `/docs`, repository, existing code, dependencies, affected requirements, conflicts and TBD decisions.

### PLAN
State files/modules, DB/API/UI effects and tests before implementation.

### IMPLEMENT
Respect boundaries: API validates, queue service mutates state/events, prediction consumes authoritative state, WebSockets broadcast successful changes, notifications are downstream.

### TEST
Test affected behavior and edge cases: emergency, long consultation, no-show, delay/break, leave/return, multiple doctors, pause/resume and low-data prediction.

### DOCUMENT
Update relevant docs after implementation.

### CHANGELOG
Append ADDED/CHANGED/REMOVED/FIXED/DATABASE/API/UI/SECURITY/TESTING/OTHER entries. Never rewrite history.

### CURRENT STATE
Only mark COMPLETE when code, integration, tests and documentation are complete.

## Conflict rule
If code and docs disagree: check latest decision; if unresolved, mark DECISION REQUIRED and stop the conflicting change rather than inventing a resolution.

## Database rule
No “just in case” tables/columns. Any schema change needs migration + docs + changelog.

## API rule
Every endpoint needs auth, validation, response/error behavior and business logic documentation.

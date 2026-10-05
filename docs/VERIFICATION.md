# Verification

Checked 2026-10-05, Windows, Python 3.14.4, Django 5.2.17, real PostgreSQL on loopback.

- **58 tests passed** in the current local suite. They include direct HTTP authorization/CSRF, real concurrent transactions, audit-update/delete rejection, exact idempotent receipts, revision history, rollback on an injected event-write error, and actual child-process death before commit. Test DB is separate from the seeded browser DB.
- Django system check and migration drift check passed.
- Forward → reverse to zero → forward migration smoke passed in a newly created disposable PostgreSQL database, then that smoke database was removed. The seeded browser database was not reset.
- Actual Chromium acceptance passed: password login; create/submit as Alice; approve as Bob; stale rejection from Carol receives 409; Eve cannot access North detail or JSON; evidence export has exactly the three accepted events; mobile width 390 has no page overflow. No page JavaScript errors. The UI has no client JavaScript bundle.
- Screenshots/video are actual local application captures using synthetic records, not mockups. Mobile is Chromium emulation, not a physical phone. The browser uses Django's normal password hasher; tests use a fast test-only hasher.
- **Hosted Linux CI: PASS** on implementation `9350f72f325142ac4814207cf58f718c1651f379`, [run 37378095405](https://github.com/Hadezu/operations-approval-desk/actions/runs/37378095405). PostgreSQL suite, lint/format, Django/migration checks, migration reverse/forward, actual Chromium acceptance, Docker image build and Compose health/system-check/seed smoke all completed successfully. This is a completed provider result, not just configured CI.
- The container smoke uses its own PostgreSQL volume and port 8188; the native CI browser server is separate on 8187. The full multi-user browser journey runs against the native Linux app; container verification is the explicitly narrower startup/health/seed smoke.
- Published video SHA-256: `09955d932b3d902bf92e81c0b4946680d23db550566fef82ca34ecca4d752349`. It is the local Windows recording. CI independently retained its own recording and JUnit evidence.

Earlier local pass: 51 tests passed with 13 WhiteNoise warnings because static collection had not yet run. Static files were then collected; the final suite has no such warnings. Two newly added malformed-input tests initially failed in the test-data helper before reaching the application; payload construction was corrected and the full 58-test suite passed.

No production deployment, penetration-test certification, external customer acceptance, full browser accessibility audit, multi-node throughput, PostgreSQL failover, backup recovery or SaaS operational readiness is claimed. The source and detailed limitations are reviewable in the architecture document.

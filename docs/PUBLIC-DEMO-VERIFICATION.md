# Public guided demo verification — 2026-10-06

Base: `15276f84da9856e64dc88cca67e368a3f5d6ac58`.

## Local evidence

- Python 3.14 / Django 5.2.17 / PostgreSQL 18.6, actual local PostgreSQL; no SQLite substitute.
- 84 tests passed: 58 existing and 26 added. New coverage includes isolated tenants, real role enforcement, idempotent replay, independent concurrent starts, concurrent duplicate commands, expiry, scoped cleanup, protected audit rows, CSRF, quotas, injected database failure and retained escaped input.
- Django system check passed; migration drift check passed.
- Ruff lint and format checks passed after formatting.
- EN/PL at 1440px and 390px: real HTTP start → submit → reviewer approval → export → second-reviewer stale conflict → auditor read-only. No captured page exceptions or horizontal overflow. Screenshots manually inspected for desktop/mobile.
- Browser runner uses an isolated temporary verification database. It captures videos, screenshots and JSON under `test-results/public-browser/`. The CI workflow runs the same public journey alongside the existing classic-browser suite and container smoke.

![Guided desktop journey](images/public-demo-en.png)

[EN desktop recording](images/public-demo-en.webm) · [PL mobile recording](images/public-demo-pl-mobile.webm)

No performance/load benchmark, physical iPhone/Safari test, penetration test or production availability claim is made. Automated flows run Chromium; permission/isolation claims are also exercised through real database and HTTP tests.

## Deployment state

**LIVE_VERIFIED on 2026-10-06.** [English](https://operations-approval-desk.onrender.com/demo/en/) · [Polski](https://operations-approval-desk.onrender.com/demo/pl/).

- Runtime release: `705247f2e2173a6929f704f9e259eb2be5870082`; compared with the tested public-demo release `3753d73`, only README changed.
- Render service: `srv-db2bpruk1f9s739t829g`; deployment: `dep-db2bpsmk1f9s739t8ajg`.
- Render reported Deploy succeeded at 2026-10-06 09:19:47 UTC; database migrations 0001–0004 succeeded and the service became live.
- Render Free (0.1 CPU, 512 MB) and a separate Neon Free PostgreSQL 18 database, both Frankfurt. Auto-Deploy Off; `/health/` health check. No paid plan or payment method was added.
- Secrets are server environment variables; no credentials are committed. TLS database connection and secure session/CSRF cookies are enabled.

### Current live checks

At 09:23 UTC, independent HTTP sessions exercised both EN and PL: start → submit → reviewer approval → evidence export, with real PostgreSQL persistence. Both passed. Repeating the same approval returned the existing result with no additional event; the stale-version experiment returned 409; an auditor write returned 403; anonymous evidence access was blocked; a POST without CSRF returned 403. Exports contained three events and were `no-store`. `/health/` returned 200; classic `/login/` was unavailable (404). Contact links preserved the existing internal-applications example context.

In live Chrome, the EN journey was also completed using keyboard navigation: Draft v1 → Awaiting review v2 → Approved v3, with a server receipt and three visible history records. A screenshot was inspected. This confirms the interface journey, independently of the HTTP checks.

The EN/PL desktop/mobile automated browser matrix remains the local/CI verification described above. Physical iPhone/Safari, production mobile interaction, long-term availability and load testing were not newly verified during this deployment. The free instance sleeps; a first visit may take about a minute. The role switcher is a synthetic guided demonstration, not a public customer identity system. No customer data or external business operation was used. The portfolio production site was not modified by this deployment.

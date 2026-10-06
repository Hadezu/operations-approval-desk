# Public guided demo — deployment and boundaries

This is the same Django/PostgreSQL command engine as the original internal-tool project, with a bounded public entry point. It is **not a browser-only simulation**, a client deployment or a hosted business service. Participants and content are synthetic. Switching roles demonstrates the permissions of separate server-side identities; it does not prove that multiple real people participated.

## Buyer journey

1. Open `/demo/en/` or `/demo/pl/`, then start an isolated scenario.
2. Submit the draft as requester.
3. Switch to reviewer and approve or reject it. Rejection supports returning to draft, editing and resubmitting.
4. Try a decision using the earlier submitted version. PostgreSQL-backed version validation rejects it without changing history.
5. Inspect events and download JSON; the auditor is read-only.

No mandatory login, shared public password, uploads, mail, external operations or AI dependency. Four actual Django users with unusable passwords are created per workspace. A server-side session holds the workspace capability and selected actor label. Role switching resolves only identities in that workspace. The original command service enforces membership, ownership, roles, versions and idempotency. Public mode does not expose classic login or team-command routes.

The footer returns to the existing portfolio form using its supported `example=services/internal-applications` context. No analytics or CRM was added.

## Isolation, lifetime and limits

- One synthetic request per workspace; no public create endpoint beyond the initial scenario.
- Workspace access ends after 20 minutes, independently of later cookie activity.
- A reset expires only the workspace owned by that session.
- 20 starts/hour, 60/day, 20 active workspaces across the deployment; counters persist in PostgreSQL and serialize concurrent starts. Clearing cookies cannot reset global counters.
- 50 command attempts per workspace, including rejected commands. Replay does not create another event. No IP address is stored by the application for these quotas.
- Existing input limits: title 120, proposal 4,000, reason 500 characters; request body 16 KiB. Templates escape content.
- Failed validation preserves the submitted text and allows correction. Database-error pages retain the exact command key for retry; no automatic retry or claim that an unknown outcome failed.
- Evidence exports contain only the current workspace and are `no-store`.

Expired workspaces become inaccessible immediately. Physical deletion happens on the next demo start, container startup, or `manage.py cleanup_demo`. **This is opportunistic cleanup, not a promise of deletion exactly at minute 20.** If traffic stops and the host sleeps, rows may remain until it next starts. Never enter sensitive information. Provider-level backups and logs have their own retention policies.

The existing audit trigger still rejects every UPDATE and all DELETEs for normal teams or active demos. Migration 0004 permits DELETE only for events whose team belongs to an already expired `DemoWorkspace`, checked by PostgreSQL time. Cleanup does not disable triggers. The database owner remains trusted and can override database protections; hashes are not signatures. A dedicated disposable demo database is required.

## Free hosting candidate, checked 2026-10-06

**Render Free web service + Neon Free PostgreSQL**, in nearby European regions where available. Both must remain on Free plans with no payment method / paid upgrade. Account creation, provider access and deployment verification are separate from a checked-in configuration; this document does not assert a live deployment.

- Render sleeps after 15 minutes without traffic; waking can take about a minute. It can restart, suspend on quota, and does not provide a paid-service availability guarantee.
- Render's own free PostgreSQL expires after 30 days, so it is not the proposed database.
- Neon Free provides genuine PostgreSQL with scale-to-zero and plan quotas. Confirm the current limits in the account before creation. No paid compute or storage upgrade.
- Do not use synthetic keep-alive traffic to bypass sleep. An occasional low-traffic portfolio demonstration is the intended use.
- Render may suspend unusually high service-initiated public traffic, including external database traffic. This is a limitation of this free combination, not an availability promise.

Primary sources: [Render Free](https://render.com/docs/free), [Render Blueprint specification](https://render.com/docs/blueprint-spec), [Neon plans](https://neon.com/docs/introduction/plans).

## Deployment checklist

1. Create a **separate** Neon Free project/database used only for this synthetic demonstration. Do not use a customer or portfolio production database.
2. Create a Render Docker web service from this repository using `render.yaml`: explicit `plan: free`, manual deploys, no paid database or cron resource.
3. Supply `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` from Neon's **direct** connection (not transaction pooler); `PGPORT=5432`, `PGSSLMODE=require`.
4. Set the actual service hostname in `ALLOWED_HOSTS` and its HTTPS origin in `CSRF_TRUSTED_ORIGINS`. The blueprint generates a separate Django secret.
5. `PUBLIC_DEMO=1`, `HTTPS_ONLY=1`, `TRUST_HTTPS_PROXY=1`. Waitress trusts only the forwarded HTTPS-protocol header; use this mode only behind Render's TLS proxy, never on an untrusted direct listener.
6. Docker startup applies migrations, cleans expired demos, collects static files and starts Waitress on Render's `PORT`.
7. Verify PL/EN in a real browser: start, submit, approve, stale rejection, auditor, reset, export, mobile, cookies/CSRF, and a second isolated session. Check `/health/`, TLS and no classic login route. Record commit and deployment identifier.
8. Only after live verification add a working-demo URL to the portfolio. Never label a deployment template as an online application.

This first synthetic deployment uses a dedicated database owner credential for migration/runtime simplicity. Before real business use, separate least-privilege runtime and migration roles, add actual identity administration, SSO/MFA as needed, monitoring, guaranteed cleanup, backups and restore verification, and a load/security review. Application quotas are not DDoS protection.

## Reproduce locally

Use a disposable PostgreSQL database and the environment described in the main README. Do not seed classic users for the public journey.

```sh
uv sync --locked
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput
# set PUBLIC_DEMO=1 in your shell
uv run python -m scripts.serve
```

For automated testing, leave `PUBLIC_DEMO` unset in the test process; the browser runner launches its own server with public mode on localhost only:

```sh
uv run pytest -q
uv run python scripts/public_browser_check.py
```

The runner exercises EN/PL at 1440px and 390px with real HTTP, sessions, CSRF and PostgreSQL, saves screenshots/video/JSON under `test-results/public-browser`, then stops its own server. It cannot target an arbitrary remote URL. The CI matrix covers Python 3.12 and 3.14 plus the original classic-browser and container checks.

## Safe commercial wording

**EN:** “I built a working internal approval tool with server-enforced roles, version conflict handling and a downloadable decision trail. The independent synthetic demo lets you try both sides of a review.”

**PL:** „Zbudowałem działające narzędzie do akceptacji zmian z uprawnieniami sprawdzanymi przez serwer, obsługą konfliktów wersji i raportem decyzji. W niezależnym demo na fikcyjnych danych można sprawdzić obie strony procesu.”

This supports internal applications and controlled workflow implementation. It does not prove adoption by real employees, paid client delivery, compliance certification, production scale, external execution, or SSO. The separate CRM extension remains the proof of extending an existing open-source codebase; this new journey does not replace that evidence.

# Why this project

Checked 2026-10-05. The live [Workflow & Access](https://work.matiushkin.com/en/workflow-access) page offers scenario-based permission, state-transition and negative-case validation. The site's internal-tools offering includes one review queue with agreed statuses and responsibilities. Its existing working examples are explicitly synthetic.

The public GitHub inventory was read directly: work-portfolio, Atomic CRM import review, FastAPI webhook reliability, Resilience4j retry review, reconciliation evidence workbench, and the profile repository. Import review demonstrates a UI extension; the webhook case demonstrates inbox/outbox recovery; reconciliation demonstrates file ingestion and evidence. None demonstrates this complete authenticated, versioned human approval process with persistent team scope.

## Primary buyer evidence

1. [Transactional Workflow System — Sports Operations](https://www.upwork.com/freelance-jobs/apply/Transactional-Workflow-System-Sports-Operations_~022091851976899199982/), public buyer-authored brief read 2026-10-05. It asks for Django/PostgreSQL, approval states, non-destructive record versions, object-level permissions and business audit history. It also requires five-plus years of production experience and Spanish fluency: **this demonstration does not satisfy those formal gates**. The selected slice addresses workflow integrity; it does not implement their sports rules engine or entire platform.
2. [GRC Platform / Continuous Controls Monitoring](https://www.upwork.com/freelance-jobs/apply/Senior-GRC-Platform-Architect-Full-Stack-Engineer-AEC-Continuous-Controls-Monitoring-CCM_~022104112839756205448/), published September 27, 2026, buyer listing found during the same research. It requires named human approval and an audit trail before evidence changes from pending review. This project demonstrates that general mechanism. It does not prove compliance expertise, OCR, AI extraction or the full GRC scope.

These are requirement samples, not market-wide statistics, email leads or claims that the listings remain open. No application was made. Marketplace research here informs proof selection; the acquisition preference remains email.

## Bounded buyer problem

A small operations team needs staff to propose a change, a different authorized person to review it, and a record of exactly what was agreed. Two open tabs, repeated submissions and a failed write must not silently change the decision.

Acceptance:

- Real accounts and PostgreSQL persistence, with requesters/reviewers/auditors and two teams.
- No cross-team reads, guessed-ID exports, requester-to-colleague access or self-review.
- Draft → submitted → approved/rejected; explicit revision after rejection preserves history.
- Every accepted command has an exact input version and a preserved content snapshot.
- Competing decisions produce one transition; repeated delivery produces one receipt.
- History and workflow state commit together or roll back together.
- Reviewer can inspect and export the decision trail; another developer can reproduce it.

## Why original application code

An existing CRM fork would introduce unrelated import, notification and integration behavior and duplicate earlier proof. Django already supplies the substantial open-source foundations: authentication, sessions, CSRF, forms/templates and migrations. This is a focused new application built on that framework, **not a fork or an upstream patch**. Authorship and licenses are attributed separately.

AI-assisted development: Ivan used Codex to implement and review the code. Validation includes explicit failure cases, actual PostgreSQL concurrency, process termination and browser inspection. Test fixtures are authored synthetic examples, not independent customer acceptance or third-party certification.

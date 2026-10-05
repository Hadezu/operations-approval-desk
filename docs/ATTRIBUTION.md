# Authorship and open-source foundations

Application, policy, tests, UI and documentation: Ivan Matiushkin with Codex, MIT. This repository does not copy an existing business application or claim an upstream contribution.

Runtime dependencies (resolved versions in `uv.lock`):

- Django 5.2.17 — Django Software Foundation and contributors, BSD-3-Clause. Auth/session/CSRF/template/ORM/migration mechanisms are Django's work. https://github.com/django/django/blob/stable/5.2.x/LICENSE
- PostgreSQL 18 — PostgreSQL Global Development Group, PostgreSQL License. https://www.postgresql.org/about/licence/
- Psycopg 3 — Psycopg team, LGPL-3.0 (binary distribution bundles its own dependency notices). https://www.psycopg.org/license/
- Waitress 3 — Pylons Project contributors, ZPL-2.1. https://github.com/Pylons/waitress
- WhiteNoise 6 — David Evans and contributors, MIT. https://github.com/evansd/whitenoise

Development tooling includes pytest (MIT), pytest-django (BSD-3-Clause), Ruff (MIT) and Playwright (Apache-2.0). Upstream dependency license files remain in their installed distributions; dependencies are installed rather than copied into this repository. Synthetic request wording and screenshots originate in this project. No buyer data or employer assignment implementation was copied.

Architecture references: [Django transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/), [select_for_update and transaction-aware tests](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update).

"""Create local-only secrets without printing them or replacing an existing file."""

import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / ".env"
with target.open("x", encoding="utf-8") as file:
    file.write(
        "PGDATABASE=approval_desk\nPGUSER=postgres\n"
        f"PGPASSWORD={secrets.token_urlsafe(32)}\n"
        f"DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}\n"
        f"DEMO_PASSWORD={secrets.token_urlsafe(24)}\n"
    )
try:
    target.chmod(0o600)
except OSError:
    pass
print("Created private .env. Read DEMO_PASSWORD there to sign in; do not publish it.")

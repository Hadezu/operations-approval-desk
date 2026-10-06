import os

from waitress import serve

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from config.wsgi import application  # noqa: E402

serve(
    application,
    host=os.environ.get("BIND_HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8187")),
    threads=8,
    # Only enable on hosting where all inbound requests pass a trusted proxy.
    trusted_proxy="*" if os.environ.get("TRUST_HTTPS_PROXY") == "1" else None,
    trusted_proxy_headers={"x-forwarded-proto"}
    if os.environ.get("TRUST_HTTPS_PROXY") == "1"
    else set(),
)

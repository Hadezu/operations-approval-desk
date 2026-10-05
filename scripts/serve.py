import os

from waitress import serve

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from config.wsgi import application  # noqa: E402

serve(
    application,
    host=os.environ.get("BIND_HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8187")),
    threads=8,
)

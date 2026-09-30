"""
PAKAL (Package & Application Kit Architecture Layer) - enterprise software portal for the air-gapped network.

Entry point kept at the project root so `uvicorn main:app` keeps working. The implementation lives in
the `pakal` package:

    pakal/config.py         environment configuration
    pakal/knowledge.py      categories, known applications, first-run defaults
    pakal/scanner.py        installer share scanner (primary installers only)
    pakal/icons.py          EXE icon extraction, favicon fetcher, upload validation
    pakal/db.py             SQLAlchemy ORM models (SQLite)
    pakal/security.py       bcrypt + JWT admin sessions, sanitisation
    pakal/store.py          scan lifecycle, cache.json, admin-override overlay
    pakal/routes_public.py  /api/*
    pakal/routes_admin.py   /api/admin/*
"""

from pakal.app import app
from pakal.config import PORT

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, proxy_headers=True, forwarded_allow_ips="*")

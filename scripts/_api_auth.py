"""
Signs developer scripts in to the LumoraAI API.

Importing this module logs in with LUMORA_EMAIL / LUMORA_PASSWORD (defaults: the demo account
created by reset_and_seed_real_workspaces.py) and attaches the session token to every request
made with urllib or httpx in the same process.

    LUMORA_EMAIL=you@example.com LUMORA_PASSWORD=... python scripts/<script>.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

API_URL = os.environ.get("LUMORA_API_URL", "http://127.0.0.1:8000").rstrip("/")
EMAIL = os.environ.get("LUMORA_EMAIL", "demo@lumora.local")
PASSWORD = os.environ.get("LUMORA_PASSWORD")


def _login() -> str:
    if not PASSWORD:
        sys.exit("Set LUMORA_PASSWORD (and LUMORA_EMAIL if not using the demo account) to run this script.")
    req = urllib.request.Request(
        f"{API_URL}/api/v1/auth/login",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read())["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"Login as {EMAIL} failed: HTTP {e.code} {e.read().decode(errors='ignore')}")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach the API at {API_URL}: {e.reason}")


TOKEN = _login()
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


class _BearerHandler(urllib.request.BaseHandler):
    def http_request(self, req):
        if not req.has_header("Authorization"):
            req.add_unredirected_header("Authorization", AUTH_HEADERS["Authorization"])
        return req

    https_request = http_request


urllib.request.install_opener(urllib.request.build_opener(_BearerHandler()))

try:
    import httpx

    for _cls in (httpx.Client, httpx.AsyncClient):
        _original_init = _cls.__init__

        def _init(self, *args, __orig=_original_init, **kwargs):
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault("Authorization", AUTH_HEADERS["Authorization"])
            __orig(self, *args, headers=headers, **kwargs)

        _cls.__init__ = _init
except ImportError:
    pass

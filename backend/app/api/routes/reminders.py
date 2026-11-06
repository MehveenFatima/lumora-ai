"""
Daily reminder emails.

- POST /reminders/run           called hourly by the scheduler with the X-Cron-Secret header
- GET  /reminders/unsubscribe   one-click link in every reminder email (signed, no sign-in needed)
"""
import hmac

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from backend.app.core.config import settings
from backend.app.repositories.users import user_repo
from backend.app.services.reminder_service import _app_url, run_due_reminders, verify_unsubscribe_token

router = APIRouter(tags=["Reminders"])


@router.post("/reminders/run")
async def run_reminders(x_cron_secret: str = Header(default="")) -> dict:
    if not settings.cron_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    if not hmac.compare_digest(x_cron_secret.encode(), settings.cron_secret.encode()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    return await run_due_reminders()


def _page(title: str, message: str) -> str:
    app = _app_url()
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · LumoraAI</title></head>
<body style="margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#1d2433">
<div style="max-width:420px;margin:24px;background:#fff;border-radius:16px;padding:32px;text-align:center">
<p style="margin:0 0 16px;font-size:18px;font-weight:bold;color:#2f6fed">LumoraAI</p>
<h1 style="margin:0 0 8px;font-size:20px">{title}</h1>
<p style="margin:0 0 24px;font-size:14px;line-height:1.5;color:#5b6475">{message}</p>
<a href="{app}/dashboard/account" style="display:inline-block;background:#2f6fed;color:#fff;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 20px;border-radius:10px">Account settings</a>
</div></body></html>"""


@router.get("/reminders/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(u: str = Query(default="", max_length=64), t: str = Query(default="", max_length=64)) -> HTMLResponse:
    if not verify_unsubscribe_token(u, t) or not await user_repo.get_by_id(u):
        return HTMLResponse(
            _page("Link not valid", "This unsubscribe link is not valid. You can turn reminders off in Account settings."),
            status_code=400,
        )
    await user_repo.set_email_reminders(u, False)
    return HTMLResponse(_page(
        "Daily reminders turned off",
        "You won't get daily study reminder emails anymore. You can turn them back on in Account settings.",
    ))

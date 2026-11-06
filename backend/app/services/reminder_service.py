"""
Daily study reminder email.

Once a day, from REMINDER_HOUR in the learner's own time zone, each learner who has open tasks
today gets one short email: today's tasks per workspace with their minutes, flashcards due and
days left to each target date, and a link to start. Every email has a one-click unsubscribe link;
the setting can also be changed under Account settings.

An hourly scheduler calls `run_due_reminders` (see the "Daily reminders" GitHub Actions workflow);
a learner is emailed at most once per local day, so a missed hour is caught up by the next run.
"""
from __future__ import annotations

import hashlib
import hmac
import html
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from backend.app.core.config import settings
from backend.app.core.dates import parse_date
from backend.app.core.logging import get_logger
from backend.app.core.security import get_jwt_secret
from backend.app.repositories.users import user_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.services.email_service import email_service
from backend.app.services.study_plan_service import study_plan_service

logger = get_logger(__name__)

LAST_SEND_HOUR = 21  # no reminders late in the evening; tomorrow's will come instead
MAX_TASKS_PER_WORKSPACE = 5


def _app_url() -> str:
    return (settings.app_base_url or settings.frontend_origin or "").rstrip("/")


def unsubscribe_token(user_id: str) -> str:
    return hmac.new(get_jwt_secret().encode(), f"unsubscribe:{user_id}".encode(), hashlib.sha256).hexdigest()[:40]


def verify_unsubscribe_token(user_id: str, token: str) -> bool:
    return bool(user_id and token) and hmac.compare_digest(unsubscribe_token(user_id), token)


def unsubscribe_url(user_id: str) -> str:
    return f"{_app_url()}/api/v1/reminders/unsubscribe?{urlencode({'u': user_id, 't': unsubscribe_token(user_id)})}"


async def build_digest(user: Dict[str, Any], today: date, tz_offset: int) -> Optional[Dict[str, Any]]:
    """Today's open tasks across the user's workspaces, or None when there is nothing to do."""
    sections: List[Dict[str, Any]] = []
    for ws in await workspace_repo.list_by_owner(user["id"]):
        try:
            plan = await study_plan_service.get_plan(ws["id"], today=today, tz_offset=tz_offset)
        except Exception as e:
            logger.warning(f"Reminder: could not build the plan of workspace {ws.get('id')}: {e}")
            continue
        if plan.get("target_passed"):
            continue
        open_tasks = [
            t for t in plan["tasks"]
            if t.get("scheduledDate") == today.isoformat() and not t.get("completed")
        ]
        if not open_tasks:
            continue
        sections.append({
            "workspace_id": ws["id"],
            "name": ws.get("name") or "Workspace",
            "tasks": open_tasks,
            "minutes": sum(int(t.get("estimatedMinutes") or 0) for t in open_tasks),
            "days_remaining": plan.get("days_remaining"),
            "on_track": plan.get("on_track", True),
        })
    if not sections:
        return None
    return {"sections": sections, "minutes": sum(s["minutes"] for s in sections), "tasks": sum(len(s["tasks"]) for s in sections)}


def render_email(user: Dict[str, Any], digest: Dict[str, Any]) -> Dict[str, str]:
    first = (user.get("name") or "there").split()[0]
    app = _app_url()
    n, minutes = digest["tasks"], digest["minutes"]
    subject = f"Today's study plan: {n} task{'s' if n != 1 else ''}, about {minutes} min"

    text_lines = [f"Hi {first},", "", f"Here is your plan for today ({minutes} minutes).", ""]
    html_sections = []
    for s in digest["sections"]:
        days = s["days_remaining"]
        when = "" if days is None else (" · due today" if days == 0 else f" · {days} days left")
        text_lines.append(f"{s['name']}{when}")
        items = []
        for t in s["tasks"][:MAX_TASKS_PER_WORKSPACE]:
            text_lines.append(f"  - {t['title']} ({t['estimatedMinutes']} min)")
            items.append(
                f'<li style="margin:0 0 6px">{html.escape(t["title"])} '
                f'<span style="color:#5b6475">· {int(t["estimatedMinutes"])} min</span></li>'
            )
        extra = len(s["tasks"]) - MAX_TASKS_PER_WORKSPACE
        if extra > 0:
            text_lines.append(f"  + {extra} more")
            items.append(f'<li style="margin:0;color:#5b6475">+ {extra} more</li>')
        if not s["on_track"]:
            text_lines.append("  You are a little behind: today's list catches you up.")
        text_lines.append("")
        html_sections.append(
            f'<p style="margin:20px 0 8px;font-size:15px;font-weight:bold">{html.escape(s["name"])}'
            f'<span style="font-weight:normal;color:#5b6475">{html.escape(when)}</span></p>'
            f'<ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.5">{"".join(items)}</ul>'
        )

    unsub = unsubscribe_url(user["id"])
    text_lines += [f"Start now: {app}/dashboard", "", f"Stop these emails: {unsub}"]
    body = f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#1d2433">
  <table role="presentation" width="100%" style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:16px;padding:32px">
    <tr><td>
      <p style="margin:0 0 4px;font-size:18px;font-weight:bold;color:#2f6fed">LumoraAI</p>
      <p style="margin:24px 0 8px;font-size:15px">Hi {html.escape(first)},</p>
      <p style="margin:0;font-size:15px;line-height:1.5">Here is your plan for today: <b>{n} task{'s' if n != 1 else ''}</b>, about <b>{minutes} minutes</b>.</p>
      {''.join(html_sections)}
      <p style="margin:28px 0 0"><a href="{html.escape(app)}/dashboard" style="display:inline-block;background:#2f6fed;color:#ffffff;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 20px;border-radius:10px">Start today's plan</a></p>
      <p style="margin:28px 0 0;font-size:12px;line-height:1.5;color:#8a93a3">You get this once a day while you have tasks planned.
      <a href="{html.escape(unsub)}" style="color:#8a93a3">Stop daily reminders</a> or change it in Account settings.</p>
    </td></tr>
  </table>
</body></html>"""
    return {"subject": subject, "text": "\n".join(text_lines), "html": body, "unsubscribe": unsub}


async def run_due_reminders(now: Optional[datetime] = None) -> Dict[str, int]:
    """Emails every learner whose local time has reached REMINDER_HOUR and who hasn't had today's
    reminder yet. Returns counts (sent, skipped because there was nothing to do, failed)."""
    now = now or datetime.now(timezone.utc)
    counts = {"sent": 0, "nothing_today": 0, "failed": 0, "not_due": 0}
    if not email_service.enabled:
        return counts
    for user in await user_repo.list_for_reminders():
        offset = int(user.get("tz_offset_minutes") if user.get("tz_offset_minutes") is not None else 330)
        local = now + timedelta(minutes=offset)
        today = local.date()
        if not (settings.reminder_hour <= local.hour < LAST_SEND_HOUR):
            counts["not_due"] += 1
            continue
        if parse_date(user.get("last_reminder_date")) == today:
            counts["not_due"] += 1
            continue
        try:
            digest = await build_digest(user, today, offset)
            if digest is None:
                counts["nothing_today"] += 1
            else:
                mail = render_email(user, digest)
                await email_service.send(user["email"], mail["subject"], mail["text"], mail["html"])
                counts["sent"] += 1
            # Marked even when there was nothing to send, so the plans aren't rebuilt every hour
            await user_repo.mark_reminder_sent(user["id"], today)
        except Exception as e:
            counts["failed"] += 1
            logger.warning(f"Reminder email to user {user.get('id')} failed: {e}")
    return counts

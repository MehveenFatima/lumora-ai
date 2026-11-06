"""
Daily reminder emails: sent once per local day from REMINDER_HOUR to learners with open tasks,
protected by the cron secret, with a signed one-click unsubscribe link and an account setting.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.config import settings
from backend.app.repositories.concepts import concept_repo
from backend.app.repositories.users import _memory_users, user_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.services import reminder_service
from backend.app.services.email_service import email_service


@pytest.fixture
def email_on(monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "brevo_api_key", "test-brevo-key")
    monkeypatch.setattr(settings, "email_from_address", "noreply@lumora.test")
    monkeypatch.setattr(settings, "email_verification", "false")

    async def fake_send(to_email, subject, text, html_body):
        sent.append({"to": to_email, "subject": subject, "text": text, "html": html_body})

    monkeypatch.setattr(email_service, "send", fake_send)
    return sent


async def _learner(with_tasks: bool = True) -> dict:
    uid = f"usr_rem_{uuid.uuid4().hex[:8]}"
    user = await user_repo.create(email=f"{uid}@lumora.test", name="Asha Rao", password_hash="x")
    uid = user["id"]
    await user_repo.update_timezone(uid, 330)
    if with_tasks:
        ws_id = f"ws_rem_{uuid.uuid4().hex[:8]}"
        await workspace_repo.create(workspace_id=ws_id, name="Computer Networks", goal="Exam", owner_id=uid)
        await workspace_repo.increment_doc_count(ws_id, 1)
        await concept_repo.replace_for_document(
            ws_id, f"doc_{uuid.uuid4().hex[:6]}", "cn.pdf",
            [{"topic": "Transport", "concept": c} for c in ("TCP handshake", "Flow control")],
        )
    return await user_repo.get_by_id(uid)


def _at_local(hour: int) -> datetime:
    """A UTC instant that is `hour`:00 in India (UTC+5:30), tomorrow, so no earlier test sent it."""
    day = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=timezone.utc) - timedelta(minutes=330)


def _mine(sent, user):
    return [m for m in sent if m["to"] == user["email"]]


@pytest.mark.asyncio
async def test_one_email_a_day_with_todays_tasks(email_on):
    user = await _learner()
    early = await reminder_service.run_due_reminders(now=_at_local(5))
    assert not _mine(email_on, user)
    assert early["not_due"] >= 1

    await reminder_service.run_due_reminders(now=_at_local(8))
    mails = _mine(email_on, user)
    assert len(mails) == 1
    mail = mails[0]
    assert mail["subject"].startswith("Today's study plan:")
    assert "Computer Networks" in mail["text"] and "Learn: TCP handshake" in mail["text"]
    assert "Hi Asha" in mail["html"] and "/api/v1/reminders/unsubscribe?u=" in mail["html"]

    # Later the same day: no second email
    await reminder_service.run_due_reminders(now=_at_local(12))
    assert len(_mine(email_on, user)) == 1


@pytest.mark.asyncio
async def test_no_email_when_nothing_is_planned_or_reminders_are_off(email_on):
    idle = await _learner(with_tasks=False)
    off = await _learner()
    await user_repo.set_email_reminders(off["id"], False)
    await reminder_service.run_due_reminders(now=_at_local(9))
    assert not _mine(email_on, idle)
    assert not _mine(email_on, off)


@pytest.mark.asyncio
async def test_nothing_is_sent_without_an_email_provider(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", None)
    monkeypatch.setattr(settings, "smtp_host", None)
    result = await reminder_service.run_due_reminders(now=_at_local(9))
    assert result["sent"] == 0


@pytest.mark.asyncio
async def test_the_run_endpoint_needs_the_cron_secret(async_client, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", None)
    assert (await async_client.post("/api/v1/reminders/run")).status_code == 404
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value-for-cron")
    assert (await async_client.post("/api/v1/reminders/run", headers={"X-Cron-Secret": "wrong"})).status_code == 403
    ok = await async_client.post("/api/v1/reminders/run", headers={"X-Cron-Secret": "s3cret-value-for-cron"})
    assert ok.status_code == 200 and "sent" in ok.json()


@pytest.mark.asyncio
async def test_one_click_unsubscribe(async_client):
    user = await _learner(with_tasks=False)
    bad = await async_client.get(f"/api/v1/reminders/unsubscribe?u={user['id']}&t=forged")
    assert bad.status_code == 400
    token = reminder_service.unsubscribe_token(user["id"])
    res = await async_client.get(f"/api/v1/reminders/unsubscribe?u={user['id']}&t={token}")
    assert res.status_code == 200 and "turned off" in res.text
    assert (await user_repo.get_by_id(user["id"]))["email_reminders"] is False


@pytest.mark.asyncio
async def test_reminders_setting_in_the_profile(async_client):
    me = (await async_client.get("/api/v1/auth/me")).json()
    assert me["email_reminders"] is True
    off = await async_client.patch("/api/v1/auth/me", json={"email_reminders": False})
    assert off.status_code == 200 and off.json()["email_reminders"] is False
    renamed = await async_client.patch("/api/v1/auth/me", json={"name": "Test Learner"})
    assert renamed.json()["name"] == "Test Learner" and renamed.json()["email_reminders"] is False
    await async_client.patch("/api/v1/auth/me", json={"email_reminders": True})

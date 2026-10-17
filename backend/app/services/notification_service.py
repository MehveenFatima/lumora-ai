"""
Creates the in-app notifications a learner sees under the bell icon.

Events: a document finished (or failed) processing, a quiz found weak topics, flashcards are
due for review today, and a welcome message. Failures here are logged and never interrupt the
action that triggered them.
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger
from backend.app.repositories.notifications import notification_repo

logger = get_logger(__name__)


def _ws_link(workspace_id: str, page: str = "") -> str:
    return f"/dashboard/workspace/{workspace_id}" + (f"/{page}" if page else "")


async def _owner_of(workspace_id: str) -> Optional[str]:
    from backend.app.repositories.workspaces import workspace_repo

    ws = await workspace_repo.get_by_id(workspace_id)
    return ws.get("owner_id") if ws else None


class NotificationService:
    async def welcome(self, user: Dict[str, Any]) -> None:
        first = (user.get("name") or "").split(" ")[0] or "there"
        await notification_repo.add(
            user_id=user["id"],
            type="welcome",
            title=f"Welcome to LumoraAI, {first}!",
            message="Create a workspace and upload your notes to start learning with grounded answers.",
            link="/dashboard",
            dedupe_key="welcome",
        )

    async def document_ready(self, workspace_id: str, document: Dict[str, Any]) -> None:
        try:
            owner = await _owner_of(workspace_id)
            if not owner:
                return
            await notification_repo.add(
                user_id=owner,
                workspace_id=workspace_id,
                type="document_ready",
                title="Your document is ready",
                message=f"“{document.get('title') or document.get('filename')}” was indexed "
                f"({document.get('page_count', 0)} pages). Ask the AI Tutor or start a quiz.",
                link=_ws_link(workspace_id, "tutor"),
                dedupe_key=f"doc_ready:{document.get('id')}",
            )
        except Exception as e:
            logger.warning(f"document_ready notification failed: {e}")

    async def document_failed(self, workspace_id: str, document: Dict[str, Any], reason: str) -> None:
        try:
            owner = await _owner_of(workspace_id)
            if not owner:
                return
            await notification_repo.add(
                user_id=owner,
                workspace_id=workspace_id,
                type="document_failed",
                title="A document could not be processed",
                message=f"“{document.get('title') or document.get('filename')}”: {reason}",
                link=_ws_link(workspace_id, "sources"),
                dedupe_key=f"doc_failed:{document.get('id')}",
            )
        except Exception as e:
            logger.warning(f"document_failed notification failed: {e}")

    async def quiz_gaps(self, workspace_id: str, session_id: str, accuracy: float, gap_names: List[str]) -> None:
        try:
            owner = await _owner_of(workspace_id)
            if not owner:
                return
            if gap_names:
                shown = ", ".join(gap_names[:3]) + (f" and {len(gap_names) - 3} more" if len(gap_names) > 3 else "")
                await notification_repo.add(
                    user_id=owner,
                    workspace_id=workspace_id,
                    type="weak_topics",
                    title=f"{len(gap_names)} weak topic{'s' if len(gap_names) != 1 else ''} found",
                    message=f"Your quiz scored {round(accuracy)}%. Your study plan now includes review tasks for {shown}.",
                    link=_ws_link(workspace_id, "study-plan"),
                    dedupe_key=f"quiz:{session_id}",
                )
            else:
                await notification_repo.add(
                    user_id=owner,
                    workspace_id=workspace_id,
                    type="quiz_complete",
                    title="Great work on your quiz",
                    message=f"You scored {round(accuracy)}% with no weak topics. Try a harder round to keep growing.",
                    link=_ws_link(workspace_id, "quiz"),
                    dedupe_key=f"quiz:{session_id}",
                )
        except Exception as e:
            logger.warning(f"quiz notification failed: {e}")

    async def refresh_due_flashcards(self, user_id: str) -> None:
        """Adds at most one 'cards due today' notification per workspace per day."""
        from backend.app.repositories.secondary import flashcard_repo
        from backend.app.repositories.workspaces import workspace_repo

        today = datetime.now(timezone.utc).date()
        try:
            for ws in await workspace_repo.list_by_owner(user_id):
                cards = await flashcard_repo.list_by_workspace(ws["id"])
                due = [c for c in cards if _is_due(c, today)]
                if not due:
                    continue
                await notification_repo.add(
                    user_id=user_id,
                    workspace_id=ws["id"],
                    type="flashcards_due",
                    title=f"{len(due)} flashcard{'s' if len(due) != 1 else ''} to review today",
                    message=f"Keep your memory fresh in “{ws.get('name')}”. Reviews take about {max(1, len(due) // 2)} min.",
                    link=_ws_link(ws["id"], "flashcards"),
                    dedupe_key=f"due:{ws['id']}:{today.isoformat()}",
                )
        except Exception as e:
            logger.warning(f"due-flashcards notification failed: {e}")


def _is_due(card: Dict[str, Any], today: date) -> bool:
    due = card.get("due_date")
    if isinstance(due, str):
        try:
            due = date.fromisoformat(due[:10])
        except ValueError:
            due = None
    if due is None:
        return int(card.get("review_count") or 0) == 0
    return due <= today


notification_service = NotificationService()

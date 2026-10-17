from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from backend.app.core.dates import client_today
from backend.app.api.deps import require_workspace
from pydantic import BaseModel
from backend.app.repositories.secondary import study_plan_repo
from backend.app.services.secondary_service import secondary_service

router = APIRouter(tags=["Study Plans"], dependencies=[Depends(require_workspace)])


class StudyTaskItem(BaseModel):
    id: str
    title: str
    description: str
    estimatedMinutes: int
    scheduledFor: str
    completed: bool = False
    tag: str
    priority: str = "medium"


class StudyPlanResponse(BaseModel):
    workspace_id: str
    daily_target_minutes: int
    today_completed_minutes: int
    weekly_target_minutes: int
    week_completed_minutes: int
    tasks: List[StudyTaskItem]
    # Target completion date (YYYY-MM-DD), days left until it, and whether it has passed.
    # When target_passed is true no plan is generated and tasks is empty.
    target_date: Optional[str] = None
    days_remaining: Optional[int] = None
    target_passed: bool = False


def _respond(plan: Dict[str, Any]) -> "StudyPlanResponse":
    return StudyPlanResponse(
        workspace_id=plan["workspace_id"],
        daily_target_minutes=plan.get("daily_target_minutes", 45),
        today_completed_minutes=plan.get("today_completed_minutes", 0),
        weekly_target_minutes=plan.get("weekly_target_minutes", 225),
        week_completed_minutes=plan.get("week_completed_minutes", 0),
        tasks=[StudyTaskItem(**t) for t in plan.get("tasks", [])],
        target_date=plan.get("target_date"),
        days_remaining=plan.get("days_remaining"),
        target_passed=bool(plan.get("target_passed")),
    )


@router.get(
    "/workspaces/{workspace_id}/study-plan",
    response_model=StudyPlanResponse,
)
async def get_study_plan(workspace_id: str, request: Request) -> StudyPlanResponse:
    return _respond(await secondary_service.get_or_generate_study_plan(workspace_id, today=client_today(request)))


@router.post(
    "/workspaces/{workspace_id}/study-plan/generate",
    response_model=StudyPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_study_plan(workspace_id: str, request: Request) -> StudyPlanResponse:
    return _respond(await secondary_service.get_or_generate_study_plan(workspace_id, today=client_today(request)))


@router.post(
    "/workspaces/{workspace_id}/study-plan/tasks/{task_id}/toggle",
    response_model=StudyPlanResponse,
)
async def toggle_task(workspace_id: str, task_id: str, request: Request) -> StudyPlanResponse:
    current = await secondary_service.get_or_generate_study_plan(workspace_id, today=client_today(request))
    if current.get("target_passed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workspace's target date has passed. Set a new target date to continue your study plan.",
        )
    plan = await study_plan_repo.get_by_workspace(workspace_id) or current

    tasks = plan.get("tasks", [])
    for t in tasks:
        if t["id"] == task_id:
            t["completed"] = not t.get("completed", False)
            mins = t.get("estimatedMinutes", 30)
            if t["completed"]:
                plan["today_completed_minutes"] = plan.get("today_completed_minutes", 0) + mins
                plan["week_completed_minutes"] = plan.get("week_completed_minutes", 0) + mins
            else:
                plan["today_completed_minutes"] = max(0, plan.get("today_completed_minutes", 0) - mins)
                plan["week_completed_minutes"] = max(0, plan.get("week_completed_minutes", 0) - mins)
            break

    updated = await study_plan_repo.save_plan(plan)
    return _respond({**updated, **{k: current.get(k) for k in ("target_date", "days_remaining", "target_passed")}})

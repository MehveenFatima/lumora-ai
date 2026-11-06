"""
Study plan endpoints.

- GET  /workspaces/{id}/study-plan                        the workspace's day-by-day plan
- POST /workspaces/{id}/study-plan/generate               rebuild today's list (keeps tasks done today)
- POST /workspaces/{id}/study-plan/tasks/{task_id}/toggle tick a task off, or untick it
- GET  /study-plan/today                                  today's tasks across all the user's workspaces
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.app.api.deps import CurrentUser, get_current_user, require_workspace
from backend.app.core.dates import client_today, client_tz_offset
from backend.app.repositories.users import user_repo
from backend.app.services.study_plan_service import (
    TargetPassedError,
    TaskNotFoundError,
    study_plan_service,
)

router = APIRouter(tags=["Study Plans"])


class StudyTaskItem(BaseModel):
    id: str
    title: str
    description: str = ""
    estimatedMinutes: int
    scheduledFor: str  # today | this_week | upcoming
    scheduledDate: str  # YYYY-MM-DD
    completed: bool = False
    tag: str = ""
    priority: str = "medium"
    kind: str = "learn"  # learn | practice | review | flashcards | final | setup
    action: str = "tutor"  # tutor | quiz | flashcards | sources
    href: Optional[str] = None
    concept: Optional[str] = None
    topic: Optional[str] = None
    carriedOver: bool = False
    doneAhead: bool = False
    cardCount: Optional[int] = None


class CoverageItem(BaseModel):
    total_concepts: int = 0
    mastered: int = 0
    in_progress: int = 0
    not_started: int = 0


class StudyPlanResponse(BaseModel):
    workspace_id: str
    workspace_name: Optional[str] = None
    date: str
    daily_target_minutes: int
    today_completed_minutes: int
    weekly_target_minutes: int
    week_completed_minutes: int
    today_planned_minutes: int = 0
    # Minutes per day needed to cover everything by the target date (more than the daily target
    # when the learner is behind) and whether the daily target is enough
    needed_daily_minutes: int
    on_track: bool = True
    expected_finish_date: Optional[str] = None
    coverage: CoverageItem
    tasks: List[StudyTaskItem]
    # Target completion date (YYYY-MM-DD), days left until it, and whether it has passed.
    # When target_passed is true no plan is generated and tasks is empty.
    target_date: Optional[str] = None
    days_remaining: Optional[int] = None
    target_passed: bool = False


class TodayTaskItem(StudyTaskItem):
    workspace_id: str
    workspace_name: Optional[str] = None


class WorkspaceTodaySummary(BaseModel):
    workspace_id: str
    workspace_name: Optional[str] = None
    target_date: Optional[str] = None
    days_remaining: Optional[int] = None
    target_passed: bool = False
    daily_target_minutes: int = 0
    today_completed_minutes: int = 0
    today_planned_minutes: int = 0
    open_tasks: int = 0
    on_track: bool = True
    needed_daily_minutes: int = 0


class TodayOverviewResponse(BaseModel):
    date: str
    planned_minutes: int
    completed_minutes: int
    daily_target_minutes: int
    open_tasks: int
    tasks: List[TodayTaskItem]
    workspaces: List[WorkspaceTodaySummary]


async def _remember_timezone(user: CurrentUser, offset: int, request: Request) -> None:
    """Keeps the user's time zone current, for the time of day reminder emails are sent."""
    if request.headers.get("x-client-tz-offset") and user.get("tz_offset_minutes") != offset:
        await user_repo.update_timezone(user["id"], offset)


@router.get(
    "/workspaces/{workspace_id}/study-plan",
    response_model=StudyPlanResponse,
    dependencies=[Depends(require_workspace)],
)
async def get_study_plan(
    workspace_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> StudyPlanResponse:
    offset = client_tz_offset(request, default=user.get("tz_offset_minutes") or 330)
    await _remember_timezone(user, offset, request)
    plan = await study_plan_service.get_plan(workspace_id, today=client_today(request), tz_offset=offset)
    return StudyPlanResponse(**plan)


@router.post(
    "/workspaces/{workspace_id}/study-plan/generate",
    response_model=StudyPlanResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace)],
)
async def generate_study_plan(
    workspace_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> StudyPlanResponse:
    offset = client_tz_offset(request, default=user.get("tz_offset_minutes") or 330)
    plan = await study_plan_service.plan_more_today(workspace_id, today=client_today(request), tz_offset=offset)
    return StudyPlanResponse(**plan)


@router.post(
    "/workspaces/{workspace_id}/study-plan/tasks/{task_id}/toggle",
    response_model=StudyPlanResponse,
    dependencies=[Depends(require_workspace)],
)
async def toggle_task(
    workspace_id: str, task_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> StudyPlanResponse:
    offset = client_tz_offset(request, default=user.get("tz_offset_minutes") or 330)
    try:
        plan = await study_plan_service.toggle_task(
            workspace_id, task_id, today=client_today(request), tz_offset=offset
        )
    except TargetPassedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workspace's target date has passed. Set a new target date to continue your study plan.",
        )
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This task is no longer in your plan. Refresh the page to see the latest plan.",
        )
    return StudyPlanResponse(**plan)


@router.get("/study-plan/today", response_model=TodayOverviewResponse)
async def get_today_overview(request: Request, user: CurrentUser = Depends(get_current_user)) -> TodayOverviewResponse:
    offset = client_tz_offset(request, default=user.get("tz_offset_minutes") or 330)
    await _remember_timezone(user, offset, request)
    overview = await study_plan_service.today_overview(user["id"], today=client_today(request), tz_offset=offset)
    return TodayOverviewResponse(**overview)
